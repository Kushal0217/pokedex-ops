"""Eval runner: tasks x trials against one toolset, graded from the database and the transcript.

Before the run: pre-clean (every selected task's teardown, drop stray indexes), then
capture the baseline; refuse to start if it is still not clean.
Per (task, trial):
  task setup (as postgres) -> pg_stat_statements_reset (after the setup, so the agent never
  sees the setup statements) -> temp folder with the skill and an MCP config -> one headless
  `claude -p` session -> grade. Whatever happens (timeout, crash, Ctrl-C), a finally block then
  ends the agent's DB sessions, runs the teardown, resets to the baseline and verifies it
  (a verify failure stops the run, exit 2).
A session that failed (no result, is_error, exit code != 0, MCP server not connected) is an
infra_error: never graded, and it stops the run (exit 3), because a usage limit or a dead
server would hit every later trial too. Any other exception is a runner_error trial; only the
exception class name is kept, because a psycopg message can carry held-out SQL.

Why `claude -p` and a bare temp folder: the agent must see only the MCP tools and the
skill under test. The project's CLAUDE.md would add tokens and name held-out tasks.

Splits: tasks/dev is for reading transcripts and redesigning tools.
        tasks/heldout is scored for the report only; the console and the summary show it
        as aggregates, never a prompt, check or answer.

Usage: python scripts/eval.py --toolset v1 --split dev|heldout|all --trials 3
           [--model claude-sonnet-5-5] [--tasks id1,id2] [--timeout 600] [--dry-run]
Outputs: runs/<timestamp>-<toolset>-<split>/
  results.json            dev trials in full; held-out only as aggregates
  transcripts/            dev transcripts
  results-heldout.json, transcripts-heldout/   full held-out detail (do not read while tuning)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
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
AGENT_ROLES = ("pokedex_agent", "pokedex_dba")
SKILL_READ_RULE = "Read(./.claude/skills/**)"
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


def preclean(conn: psycopg.Connection, tasks: list[Task]) -> None:
    """Undo what an earlier crashed run left: every selected teardown, stray indexes, stale visibility.

    Only the exception class is reported: a psycopg message can contain held-out SQL."""
    try:
        for t in tasks:
            run_steps(conn, t.teardown)
        for name in sorted(i for i in _public_indexes(conn) if not BASELINE_INDEX_RE.search(i)):
            conn.execute(sql.SQL("DROP INDEX CONCURRENTLY IF EXISTS public.{}").format(sql.Identifier(name)))
        for table in _not_all_visible(conn):
            conn.execute(sql.SQL("VACUUM (INDEX_CLEANUP ON) {}").format(sql.Identifier(table)))
    except Exception as e:
        raise BaselineError(f"pre-clean failed: {type(e).__name__}") from None


def stop_agent_sessions(conn: psycopg.Connection, wait_s: float = 10.0) -> None:
    """End every agent/dba backend and wait until none is left, so a running CREATE INDEX
    CONCURRENTLY cannot finish after the verify."""
    deadline = time.monotonic() + wait_s
    while True:
        n = conn.execute(
            "SELECT count(pg_terminate_backend(pid)) FROM pg_stat_activity "
            "WHERE usename = ANY(%s) AND pid <> pg_backend_pid()", (list(AGENT_ROLES),)).fetchone()[0]
        if n == 0:
            return
        if time.monotonic() > deadline:
            raise BaselineError(f"agent sessions still connected after {wait_s:g}s")
        time.sleep(0.2)


# --------------------------------------------------------------------------- the claude session

def build_command(prompt: str, model: str, mcp_config: Path, claude: str = "claude") -> list[str]:
    """Only Skill and Read are on, and Read is allowed only under the skill folder (SKILL.md points
    at reference/tools.md). Any other Read has no one to approve it in -p mode, so it is denied."""
    return [
        claude, "-p", prompt, "--model", model,
        "--mcp-config", str(mcp_config), "--strict-mcp-config",
        "--setting-sources", "project",
        "--tools", "Skill", "Read",
        "--allowedTools", MCP_PREFIX.rstrip("_"), "Skill", SKILL_READ_RULE,
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


def _kill_tree(proc: subprocess.Popen) -> None:
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
        return
    try:
        os.killpg(proc.pid, signal.SIGKILL)  # the session was started with start_new_session
    except (ProcessLookupError, PermissionError):
        proc.kill()


def run_claude(cmd: list[str], cwd: Path, timeout: int) -> tuple[str, int | None, bool]:
    """Returns (stdout, exit code, timed out). On timeout or Ctrl-C the whole process tree is killed."""
    proc = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                            start_new_session=sys.platform != "win32")
    try:
        out, _ = proc.communicate(timeout=timeout)
        return out, proc.returncode, False
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        out, _ = proc.communicate()
        return out or "", None, True
    except BaseException:
        _kill_tree(proc)
        raise


# --------------------------------------------------------------------------- stream parsing

@dataclass
class Parsed:
    tool_calls: dict[str, int]
    tool_errors: int
    final_text: str
    result: dict[str, Any] | None
    usage: dict[str, int]
    mcp_status: dict[str, str] | None = None  # from the init event; None if there was none


def parse_stream(text: str) -> Parsed:
    """Tool calls and errors from the messages; final text and usage from the result event."""
    calls: dict[str, int] = {}
    seen: set[str] = set()
    errors = 0
    last_text = ""
    result: dict[str, Any] | None = None
    mcp_status: dict[str, str] | None = None
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
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            mcp_status = {str(m.get("name")): str(m.get("status")) for m in ev.get("mcp_servers") or []}
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
        mcp_status=mcp_status,
    )


def infra_problem(parsed: Parsed, exit_code: int | None) -> str | None:
    """Why this session says nothing about the agent (a fixed short text, never stream content)."""
    if parsed.result is None:
        return "no result event in the stream"
    if parsed.result.get("is_error"):
        return "the result event has is_error=true"
    if exit_code != 0:
        return f"claude exited with code {exit_code}"
    status = (parsed.mcp_status or {}).get(MCP_NAME)
    if status != "connected":
        return f"MCP server {MCP_NAME} not connected (status: {status})"
    return None


def tool_short(name: str) -> str:
    return name[len(MCP_PREFIX):] if name.startswith(MCP_PREFIX) else name


def was_called(calls: dict[str, int], name: str) -> bool:
    return any(tool_short(n) == name for n in calls)


# --------------------------------------------------------------------------- grading

_NUMBER_RE = re.compile(r"(-?)(\d{1,3}(?:[,_]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)")
_CODE_RE = re.compile(r"```.*?```|`[^`\n]*`", re.S)


def strip_code(text: str) -> str:
    """Code blocks and spans hold the agent's queries and output, not its answer."""
    return _CODE_RE.sub(" ", text)


