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

Usage: python scripts/eval.py --toolset v1 --split dev|heldout|all --trials 1
           [--model claude-sonnet-5-5] [--effort medium] [--tasks id1,id2] [--timeout 600]
           [--run NAME] [--max-trials N] [--stop-at-5h 0.90] [--stop-at-7d 0.80] [--dry-run]
Outputs: runs/<NAME or timestamp-toolset-split>/{transcripts/<task>-t<n>.jsonl,
         trials/<task>-t<n>.json (one per trial, written atomically), results.json}
A run is resumable: rerun with the same --run NAME and finished trials are skipped.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
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
DEFAULT_EFFORT = "medium"
MAX_REPLIES = 3
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
    answers: list[dict[str, Any]] = field(default_factory=list)


TASK_KEYS = {"id", "prompt", "setup", "teardown", "checks", "tags", "answers"}
CHECK_KINDS = {"tool_called", "tool_not_called", "index_exists", "answer_matches"}
CREATE_INDEX_RE = re.compile(r"\s*CREATE\s+(UNIQUE\s+)?INDEX\b", re.IGNORECASE)


def _bad(path: Path, split: str, reason: str, detail: str = "") -> SystemExit:
    """Held-out files get the file name and the reason only, never prompt or SQL text."""
    return SystemExit(f"invalid task file {path.name}: {reason}"
                      + (f" ({detail})" if detail and split != "heldout" else ""))


def _steps(path: Path, split: str, d: dict[str, Any], key: str) -> list[str]:
    raw = d.get(key) or []
    if not isinstance(raw, list):
        raise _bad(path, split, f"{key} must be a list")
    out = []
    for step in raw:
        if not isinstance(step, dict) or set(step) != {"sql"} or not isinstance(step["sql"], str):
            raise _bad(path, split, f"each {key} step must be a map with the single key sql")
        out.append(step["sql"])
    return out


def _validate_check(path: Path, split: str, check: Any) -> None:
    if not isinstance(check, dict) or len(check) != 1:
        raise _bad(path, split, "a check must be a map with exactly one key")
    (kind, arg), = check.items()
    if kind not in CHECK_KINDS:
        raise _bad(path, split, "unknown check kind", repr(kind))
    ok = {
        "tool_called": isinstance(arg, str), "tool_not_called": isinstance(arg, str),
        "index_exists": isinstance(arg, dict) and isinstance(arg.get("table"), str)
                        and isinstance(arg.get("leading_columns"), list),
        "answer_matches": isinstance(arg, dict) and isinstance(arg.get("query"), str),
    }[kind]
    if not ok:
        raise _bad(path, split, f"malformed argument for check {kind}")


