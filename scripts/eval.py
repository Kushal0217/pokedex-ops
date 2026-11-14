"""Eval runner: tasks x trials against one toolset, graded from the database and the transcript.

Per (task, trial):
  pg_stat_statements_reset -> task setup (as postgres) -> temp folder with the skill and
  an MCP config -> one headless `claude -p` session -> grade -> teardown + reset to the
  verified baseline -> verify the baseline (stop the whole run if it differs).

Why `claude -p` and a bare temp folder: the agent must see only the MCP tools and the
skill under test. The project's CLAUDE.md would add tokens and name held-out tasks.

Splits: tasks/dev is for reading transcripts and redesigning tools.
        tasks/heldout is scored for the report only; the console and the summary show it
        as aggregates, never a prompt, check or answer.

Usage: python scripts/eval.py --toolset v1 --split dev|heldout|all --trials 3
           [--model claude-sonnet-5-5] [--tasks id1,id2] [--timeout 600] [--dry-run]
Outputs: runs/<timestamp>-<toolset>-<split>/{transcripts/<task>-t<n>.jsonl, results.json}
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import yaml
from psycopg import sql

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server import config  # noqa: E402

TASKS_DIR = ROOT / "tasks"
SKILLS_DIR = ROOT / "skills"
RUNS_DIR = ROOT / "runs"
DEFAULT_MODEL = "claude-sonnet-5-5"
MCP_NAME = "pokedex-ops"
MCP_PREFIX = f"mcp__{MCP_NAME}__"
WORKLOAD_TABLES = ("trainers", "teams", "team_members", "battles", "encounters")
BASELINE_INDEX_RE = re.compile(r"(_pkey|_name_key)$")


class BaselineError(RuntimeError):
    """The database is not at the verified baseline. The run must stop."""


# --------------------------------------------------------------------------- tasks

@dataclass
class Task:
    id: str
    prompt: str
    split: str
    setup: list[str] = field(default_factory=list)
    teardown: list[str] = field(default_factory=list)
    checks: list[dict[str, Any]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


def load_tasks(split: str, only: list[str] | None = None, tasks_dir: Path = TASKS_DIR) -> list[Task]:
    splits = ["dev", "heldout"] if split == "all" else [split]
    tasks: list[Task] = []
    for s in splits:
        for path in sorted((tasks_dir / s).glob("*.yaml")):
            d = yaml.safe_load(path.read_text(encoding="utf-8"))
            tasks.append(Task(
                id=d["id"], prompt=" ".join(str(d["prompt"]).split()), split=s,
                setup=[step["sql"] for step in d.get("setup") or []],
                teardown=[step["sql"] for step in d.get("teardown") or []],
                checks=d.get("checks") or [], tags=d.get("tags") or [],
            ))
    if only:
        missing = set(only) - {t.id for t in tasks}
        if missing:
            raise SystemExit(f"unknown task id(s) in --tasks: {', '.join(sorted(missing))}")
        tasks = [t for t in tasks if t.id in only]
    return tasks


# --------------------------------------------------------------------------- database

def admin() -> psycopg.Connection:
    """Autocommit postgres connection: VACUUM and DROP INDEX CONCURRENTLY need it."""
    return psycopg.connect(config.ADMIN_DSN, autocommit=True)


@dataclass
class Baseline:
    indexes: frozenset[str]
    counts: dict[str, int]


def _public_indexes(conn: psycopg.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")}


def _public_counts(conn: psycopg.Connection) -> dict[str, int]:
    tables = [r[0] for r in conn.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1")]
    return {t: conn.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(t))).fetchone()[0]
            for t in tables}


def _not_all_visible(conn: psycopg.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT relname FROM pg_class WHERE relnamespace = 'public'::regnamespace AND relkind = 'r' "
        "AND relname = ANY(%s) AND relallvisible <> relpages", (list(WORKLOAD_TABLES),)).fetchall()
    return sorted(r[0] for r in rows)


def capture_baseline(conn: psycopg.Connection) -> Baseline:
    """Snapshot the clean state. Refuses (never repairs) a database that is not clean."""
    indexes = _public_indexes(conn)
    extra = sorted(i for i in indexes if not BASELINE_INDEX_RE.search(i))
    if extra:
        raise BaselineError(f"cannot start: extra indexes in public: {extra}")
    dirty = _not_all_visible(conn)
    if dirty:
        raise BaselineError(f"cannot start: relallvisible != relpages on {dirty}; run VACUUM on them")
    return Baseline(frozenset(indexes), _public_counts(conn))


def verify_baseline(conn: psycopg.Connection, base: Baseline) -> None:
    problems: list[str] = []
    indexes = _public_indexes(conn)
    if indexes != base.indexes:
        problems.append(f"indexes differ: extra={sorted(indexes - base.indexes)} "
                        f"missing={sorted(base.indexes - indexes)}")
    counts = _public_counts(conn)
    for t in sorted(set(counts) | set(base.counts)):
        if counts.get(t) != base.counts.get(t):
            problems.append(f"row count of {t}: {counts.get(t)} != baseline {base.counts.get(t)}")
    dirty = _not_all_visible(conn)
    if dirty:
        problems.append(f"relallvisible != relpages on {dirty}")
    if problems:
        raise BaselineError("baseline check failed: " + "; ".join(problems))


def reset_stats(conn: psycopg.Connection) -> None:
    conn.execute("SELECT pg_stat_statements_reset()")


def run_steps(conn: psycopg.Connection, statements: list[str]) -> None:
    for stmt in statements:
        conn.execute(stmt)


def tables_to_vacuum(conn: psycopg.Connection) -> list[str]:
    """Tables with dead tuples or rows added since the last vacuum (their pages are not all-visible)."""
    conn.execute("SELECT pg_stat_force_next_flush()")
    return [r[0] for r in conn.execute(
        "SELECT relname FROM pg_stat_user_tables WHERE schemaname = 'public' "
        "AND (n_dead_tup > 0 OR n_ins_since_vacuum > 0) ORDER BY 1")]


def reset_database(conn: psycopg.Connection, base: Baseline, teardown: list[str] | None = None,
                   vacuum: str = "dirty") -> dict[str, float]:
    """Teardown, drop non-baseline indexes, vacuum, reset query stats. Returns timings (s)."""
    t0 = time.perf_counter()
    run_steps(conn, teardown or [])
    for name in sorted(_public_indexes(conn) - base.indexes):
        conn.execute(sql.SQL("DROP INDEX CONCURRENTLY IF EXISTS public.{}").format(sql.Identifier(name)))
    t1 = time.perf_counter()
    if vacuum == "all":
        targets = sorted(base.counts)
    else:
        targets = tables_to_vacuum(conn)
    for t in targets:
        conn.execute(sql.SQL("VACUUM (INDEX_CLEANUP ON) {}").format(sql.Identifier(t)))
    t2 = time.perf_counter()
    reset_stats(conn)
    return {"teardown_and_drop_s": t1 - t0, "vacuum_s": t2 - t1}


# --------------------------------------------------------------------------- the claude session

def build_command(prompt: str, model: str, mcp_config: Path, claude: str = "claude") -> list[str]:
    """Built-in tools other than Skill are off, so the database is reachable only through MCP."""
    return [
        claude, "-p", prompt, "--model", model,
        "--mcp-config", str(mcp_config), "--strict-mcp-config",
        "--setting-sources", "project",
        "--tools", "Skill",
        "--allowedTools", MCP_PREFIX.rstrip("_"), "Skill",
        "--max-turns", "30", "--no-session-persistence",
        "--output-format", "stream-json", "--verbose",
    ]


def make_workdir(toolset: str, skills_dir: Path = SKILLS_DIR) -> tuple[Path, Path]:
    """Empty temp folder with only the skill and the MCP config. Returns (folder, config path)."""
    src = skills_dir / toolset
    if not src.is_dir():
        raise SystemExit(f"no skill folder {src}")
    work = Path(tempfile.mkdtemp(prefix="pokedex-eval-"))
    shutil.copytree(src, work / ".claude" / "skills" / "pokedex-ops")
    cfg = work / "mcp.json"
    cfg.write_text(json.dumps({"mcpServers": {MCP_NAME: {
        "command": sys.executable,
        "args": ["-m", "server.mcp_server", "--toolset", toolset],
    }}}, indent=2), encoding="utf-8")
    return work, cfg


def run_claude(cmd: list[str], cwd: Path, timeout: int) -> tuple[str, int | None, bool]:
    """Returns (stdout, exit code, timed out). On timeout the whole process tree is killed."""
    proc = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    try:
        out, _ = proc.communicate(timeout=timeout)
        return out, proc.returncode, False
    except subprocess.TimeoutExpired:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
        else:
            proc.kill()
        out, _ = proc.communicate()
        return out or "", None, True


# --------------------------------------------------------------------------- stream parsing

@dataclass
class Parsed:
    tool_calls: dict[str, int]
    tool_errors: int
    final_text: str
    result: dict[str, Any] | None
    usage: dict[str, int]


def parse_stream(text: str) -> Parsed:
    """Tool calls and errors from the messages; final text and usage from the result event."""
    calls: dict[str, int] = {}
    seen: set[str] = set()
    errors = 0
    last_text = ""
    result: dict[str, Any] | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "result":
            result = ev
            continue
        content = (ev.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            kind = block.get("type")
            if ev.get("type") == "assistant" and kind == "tool_use" and block.get("id") not in seen:
                seen.add(block.get("id"))
                name = block["name"]
                calls[name] = calls.get(name, 0) + 1
            elif ev.get("type") == "assistant" and kind == "text":
                last_text = block.get("text", "")
            elif ev.get("type") == "user" and kind == "tool_result" and block.get("is_error"):
                errors += 1
    final = (result or {}).get("result")
    u = (result or {}).get("usage") or {}
    return Parsed(
        tool_calls=calls, tool_errors=errors,
        final_text=final if isinstance(final, str) else last_text, result=result,
        usage={"input": u.get("input_tokens", 0), "output": u.get("output_tokens", 0),
               "cache_read": u.get("cache_read_input_tokens", 0),
               "cache_write": u.get("cache_creation_input_tokens", 0)},
    )


def tool_short(name: str) -> str:
    return name[len(MCP_PREFIX):] if name.startswith(MCP_PREFIX) else name


def was_called(calls: dict[str, int], name: str) -> bool:
    return any(tool_short(n) == name for n in calls)


# --------------------------------------------------------------------------- grading

_NUMBER_RE = re.compile(r"(?<![\w.])-?(?:\d{1,3}(?:[,_]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)")


def extract_numbers(text: str) -> list[float]:
    return [float(m.group().replace(",", "").replace("_", "")) for m in _NUMBER_RE.finditer(text)]


def answer_matches(answer: str, expected: Any, tolerance: float = 0.0) -> tuple[bool, str]:
    if expected is None:
        return False, "expected value is NULL or the query returned no row"
    if isinstance(expected, bool) or not isinstance(expected, (int, float, Decimal)):
        ok = str(expected).lower() in answer.lower()
        return ok, f"{'found' if ok else 'did not find'} {str(expected)!r} in the answer"
    exp = float(expected)
    nums = extract_numbers(answer)
    for n in nums:
        if abs(n - exp) <= tolerance * abs(exp):
            return True, f"answer has {n:g}, expected {exp:g} (tolerance {tolerance})"
    return False, f"no number in the answer is within {tolerance} of {exp:g} (found {nums[:8]})"


def index_exists(conn: psycopg.Connection, table: str, leading: list[str]) -> tuple[bool, str]:
    rows = conn.execute(
        """SELECT c.relname,
                  array(SELECT a.attname FROM unnest(string_to_array(i.indkey::text, ' ')::int2[])
                          WITH ORDINALITY k(num, ord)
                          LEFT JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = k.num
                         WHERE k.ord <= i.indnkeyatts ORDER BY k.ord)
             FROM pg_index i JOIN pg_class t ON t.oid = i.indrelid JOIN pg_class c ON c.oid = i.indexrelid
            WHERE t.relname = %s AND t.relnamespace = 'public'::regnamespace AND i.indisvalid""",
        (table,)).fetchall()
    for name, cols in rows:
        if cols[:len(leading)] == leading:
            return True, f"index {name} on {table}({', '.join(c or '<expr>' for c in cols)})"
    return False, f"no valid index on {table} starting with {leading}; found {[(n, c) for n, c in rows]}"


def grade(conn: psycopg.Connection, checks: list[dict[str, Any]], parsed: Parsed) -> list[dict[str, Any]]:
    out = []
    for check in checks:
        (kind, arg), = check.items()
        if kind == "tool_called":
            ok, why = was_called(parsed.tool_calls, arg), f"{arg} {'was' if was_called(parsed.tool_calls, arg) else 'was not'} called"
        elif kind == "tool_not_called":
            called = was_called(parsed.tool_calls, arg)
            ok, why = not called, f"{arg} {'was called' if called else 'was not called'}"
        elif kind == "index_exists":
            ok, why = index_exists(conn, arg["table"], list(arg["leading_columns"]))
        elif kind == "answer_matches":
            row = conn.execute(arg["query"]).fetchone()
            ok, why = answer_matches(parsed.final_text, row[0] if row else None, float(arg.get("tolerance", 0)))
        else:
            ok, why = False, f"unknown check type {kind!r}"
        out.append({"check": kind, "passed": bool(ok), "reason": why})
    return out


# --------------------------------------------------------------------------- one trial

def run_trial(task: Task, trial: int, args: argparse.Namespace, conn: psycopg.Connection,
              base: Baseline, run_dir: Path) -> dict[str, Any]:
    reset_stats(conn)
    run_steps(conn, task.setup)
    work, cfg = make_workdir(args.toolset)
    try:
        cmd = build_command(task.prompt, args.model, cfg, shutil.which("claude") or "claude")
        started = time.perf_counter()
        out, code, timed_out = run_claude(cmd, work, args.timeout)
        duration = time.perf_counter() - started
    finally:
        shutil.rmtree(work, ignore_errors=True)
    (run_dir / "transcripts" / f"{task.id}-t{trial}.jsonl").write_text(out, encoding="utf-8")

    parsed = parse_stream(out)
    checks = grade(conn, task.checks, parsed)  # before any reset: the setup data must still be there
    timings = reset_database(conn, base, task.teardown, args.vacuum)
    verify_baseline(conn, base)

    res = parsed.result or {}
    forbids_apply = any(c.get("tool_not_called") == "apply_index" for c in task.checks)
    return {
        "task": task.id, "split": task.split, "trial": trial,
        "success": bool(checks) and all(c["passed"] for c in checks) and not timed_out,
        "checks": checks,
        "tool_calls": parsed.tool_calls, "tool_call_count": sum(parsed.tool_calls.values()),
        "tool_errors": parsed.tool_errors, "turns": res.get("num_turns"),
        "duration_s": round(duration, 1), "tokens": parsed.usage,
        "cost_usd_list_estimate": res.get("total_cost_usd"),
        "ended_with_question": parsed.final_text.strip().endswith("?"),
        "unrequested_writes": forbids_apply and was_called(parsed.tool_calls, "apply_index"),
        "timed_out": timed_out, "exit_code": code, "reset_s": {k: round(v, 2) for k, v in timings.items()},
    }


# --------------------------------------------------------------------------- summary

def summarize(trials: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(trials)
    if not n:
        return {"trials": 0}
    tok = sum(sum(t["tokens"].values()) for t in trials)
    return {
        "trials": n, "success_rate": sum(t["success"] for t in trials) / n,
        "mean_tool_calls": sum(t["tool_call_count"] for t in trials) / n,
        "mean_tokens": tok / n, "total_tokens": tok,
        "total_cost_usd_list_estimate": sum(t["cost_usd_list_estimate"] or 0 for t in trials),
        "tool_errors": sum(t["tool_errors"] for t in trials),
        "ended_with_question": sum(t["ended_with_question"] for t in trials),
        "unrequested_writes": sum(t["unrequested_writes"] for t in trials),
        "timed_out": sum(t["timed_out"] for t in trials),
    }


def build_summary(trials: list[dict[str, Any]]) -> dict[str, Any]:
    """Per task for dev; held-out tasks only as one aggregate."""
    dev = [t for t in trials if t["split"] != "heldout"]
    held = [t for t in trials if t["split"] == "heldout"]
    per_task = {tid: summarize([t for t in dev if t["task"] == tid]) for tid in sorted({t["task"] for t in dev})}
    return {"overall": summarize(trials), "dev_per_task": per_task, "heldout_aggregate": summarize(held)}


def print_trial_line(r: dict[str, Any]) -> None:
    label = f"{r['task']} t{r['trial']}" if r["split"] != "heldout" else f"heldout t{r['trial']}"
    print(f"{label}: {'PASS' if r['success'] else 'FAIL'}  calls={r['tool_call_count']} "
          f"turns={r['turns']} {r['duration_s']}s", flush=True)
    if r["split"] != "heldout":
        for c in r["checks"]:
            print(f"    [{'x' if c['passed'] else ' '}] {c['check']}: {c['reason']}")


# --------------------------------------------------------------------------- main

def plan_lines(tasks: list[Task], args: argparse.Namespace) -> list[str]:
    cfg = Path("<tmp>/mcp.json")
    lines = [f"toolset={args.toolset} model={args.model} trials={args.trials} timeout={args.timeout}s "
             f"tasks={len(tasks)} ({sum(t.split == 'heldout' for t in tasks)} held out)"]
    for t in tasks:
        for n in range(1, args.trials + 1):
            if t.split == "heldout":
                lines.append(f"heldout trial {n}: claude -p <held-out prompt> ...")
                continue
            cmd = build_command(t.prompt, args.model, cfg)
            lines.append(f"{t.id} t{n}: " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
    return lines


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--toolset", default="v1")
    p.add_argument("--split", choices=["dev", "heldout", "all"], default="dev")
    p.add_argument("--trials", type=int, default=3)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--tasks", help="comma-separated task ids")
    p.add_argument("--timeout", type=int, default=600, help="wall-clock seconds per session")
    p.add_argument("--vacuum", choices=["dirty", "all"], default="dirty",
                   help="which tables to VACUUM after each trial")
    p.add_argument("--dry-run", action="store_true", help="print the plan; run nothing, touch no database")
    args = p.parse_args(argv)

    tasks = load_tasks(args.split, args.tasks.split(",") if args.tasks else None)
    if args.dry_run:
        print("\n".join(plan_lines(tasks, args)))
        return 0
    if not tasks:
        raise SystemExit("no tasks selected")
    if not (SKILLS_DIR / args.toolset).is_dir():
        raise SystemExit(f"no skill folder skills/{args.toolset}")

    run_dir = RUNS_DIR / f"{datetime.now():%Y%m%d-%H%M%S}-{args.toolset}-{args.split}"
    (run_dir / "transcripts").mkdir(parents=True)
    results: list[dict[str, Any]] = []
    with admin() as conn:
        base = capture_baseline(conn)
        reset_stats(conn)
        try:
            for task in tasks:
                for n in range(1, args.trials + 1):
                    r = run_trial(task, n, args, conn, base, run_dir)
                    results.append(r)
                    print_trial_line(r)
                    (run_dir / "results.json").write_text(json.dumps(
                        {"toolset": args.toolset, "model": args.model, "split": args.split,
                         "trials": results, "summary": build_summary(results)}, indent=2), encoding="utf-8")
        except BaselineError as e:
            print(f"STOPPED: {e}", file=sys.stderr)
            return 2
    print(json.dumps(build_summary(results), indent=2))
    print(f"results: {run_dir / 'results.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