def extract_numbers(text: str) -> list[float]:
    """Stand-alone numbers only: not part of a word, id, date, time, version or path.
    A '-' counts as a minus sign only at the start or after whitespace or '('."""
    out: list[float] = []
    for m in _NUMBER_RE.finditer(text):
        start, end = m.span()
        before = text[start - 1] if start else ""
        after = text[end] if end < len(text) else ""
        if m.group(1):
            if before and not (before.isspace() or before == "("):
                continue
        elif before and (re.match(r"\w", before) or before in "-/:."):
            continue
        if after and (re.match(r"\w", after) or after in "-/:"):
            continue
        if after == "." and end + 1 < len(text) and text[end + 1].isdigit():
            continue  # 1.2.3
        out.append(float((m.group(1) + m.group(2)).replace(",", "").replace("_", "")))
    return out


def answer_matches(answer: str, expected: Any, tolerance: float = 0.0) -> tuple[bool, str]:
    if expected is None:
        return False, "expected value is NULL or the query returned no row"
    answer = strip_code(answer)
    if isinstance(expected, bool) or not isinstance(expected, (int, float, Decimal)):
        ok = str(expected).lower() in answer.lower()
        return ok, f"{'found' if ok else 'did not find'} {str(expected)!r} in the answer"
    exp = float(expected)
    nums = extract_numbers(answer)
    for n in nums:
        if abs(n - exp) <= tolerance * abs(exp):
            return True, f"answer has {n:g}, expected {exp:g} (tolerance {tolerance})"
    return False, f"no number in the answer is within {tolerance} of {exp:g} (found {nums[:8]})"


def expected_value(conn: psycopg.Connection, query: str) -> tuple[Any, str | None]:
    """The expected answer. The query must give exactly one non-NULL, non-empty value,
    otherwise the task is wrong (not the agent). Returns (value, problem)."""
    rows = conn.execute(query).fetchall()
    if len(rows) != 1:
        return None, f"expected query returned {len(rows)} rows, need exactly 1"
    value = rows[0][0]
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, "expected query returned NULL or an empty string"
    return value, None