def _validate_answers(path: Path, split: str, raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise _bad(path, split, "answers must be a list")
    for entry in raw:
        if (not isinstance(entry, dict) or set(entry) != {"when_all", "reply"}
                or not isinstance(entry["reply"], str) or not entry["reply"].strip()
                or not isinstance(entry["when_all"], list) or not entry["when_all"]
                or not all(isinstance(w, str) and w for w in entry["when_all"])):
            raise _bad(path, split, "malformed answers entry (need when_all: [str, ...] and reply: str)")
    return raw


def parse_task(path: Path, split: str) -> Task:
    try:
        d = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        raise _bad(path, split, "not valid YAML") from None
    if not isinstance(d, dict):
        raise _bad(path, split, "top level must be a map")
    unknown = sorted(set(d) - TASK_KEYS)
    if unknown:
        raise _bad(path, split, "unknown top-level key(s)", ", ".join(map(str, unknown)))
    if not isinstance(d.get("id"), str) or not d.get("prompt"):
        raise _bad(path, split, "id and prompt are required")
    if d["id"] != path.stem:
        raise _bad(path, split, "id does not match the file name", f"id {d['id']!r}")
    setup, teardown = _steps(path, split, d, "setup"), _steps(path, split, d, "teardown")
    if any(not CREATE_INDEX_RE.match(stmt) for stmt in setup) and not teardown:
        raise _bad(path, split, "a setup step that is not CREATE INDEX needs a teardown")
    checks = d.get("checks") or []
    if not isinstance(checks, list):
        raise _bad(path, split, "checks must be a list")
    for check in checks:
        _validate_check(path, split, check)
    tags = d.get("tags") or []
    if not isinstance(tags, list):
        raise _bad(path, split, "tags must be a list")
    return Task(id=d["id"], prompt=" ".join(str(d["prompt"]).split()), split=split, setup=setup,
                teardown=teardown, checks=checks, tags=tags,
                answers=_validate_answers(path, split, d.get("answers") or []))


def load_tasks(split: str, only: list[str] | None = None, tasks_dir: Path = TASKS_DIR) -> list[Task]:
    splits = ["dev", "heldout"] if split == "all" else [split]
    tasks = [parse_task(path, s) for s in splits for path in sorted((tasks_dir / s).glob("*.yaml"))]
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

def build_command(prompt: str, model: str, mcp_config: Path, claude: str = "claude",
                  effort: str = DEFAULT_EFFORT, resume: str | None = None,
                  persist: bool = False) -> list[str]:
    """Built-in tools other than Skill are off, so the database is reachable only through MCP.

    Only the v1 skill is allowed. `persist` keeps the session on disk so a reply can resume it.
    """
    cmd = [claude, "-p", prompt]
    if resume:
        cmd += ["--resume", resume]
    cmd += [
        "--model", model, "--effort", effort,
        "--mcp-config", str(mcp_config), "--strict-mcp-config",
        "--setting-sources", "project",
        "--tools", "Skill",
        "--allowedTools", MCP_PREFIX.rstrip("_"), f"Skill({MCP_NAME})",
        "--max-turns", "30",
    ]
    if not persist:
        cmd.append("--no-session-persistence")
    return cmd + ["--output-format", "stream-json", "--verbose"]


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
    init: dict[str, Any] | None = None  # the first system/init event
    skill_inputs: list[str] = field(default_factory=list)  # skill named by each Skill tool_use
    rate_limit: dict[str, Any] | None = None  # the latest rate_limit_info


def parse_stream(text: str) -> Parsed:
    """Tool calls and errors from the messages; final text and usage from the result event."""
    calls: dict[str, int] = {}
    seen: set[str] = set()
    errors = 0
    last_text = ""
    result: dict[str, Any] | None = None
    init: dict[str, Any] | None = None
    skills: list[str] = []
    rate: dict[str, Any] | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(ev, dict):
            continue
        if ev.get("type") == "result":
            result = ev
            continue
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            init = init or ev
            continue
        if ev.get("type") == "rate_limit_event":
            if isinstance(ev.get("rate_limit_info"), dict):
                rate = ev["rate_limit_info"]
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
                if name == "Skill":
                    inp = block.get("input") or {}
                    skills.append(str(inp.get("skill") or inp.get("command") or ""))
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
        init=init, skill_inputs=skills, rate_limit=rate,
    )


def skill_was_loaded(skill_inputs: list[str]) -> bool:
    return any(s.startswith(MCP_NAME) for s in skill_inputs)


def merge_parsed(parts: list[Parsed]) -> Parsed:
    """One trial can span several invocations: sum counts, usage, turns, cost; keep the last text."""
    calls: dict[str, int] = {}
    usage: dict[str, int] = {}
    for p in parts:
        for k, v in p.tool_calls.items():
            calls[k] = calls.get(k, 0) + v
        for k, v in p.usage.items():
            usage[k] = usage.get(k, 0) + v
    results = [p.result for p in parts if p.result]
    merged = None
    if results:
        merged = dict(results[-1])
        merged["num_turns"] = sum(r.get("num_turns") or 0 for r in results)
        merged["total_cost_usd"] = sum(r.get("total_cost_usd") or 0 for r in results)
    rates = [p.rate_limit for p in parts if p.rate_limit]
    return Parsed(
        tool_calls=calls, tool_errors=sum(p.tool_errors for p in parts),
        final_text=parts[-1].final_text if parts else "", result=merged, usage=usage,
        init=parts[0].init if parts else None,
        skill_inputs=[s for p in parts for s in p.skill_inputs],
        rate_limit=rates[-1] if rates else None,
    )


def isolation_problems(init: dict[str, Any], toolset: str, home: Path | None = None) -> list[str]:
    """Why the session did not see exactly the MCP tools and the skill under test."""
    from server import toolsets

    problems = []
    want = {"Skill"} | {MCP_PREFIX + t.name for t in toolsets.load(toolset).tools}
    have = set(init.get("tools") or [])
    if have != want:
        problems.append(f"tools differ: extra={sorted(have - want)} missing={sorted(want - have)}")
    servers = {m.get("name"): m.get("status") for m in init.get("mcp_servers") or []}
    if servers.get(MCP_NAME) != "connected":
        problems.append(f"MCP server {MCP_NAME} is {servers.get(MCP_NAME, 'absent')}, not connected")
    skills = set(init.get("skills") or [])
    if MCP_NAME not in skills:
        problems.append(f"skill {MCP_NAME} is not loaded")
    personal = (home or Path.home()) / ".claude" / "skills"
    if personal.is_dir():
        leaked = sorted(skills & {p.name for p in personal.iterdir() if p.is_dir()})
        if leaked:
            problems.append(f"personal skill(s) leaked into the session: {leaked}")
    return problems


def match_answer(answers: list[dict[str, Any]], text: str) -> str | None:
    """Reply of the first entry whose when_all words all appear in the text (case-insensitive)."""
    low = text.lower()
    for entry in answers:
        if all(w.lower() in low for w in entry["when_all"]):
            return entry["reply"]
    return None


def tool_short(name: str) -> str:
    return name[len(MCP_PREFIX):] if name.startswith(MCP_PREFIX) else name


def was_called(calls: dict[str, int], name: str) -> bool:
    return any(tool_short(n) == name for n in calls)


# --------------------------------------------------------------------------- grading

_NUMBER_RE = re.compile(
    r"(?<![\w.])(-?(?:\d{1,3}(?:[,_]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?))(?:\s*(thousand|million)\b)?",
    re.IGNORECASE)
_SCALE = {"thousand": 1e3, "million": 1e6}


def extract_numbers(text: str) -> list[float]:
    """1,234 / 1_234 / 12.5 and "<n> thousand" / "<n> million" (scaled)."""
    return [float(m.group(1).replace(",", "").replace("_", "")) * _SCALE.get((m.group(2) or "").lower(), 1)
            for m in _NUMBER_RE.finditer(text)]


def answer_matches(answer: str, expected: Any, tolerance: float = 0.0) -> tuple[bool, str]:
    if expected is None:
        return False, "expected value is NULL or the query returned no row"
    if isinstance(expected, bool) or not isinstance(expected, (int, float, Decimal)):
        # whole token only: "teams" must not match "teamsters" or "teams_pkey"
        ok = re.search(rf"(?<!\w){re.escape(str(expected))}(?!\w)", answer, re.IGNORECASE) is not None
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


def compute_truths(conn: psycopg.Connection, checks: list[dict[str, Any]]) -> dict[int, Any]:
    """Ground truth for each answer_matches check, by check position. Run after setup and
    before the agent starts, so nothing the agent does can change what it is graded against."""
    truths: dict[int, Any] = {}
    for i, check in enumerate(checks):
        if "answer_matches" in check:
            row = conn.execute(check["answer_matches"]["query"]).fetchone()
            truths[i] = row[0] if row else None
    return truths


def grade(conn: psycopg.Connection, checks: list[dict[str, Any]], parsed: Parsed,
          truths: dict[int, Any] | None = None) -> list[dict[str, Any]]:
    out = []
    for i, check in enumerate(checks):
        (kind, arg), = check.items()
        if kind == "tool_called":
            ok, why = was_called(parsed.tool_calls, arg), f"{arg} {'was' if was_called(parsed.tool_calls, arg) else 'was not'} called"
        elif kind == "tool_not_called":
            called = was_called(parsed.tool_calls, arg)
            ok, why = not called, f"{arg} {'was called' if called else 'was not called'}"
        elif kind == "index_exists":
            ok, why = index_exists(conn, arg["table"], list(arg["leading_columns"]))
        elif kind == "answer_matches":
            if truths is None or i not in truths:
                ok, why = False, "ground truth was not computed before the agent ran"
            else:
                ok, why = answer_matches(parsed.final_text, truths[i], float(arg.get("tolerance", 0)))
        else:
            ok, why = False, f"unknown check type {kind!r}"
        out.append({"check": kind, "passed": bool(ok), "reason": why})
    return out


# --------------------------------------------------------------------------- one trial

Runner = Callable[[list[str], Path, int], tuple[str, int | None, bool]]