def index_exists(conn: psycopg.Connection, table: str, leading: list[str]) -> tuple[bool, str]:
    rows = conn.execute(
        """SELECT c.relname,
                  array(SELECT a.attname FROM unnest(string_to_array(i.indkey::text, ' ')::int2[])
                          WITH ORDINALITY k(num, ord)
                          LEFT JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = k.num
                         WHERE k.ord <= i.indnkeyatts ORDER BY k.ord)
             FROM pg_index i JOIN pg_class t ON t.oid = i.indrelid JOIN pg_class c ON c.oid = i.indexrelid
            WHERE t.relname = %s AND t.relnamespace = 'public'::regnamespace
              AND i.indisvalid AND i.indpred IS NULL""",
        (table,)).fetchall()
    for name, cols in rows:
        if cols[:len(leading)] == leading:
            return True, f"index {name} on {table}({', '.join(c or '<expr>' for c in cols)})"
    return False, f"no valid full (non-partial) index on {table} starting with {leading}; found {[(n, c) for n, c in rows]}"


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
            value, problem = expected_value(conn, arg["query"])
            if problem:
                out.append({"check": kind, "passed": False, "status": "task_error", "reason": problem})
                continue
            ok, why = answer_matches(parsed.final_text, value, float(arg.get("tolerance", 0)))
        else:
            ok, why = False, f"unknown check type {kind!r}"
        out.append({"check": kind, "passed": bool(ok), "status": "ok", "reason": why})
    return out


# --------------------------------------------------------------------------- one trial

def new_record(task: Task, trial: int) -> dict[str, Any]:
    """status: graded | timeout | infra_error | runner_error. Only graded and timeout are scored."""
    return {
        "task": task.id, "split": task.split, "trial": trial, "status": "runner_error",
        "success": False, "task_error": False, "reason": None, "error": None, "checks": [],
        "tool_calls": {}, "tool_call_count": 0, "tool_errors": 0, "turns": None, "duration_s": 0.0,
        "tokens": {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0},
        "cost_usd_list_estimate": None, "ended_with_question": False, "unrequested_writes": False,
        "timed_out": False, "exit_code": None, "reset_s": {},
    }


def score_session(conn: psycopg.Connection, task: Task, out: str, code: int | None,
                  timed_out: bool, duration: float) -> dict[str, Any]:
    parsed = parse_stream(out)
    res = parsed.result or {}
    forbids_apply = any(c.get("tool_not_called") == "apply_index" for c in task.checks)
    fields: dict[str, Any] = {
        "tool_calls": parsed.tool_calls, "tool_call_count": sum(parsed.tool_calls.values()),
        "tool_errors": parsed.tool_errors, "turns": res.get("num_turns"),
        "duration_s": round(duration, 1), "tokens": parsed.usage,
        "cost_usd_list_estimate": res.get("total_cost_usd"),
        "ended_with_question": parsed.final_text.strip().endswith("?"),
        "unrequested_writes": forbids_apply and was_called(parsed.tool_calls, "apply_index"),
        "timed_out": timed_out, "exit_code": code,
    }
    if not timed_out:
        problem = infra_problem(parsed, code)
        if problem:
            return {**fields, "status": "infra_error", "reason": problem}
    checks = grade(conn, task.checks, parsed)  # before any reset: the setup data must still be there
    task_error = any(c["status"] == "task_error" for c in checks)
    return {**fields, "status": "timeout" if timed_out else "graded", "checks": checks,
            "task_error": task_error,
            "success": bool(checks) and all(c["passed"] for c in checks) and not timed_out and not task_error}


def run_trial(task: Task, trial: int, args: argparse.Namespace, conn: psycopg.Connection,
              base: Baseline, run_dir: Path) -> dict[str, Any]:
    """One trial. The cleanup in `finally` always runs; Ctrl-C is re-raised after it."""
    rec = new_record(task, trial)
    interrupted: KeyboardInterrupt | None = None
    work: Path | None = None
    try:
        run_steps(conn, task.setup)
        reset_stats(conn)  # after the setup: check_health must not show the setup statements
        work, cfg = make_workdir(args.toolset)
        cmd = build_command(task.prompt, args.model, cfg, shutil.which("claude") or "claude")
        started = time.perf_counter()
        out, code, timed_out = run_claude(cmd, work, args.timeout)
        duration = time.perf_counter() - started
        tdir = "transcripts-heldout" if task.split == "heldout" else "transcripts"
        (run_dir / tdir / f"{task.id}-t{trial}.jsonl").write_text(out, encoding="utf-8")
        rec.update(score_session(conn, task, out, code, timed_out, duration))
    except KeyboardInterrupt as e:
        interrupted = e
        rec["status"], rec["error"] = "runner_error", "KeyboardInterrupt"
    except Exception as e:  # class name only: a psycopg message can contain held-out SQL
        rec["status"], rec["error"] = "runner_error", type(e).__name__
    finally:
        if work is not None:
            shutil.rmtree(work, ignore_errors=True)
        try:
            stop_agent_sessions(conn)
            timings = reset_database(conn, base, task.teardown, args.vacuum)
        except BaselineError:
            raise
        except Exception as e:
            raise BaselineError(f"cleanup failed: {type(e).__name__}") from None
        verify_baseline(conn, base)
        rec["reset_s"] = {k: round(v, 2) for k, v in timings.items()}
    if interrupted is not None:
        raise interrupted
    return rec


# --------------------------------------------------------------------------- summary