@dataclass
class Session:
    parsed: Parsed
    transcript: str
    replies: list[str]
    unanswered_question: bool
    status: str  # ok | isolation_failed | claude_error
    problems: list[str]
    duration: float
    exit_code: int | None
    timed_out: bool


def run_session(task: Task, args: argparse.Namespace, work: Path, cfg: Path,
                runner: Runner | None = None, claude: str = "claude") -> Session:
    """The conversation: the prompt, then up to MAX_REPLIES canned replies resuming the session."""
    runner = runner or run_claude
    persist = bool(task.answers)
    cmd = build_command(task.prompt, args.model, cfg, claude, args.effort, persist=persist)
    parts: list[Parsed] = []
    outs: list[str] = []
    replies: list[str] = []
    problems: list[str] = []
    status = "ok"
    code: int | None = None
    timed_out = False
    started = time.perf_counter()
    while True:
        out, code, timed_out = runner(cmd, work, args.timeout)
        outs.append(out if out.endswith("\n") or not out else out + "\n")
        parsed = parse_stream(out)
        parts.append(parsed)
        if parsed.init is None:
            status = "claude_error"
            problems.append("no system/init event in the claude output")
        else:
            found = isolation_problems(parsed.init, args.toolset)
            if found and status == "ok":
                status = "isolation_failed"
            problems += found
        reply = match_answer(task.answers, parsed.final_text) if task.answers else None
        session_id = (parsed.result or {}).get("session_id") or (parsed.init or {}).get("session_id")
        if not reply or len(replies) >= MAX_REPLIES or timed_out or status == "claude_error" or not session_id:
            break
        replies.append(reply)
        cmd = build_command(reply, args.model, cfg, claude, args.effort, resume=session_id, persist=True)
    duration = time.perf_counter() - started
    last = parts[-1].final_text
    return Session(
        parsed=merge_parsed(parts), transcript="".join(outs), replies=replies,
        unanswered_question="?" in last and match_answer(task.answers, last) is None,
        status=status, problems=problems, duration=duration, exit_code=code, timed_out=timed_out)


def run_trial(task: Task, trial: int, args: argparse.Namespace, conn: psycopg.Connection,
              base: Baseline, run_dir: Path, runner: Runner | None = None) -> dict[str, Any]:
    reset_stats(conn)
    run_steps(conn, task.setup)
    truths = compute_truths(conn, task.checks)  # as admin, after setup, before the agent
    work, cfg = make_workdir(args.toolset)
    try:
        session = run_session(task, args, work, cfg, runner, shutil.which("claude") or "claude")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    (run_dir / "transcripts" / f"{task.id}-t{trial}.jsonl").write_text(session.transcript, encoding="utf-8")

    parsed = session.parsed
    checks = grade(conn, task.checks, parsed, truths)  # before any reset: the setup data must still be there
    timings = reset_database(conn, base, task.teardown, args.vacuum)
    verify_baseline(conn, base)

    res = parsed.result or {}
    forbids_apply = any(c.get("tool_not_called") == "apply_index" for c in task.checks)
    return {
        "task": task.id, "split": task.split, "trial": trial, "status": session.status,
        "isolation_problems": session.problems,
        "success": (session.status == "ok" and bool(checks) and all(c["passed"] for c in checks)
                    and not session.timed_out),
        "checks": checks,
        "tool_calls": parsed.tool_calls, "tool_call_count": sum(parsed.tool_calls.values()),
        "tool_errors": parsed.tool_errors, "turns": res.get("num_turns"),
        "duration_s": round(session.duration, 1), "tokens": parsed.usage,
        "cost_usd_list_estimate": res.get("total_cost_usd"),
        "skill_loaded": skill_was_loaded(parsed.skill_inputs),
        "replies": session.replies, "unanswered_question": session.unanswered_question,
        "ended_with_question": parsed.final_text.strip().endswith("?"),
        "unrequested_writes": forbids_apply and was_called(parsed.tool_calls, "apply_index"),
        "timed_out": session.timed_out, "exit_code": session.exit_code,
        "rate_limit": parsed.rate_limit,
        "reset_s": {k: round(v, 2) for k, v in timings.items()},
    }


# --------------------------------------------------------------------------- usage guard

def _local_time(ts: Any) -> str:
    return datetime.fromtimestamp(ts).astimezone().strftime("%Y-%m-%d %H:%M %Z") if ts else "unknown time"


def usage_stop_reason(info: dict[str, Any] | None, stop_5h: float, stop_7d: float, run: str) -> str | None:
    """Why the run should stop before the next trial, or None to go on."""
    if not info:
        return None
    wins = info.get("unifiedWindows") or {}
    resume = f"resume with: python scripts/eval.py ... --run {run}"
    if info.get("status") != "allowed":
        name = next((n for n, w in wins.items() if w.get("status") != "allowed"),
                    info.get("rateLimitType") or "unknown")
        w = wins.get(name) or {}
        util = f"{w['utilization']:.0%}" if "utilization" in w else "n/a"
        return (f"usage guard: status is {info.get('status')!r} on the {name} window (utilization {util}), "
                f"resets {_local_time(w.get('resetsAt') or info.get('resetsAt'))}; {resume}")
    for name, limit in (("five_hour", stop_5h), ("seven_day", stop_7d)):
        w = wins.get(name) or {}
        if w.get("utilization") is not None and w["utilization"] >= limit:
            return (f"usage guard: {name} window at {w['utilization']:.0%} (stop at {limit:.0%}), "
                    f"resets {_local_time(w.get('resetsAt'))}; {resume}")
    return None


# --------------------------------------------------------------------------- summary

def summarize(trials: list[dict[str, Any]]) -> dict[str, Any]:
    """Isolation failures and claude errors are counted apart and left out of the rates."""
    n = len(trials)
    if not n:
        return {"trials": 0}
    ok = [t for t in trials if t.get("status", "ok") == "ok"]
    m = len(ok)
    tok = sum(sum(t["tokens"].values()) for t in ok)
    return {
        "trials": n, "scored_trials": m,
        "isolation_failed": sum(t.get("status") == "isolation_failed" for t in trials),
        "claude_error": sum(t.get("status") == "claude_error" for t in trials),
        "success_rate": sum(t["success"] for t in ok) / m if m else None,
        "skill_loaded": sum(bool(t.get("skill_loaded")) for t in ok) / m if m else None,
        "mean_tool_calls": sum(t["tool_call_count"] for t in ok) / m if m else None,
        "mean_tokens": tok / m if m else None, "total_tokens": tok,
        "total_cost_usd_list_estimate": sum(t["cost_usd_list_estimate"] or 0 for t in trials),
        "tool_errors": sum(t["tool_errors"] for t in ok),
        "ended_with_question": sum(t["ended_with_question"] for t in ok),
        "unanswered_question": sum(bool(t.get("unanswered_question")) for t in ok),
        "unrequested_writes": sum(t["unrequested_writes"] for t in ok),
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
    verdict = r["status"].upper() if r.get("status", "ok") != "ok" else "PASS" if r["success"] else "FAIL"
    print(f"{label}: {verdict}  calls={r['tool_call_count']} "
          f"turns={r['turns']} {r['duration_s']}s", flush=True)
    if r["split"] != "heldout":
        for c in r["checks"]:
            print(f"    [{'x' if c['passed'] else ' '}] {c['check']}: {c['reason']}")
        for prob in r.get("isolation_problems") or []:
            print(f"    ! {prob}")


# --------------------------------------------------------------------------- main

def plan_lines(tasks: list[Task], args: argparse.Namespace) -> list[str]:
    cfg = Path("<tmp>/mcp.json")
    lines = [f"toolset={args.toolset} model={args.model} effort={args.effort} trials={args.trials} timeout={args.timeout}s "
             f"tasks={len(tasks)} ({sum(t.split == 'heldout' for t in tasks)} held out)"]
    for t in tasks:
        for n in range(1, args.trials + 1):
            if t.split == "heldout":
                lines.append(f"heldout trial {n}: claude -p <held-out prompt> ...")
                continue
            cmd = build_command(t.prompt, args.model, cfg, effort=args.effort, persist=bool(t.answers))
            lines.append(f"{t.id} t{n}: " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
    return lines


def trial_path(run_dir: Path, task: str, trial: int) -> Path:
    return run_dir / "trials" / f"{task}-t{trial}.json"


def write_atomic(path: Path, data: str) -> None:
    """Write then rename, so a crash never leaves a half-written file."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    os.replace(tmp, path)


def load_trials(run_dir: Path) -> list[dict[str, Any]]:
    trials = [json.loads(p.read_text(encoding="utf-8")) for p in (run_dir / "trials").glob("*.json")]
    return sorted(trials, key=lambda t: (t["task"], t["trial"]))


def write_results(run_dir: Path, args: argparse.Namespace) -> list[dict[str, Any]]:
    trials = load_trials(run_dir)
    write_atomic(run_dir / "results.json", json.dumps(
        {"toolset": args.toolset, "model": args.model, "effort": args.effort, "split": args.split,
         "trials": trials, "summary": build_summary(trials)}, indent=2))
    return trials


def run_loop(tasks: list[Task], args: argparse.Namespace, run_dir: Path,
             trial_fn: Callable[[Task, int], dict[str, Any]]) -> int:
    """Run the missing (task, trial) pairs; stop at --max-trials or when the usage guard trips."""
    (run_dir / "transcripts").mkdir(parents=True, exist_ok=True)
    (run_dir / "trials").mkdir(parents=True, exist_ok=True)
    plan = [(t, n) for t in tasks for n in range(1, args.trials + 1)]
    done = {(t["task"], t["trial"]) for t in load_trials(run_dir)}
    skipped = sum((t.id, n) in done for t, n in plan)
    print(f"skipping {skipped} already finished trial(s) of {len(plan)} planned in {run_dir}", flush=True)
    rate: dict[str, Any] | None = None
    new = 0
    for task, n in plan:
        if (task.id, n) in done:
            continue
        if args.max_trials is not None and new >= args.max_trials:
            print(f"stopping: --max-trials {args.max_trials} reached; rerun with --run {run_dir.name} to go on")
            break
        why = usage_stop_reason(rate, args.stop_at_5h, args.stop_at_7d, run_dir.name)
        if why:
            print(f"STOPPED CLEANLY: {why}")
            break
        r = trial_fn(task, n)
        new += 1
        rate = r.get("rate_limit") or rate
        write_atomic(trial_path(run_dir, task.id, n), json.dumps(r, indent=2))
        write_results(run_dir, args)
        print_trial_line(r)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--toolset", default="v1")
    p.add_argument("--split", choices=["dev", "heldout", "all"], default="dev")
    p.add_argument("--trials", type=int, default=1)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--effort", default=DEFAULT_EFFORT, help="passed to claude as --effort")
    p.add_argument("--tasks", help="comma-separated task ids")
    p.add_argument("--timeout", type=int, default=600, help="wall-clock seconds per claude invocation")
    p.add_argument("--run", help="run name (folder under runs/); rerun with it to resume")
    p.add_argument("--max-trials", type=int, help="stop after this many newly run trials")
    p.add_argument("--stop-at-5h", type=float, default=0.90, help="stop when 5-hour utilization reaches this")
    p.add_argument("--stop-at-7d", type=float, default=0.80, help="stop when 7-day utilization reaches this")
    p.add_argument("--vacuum", choices=["dirty", "all"], default="dirty",
                   help="which tables to VACUUM after each trial")
    p.add_argument("--dry-run", action="store_true", help="print the plan; run nothing, touch no database")
    args = p.parse_args(argv)

    tasks = load_tasks(args.split, args.tasks.split(",") if args.tasks else None)  # also validates
    if args.dry_run:
        print("\n".join(plan_lines(tasks, args)))
        return 0
    if not tasks:
        raise SystemExit("no tasks selected")
    if not (SKILLS_DIR / args.toolset).is_dir():
        raise SystemExit(f"no skill folder skills/{args.toolset}")
    if args.run and (not args.run.strip() or re.search(r"[\\/]", args.run) or args.run in (".", "..")):
        raise SystemExit("--run must be a plain folder name")

    run_dir = RUNS_DIR / (args.run or f"{datetime.now():%Y%m%d-%H%M%S}-{args.toolset}-{args.split}")
    with admin() as conn:
        base = capture_baseline(conn)
        reset_stats(conn)
        try:
            run_loop(tasks, args, run_dir, lambda task, n: run_trial(task, n, args, conn, base, run_dir))
        except BaselineError as e:
            print(f"STOPPED: {e}", file=sys.stderr)
            return 2
    trials = write_results(run_dir, args)
    print(json.dumps(build_summary(trials), indent=2))
    print(f"results: {run_dir / 'results.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