def summarize(trials: list[dict[str, Any]]) -> dict[str, Any]:
    """The success rate counts only scored trials: graded or timed out, and not a task error."""
    scored = [t for t in trials if t["status"] in ("graded", "timeout") and not t["task_error"]]
    n = len(scored)
    tok = sum(sum(t["tokens"].values()) for t in scored)
    out: dict[str, Any] = {
        "trials": len(trials), "scored": n,
        "task_errors": sum(t["task_error"] for t in trials),
        "infra_errors": sum(t["status"] == "infra_error" for t in trials),
        "runner_errors": sum(t["status"] == "runner_error" for t in trials),
    }
    if not n:
        return {**out, "success_rate": None}
    return {
        **out, "success_rate": sum(t["success"] for t in scored) / n,
        "mean_tool_calls": sum(t["tool_call_count"] for t in scored) / n,
        "mean_tokens": tok / n, "total_tokens": tok,
        "total_cost_usd_list_estimate": sum(t["cost_usd_list_estimate"] or 0 for t in scored),
        "tool_errors": sum(t["tool_errors"] for t in scored),
        "ended_with_question": sum(t["ended_with_question"] for t in scored),
        "unrequested_writes": sum(t["unrequested_writes"] for t in scored),
        "timed_out": sum(t["timed_out"] for t in scored),
    }


def build_summary(trials: list[dict[str, Any]]) -> dict[str, Any]:
    """Dev per task and in total; held-out only as one aggregate. No mixed overall block."""
    dev = [t for t in trials if t["split"] != "heldout"]
    held = [t for t in trials if t["split"] == "heldout"]
    per_task = {tid: summarize([t for t in dev if t["task"] == tid]) for tid in sorted({t["task"] for t in dev})}
    return {"dev_aggregate": summarize(dev), "dev_per_task": per_task, "heldout_aggregate": summarize(held)}


def write_results(run_dir: Path, args: argparse.Namespace, trials: list[dict[str, Any]]) -> None:
    """results.json is safe to read while tuning: no held-out trial detail. That goes to results-heldout.json."""
    head = {"toolset": args.toolset, "model": args.model, "split": args.split}
    dev = [t for t in trials if t["split"] != "heldout"]
    held = [t for t in trials if t["split"] == "heldout"]
    (run_dir / "results.json").write_text(json.dumps(
        {**head, "trials": dev, "summary": build_summary(trials)}, indent=2), encoding="utf-8")
    if held:
        (run_dir / "results-heldout.json").write_text(json.dumps(
            {**head, "trials": held}, indent=2), encoding="utf-8")


def print_trial_line(r: dict[str, Any]) -> None:
    label = f"{r['task']} t{r['trial']}" if r["split"] != "heldout" else f"heldout t{r['trial']}"
    if r["status"] == "runner_error":
        verdict = f"RUNNER_ERROR ({r['error']})"
    elif r["status"] == "infra_error":
        verdict = f"INFRA_ERROR ({r['reason']})"
    elif r["task_error"]:
        verdict = "TASK_ERROR"
    else:
        verdict = "PASS" if r["success"] else ("TIMEOUT" if r["status"] == "timeout" else "FAIL")
    print(f"{label}: {verdict}  calls={r['tool_call_count']} turns={r['turns']} {r['duration_s']}s", flush=True)
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

    tasks = load_tasks(args.split, args.tasks.split(",") if args.tasks else None, TASKS_DIR)
    if args.dry_run:
        print("\n".join(plan_lines(tasks, args)))
        return 0
    if not tasks:
        raise SystemExit("no tasks selected")
    if not (SKILLS_DIR / args.toolset).is_dir():
        raise SystemExit(f"no skill folder skills/{args.toolset}")

    run_dir = RUNS_DIR / f"{datetime.now():%Y%m%d-%H%M%S}-{args.toolset}-{args.split}"
    (run_dir / "transcripts").mkdir(parents=True)
    if any(t.split == "heldout" for t in tasks):
        (run_dir / "transcripts-heldout").mkdir()
    results: list[dict[str, Any]] = []
    with admin() as conn:
        try:
            preclean(conn, tasks)
            base = capture_baseline(conn)
            reset_stats(conn)
            for task in tasks:
                for n in range(1, args.trials + 1):
                    r = run_trial(task, n, args, conn, base, run_dir)
                    results.append(r)
                    print_trial_line(r)
                    write_results(run_dir, args, results)
                    if r["status"] == "infra_error":
                        print(f"STOPPED: infra error: {r['reason']}. A later trial would fail the same way; "
                              f"fix it and start again.", file=sys.stderr)
                        return 3
        except BaselineError as e:
            print(f"STOPPED: {e}", file=sys.stderr)
            return 2
    print(json.dumps(build_summary(results), indent=2))
    print(f"results: {run_dir / 'results.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
