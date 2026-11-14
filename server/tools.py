"""Tool handlers: what each tool *does*.

Owns: behaviour. Each handler takes plain arguments, returns a JSON-serialisable
dict, and raises ToolError with an agent-readable message on failure.

Does NOT own: names, descriptions or input schemas. Those are the agent-facing
interface and live in server/toolsets/, versioned, because they are the thing
the eval loop changes between v1 and v2. Keeping behaviour here and interface
there means a description rewrite can never silently change behaviour.
"""

from __future__ import annotations

import datetime
import decimal
import math
import time
import uuid
from collections.abc import Iterator
from typing import Any

import psycopg

from server import config, db, sqlguard
from server.errors import ToolError

# --------------------------------------------------------------------------- describe_schema

_TABLES_SQL = """
SELECT c.relname, c.reltuples::bigint, pg_size_pretty(pg_total_relation_size(c.oid))
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
  AND (%(table)s::text IS NULL OR c.relname = %(table)s)
ORDER BY c.relname
"""

_COLUMNS_SQL = """
SELECT c.relname, a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') AND a.attnum > 0 AND NOT a.attisdropped
  AND (%(table)s::text IS NULL OR c.relname = %(table)s)
ORDER BY c.relname, a.attnum
"""

_INDEXES_SQL = """
SELECT t.relname, i.relname, pg_get_indexdef(i.oid), x.indisvalid, pg_size_pretty(pg_relation_size(i.oid))
FROM pg_index x
JOIN pg_class i ON i.oid = x.indexrelid
JOIN pg_class t ON t.oid = x.indrelid
JOIN pg_namespace n ON n.oid = t.relnamespace
WHERE n.nspname = 'public' AND (%(table)s::text IS NULL OR t.relname = %(table)s)
ORDER BY t.relname, i.relname
"""


def describe_schema(table: str | None = None) -> dict[str, Any]:
    """Tables, columns, row estimates, existing indexes. One table if given.

    Row counts are the planner's estimates (instant; exact right after ANALYZE,
    can drift after changes), so they are labelled `rows_estimate`.
    """
    if table is not None:
        table = table.strip().removeprefix("public.").strip('"')
    params = {"table": table}
    with db.read_only() as cur:
        tables = cur.execute(_TABLES_SQL, params).fetchall()
        if not tables:
            names = [r[0] for r in cur.execute(_TABLES_SQL, {"table": None}).fetchall()]
            raise ToolError(f"No table named {table!r}. Tables: {', '.join(names)}.")
        columns = cur.execute(_COLUMNS_SQL, params).fetchall()
        indexes = cur.execute(_INDEXES_SQL, params).fetchall()

    out = {
        name: {
            "name": name,
            "rows_estimate": rows if rows >= 0 else None,  # -1: never analyzed
            "size": size,
            "columns": [],
            "indexes": [],
        }
        for name, rows, size in tables
    }
    for tname, col, typ, notnull in columns:
        out[tname]["columns"].append(f"{col} {typ}" + (" not null" if notnull else ""))
    for tname, iname, definition, valid, size in indexes:
        out[tname]["indexes"].append({"name": iname, "definition": definition, "valid": valid, "size": size})
    return {"tables": list(out.values())}


# --------------------------------------------------------------------------- run_read_query

def _cut(s: str) -> str:
    limit = config.MAX_VALUE_CHARS
    return s if len(s) <= limit else f"{s[:limit]}… [cut: {len(s)} chars]"


def _jsonable(v: Any) -> Any:
    """A JSON-friendly version of one result value: ISO 8601 timestamps, decimals
    as numbers, long text cut to MAX_VALUE_CHARS."""
    if v is None or isinstance(v, (bool, int)):
        return v
    if isinstance(v, float):
        return v if math.isfinite(v) else str(v)
    if isinstance(v, decimal.Decimal):
        return float(v) if v.is_finite() else str(v)
    if isinstance(v, str):
        return _cut(v)
    if isinstance(v, (datetime.datetime, datetime.date, datetime.time)):
        return v.isoformat()
    if isinstance(v, (bytes, bytearray, memoryview)):
        return _cut("\\x" + bytes(v).hex())
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (datetime.timedelta, uuid.UUID)):
        return str(v)
    return _cut(str(v))


def run_read_query(sql: str) -> dict[str, Any]:
    """Run one read-only query; return columns, up to MAX_ROWS rows, and whether it was truncated.

    The query is wrapped as `SELECT * FROM (<query>) q LIMIT MAX_ROWS + 1`, so
    Postgres stops after the rows we show (psycopg would otherwise download the
    whole result first). One extra row tells us whether there were more. SHOW
    can't be wrapped and returns few rows, so it runs as is.
    """
    verdict = sqlguard.classify(sql)
    if verdict.kind == "create_index":
        raise ToolError("run_read_query only runs read-only queries. Use apply_index to create an index.")
    if verdict.kind != "read":
        raise ToolError(verdict.reason)

    limit = config.MAX_ROWS
    body = sqlguard.strip_terminator(sql)
    prefix = ""
    if sqlguard.leading_keyword(sql) != "show":
        # The newline keeps a trailing -- comment from swallowing the closing parenthesis.
        prefix = "SELECT * FROM (\n"
        body = f"{prefix}{body}\n) AS q LIMIT {limit + 1}"

    with db.read_only(position_offset=len(prefix)) as cur:
        started = time.perf_counter()
        cur.execute(body)
        rows = cur.fetchmany(limit + 1)
        elapsed_ms = (time.perf_counter() - started) * 1000
        columns = [d.name for d in cur.description or []]

    return {
        "columns": columns,
        "rows": [[_jsonable(v) for v in row] for row in rows[:limit]],
        "row_count": min(len(rows), limit),
        "truncated": len(rows) > limit,
        "elapsed_ms": round(elapsed_ms, 1),
    }


def _explain(body: str, options: str) -> str:
    """Run one EXPLAIN and return Postgres's text plan, unchanged."""
    # The newline keeps a trailing -- comment from swallowing anything after the query.
    prefix = f"EXPLAIN {options}\n"
    with db.read_only(position_offset=len(prefix)) as cur:
        cur.execute(f"{prefix}{body}")
        return "\n".join(row[0] for row in cur.fetchall())


def _explainable_body(sql: str, tool: str) -> str:
    """Check that `sql` is one read query EXPLAIN can explain, and return it without its
    terminator. Shared by explain_query and propose_index; `tool` names the caller in messages."""
    keyword = sqlguard.leading_keyword(sql)
    if keyword == "explain":
        raise ToolError(f"{tool} adds EXPLAIN itself. Send the query without the EXPLAIN keyword.")
    verdict = sqlguard.classify(sql)
    if verdict.kind == "create_index":
        raise ToolError(f"{tool} only explains read-only queries. Use apply_index to create an index.")
    if verdict.kind != "read":
        raise ToolError(verdict.reason)
    if keyword == "show":
        raise ToolError("EXPLAIN cannot explain a SHOW statement. Use run_read_query to run it.")
    return sqlguard.strip_terminator(sql)


def explain_query(sql: str) -> dict[str, Any]:
    """Return the raw text plan of EXPLAIN (ANALYZE, BUFFERS) for one read query.

    ANALYZE really runs the query; that is safe because db.read_only() is a
    read-only transaction that is always rolled back. If statement_timeout
    cancels it, the plan comes from plain EXPLAIN (estimates only, nothing runs)
    and a note says so. Output: {"plan", "analyzed"}, plus "note" on fallback.
    """
    body = _explainable_body(sql, "explain_query")
    started = time.perf_counter()
    try:
        return {"plan": _explain(body, "(ANALYZE, BUFFERS)"), "analyzed": True}
    except ToolError as err:
        # Fall back only for our own statement_timeout. A cancel from another
        # session (pg_cancel_backend) raises the same QueryCanceled, but always
        # sooner than the timeout, and someone wanted that query stopped. The
        # elapsed time tells them apart without matching (translated) message text.
        timed_out = (isinstance(err.__cause__, psycopg.errors.QueryCanceled)
                     and (time.perf_counter() - started) * 1000 >= config.STATEMENT_TIMEOUT_MS)
        if not timed_out:
            raise
    seconds = config.STATEMENT_TIMEOUT_MS / 1000
    try:
        plan = _explain(body, "")
    except ToolError as err:
        # The usual advice ("use EXPLAIN without ANALYZE") is what just failed.
        if isinstance(err.__cause__, psycopg.errors.QueryCanceled) and "statement_timeout" in str(err):
            raise ToolError(
                f"EXPLAIN ANALYZE took longer than {seconds:g} s (statement_timeout), and so did plain "
                "EXPLAIN, which only plans the query and runs nothing. Planning alone is that slow, so "
                "simplify the query (fewer joins or subqueries) and try again."
            ) from err.__cause__
        raise
    return {
        "plan": plan,
        "analyzed": False,
        "note": (f"EXPLAIN ANALYZE was cancelled after {seconds:g} s (statement_timeout), so this plan "
                 "has estimates only: no actual rows, times or buffers."),
    }


def _plan_nodes(node: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Every node of a JSON plan tree, parents before children."""
    yield node
    for child in node.get("Plans", ()):
        yield from _plan_nodes(child)


def _explain_json(cur: db.Cursor, body: str) -> dict[str, Any]:
    """The top node of a plain EXPLAIN (FORMAT JSON) plan."""
    cur.execute(f"EXPLAIN (FORMAT JSON)\n{body}")
    return cur.fetchone()[0][0]["Plan"]


def propose_index(sql: str, index_sql: str) -> dict[str, Any]:
    """Test the agent's own CREATE INDEX with hypopg: a hypothetical index, nothing is built.

    Returns the planner's cost before and after, whether the planner uses the index,
    its estimated size and the new plan. Plain EXPLAIN only: EXPLAIN ANALYZE ignores
    hypothetical indexes. hypopg accepts CONCURRENTLY, IF NOT EXISTS, a name, UNIQUE,
    WHERE and INCLUDE as they are (it makes up its own name), so index_sql is not rewritten.
    A hypothetical index belongs to the session, not the transaction, so it is reset here
    and again whenever db.py hands out a connection (DECISIONS D24).
    """
    body = _explainable_body(sql, "propose_index")
    verdict = sqlguard.classify(index_sql)
    if verdict.kind != "create_index":
        why = f" {verdict.reason}" if verdict.kind == "forbidden" else ""
        raise ToolError("propose_index needs one CREATE INDEX statement in index_sql, for example "
                        f"CREATE INDEX ON battles (winner_team_id).{why}")
    index_stmt = sqlguard.strip_terminator(index_sql)

    # Error positions in `sql` count from the start of the first EXPLAIN statement.
    offset = len("EXPLAIN (FORMAT JSON)\n")
    with db.read_only(position_offset=offset) as cur:
        try:
            before = _explain_json(cur, body)
            try:
                oid, name = cur.execute(
                    "SELECT indexrelid, indexname FROM hypopg_create_index(%s)", (index_stmt,)
                ).fetchone()
            except psycopg.Error as e:
                raise ToolError(f"Could not test index_sql: {db._tool_error(e)}") from e
            after = _explain_json(cur, body)
            used = any(n.get("Index Name") == name for n in _plan_nodes(after))
            cur.execute(f"EXPLAIN\n{body}")
            plan = "\n".join(row[0] for row in cur.fetchall())
            size = cur.execute("SELECT hypopg_relation_size(%s)", (oid,)).fetchone()[0]
        finally:
            try:
                cur.execute("SELECT hypopg_reset(), hypopg_unhide_all_indexes()")
            except psycopg.Error:
                pass  # the transaction already failed; db._begin_read resets on the next checkout

    cost_before, cost_after = float(before["Total Cost"]), float(after["Total Cost"])
    reduction = 100 * (1 - cost_after / cost_before) if cost_before else 0.0
    return {
        "index_sql": index_stmt,
        "used_by_planner": used,
        "cost_before": cost_before,
        "cost_after": cost_after,
        "cost_reduction_pct": round(reduction, 1),
        "estimated_size_mb": round(size / (1024 * 1024), 1),
        "plan": plan,
    }


# --------------------------------------------------------------------------- check_health

LONG_RUNNING_S = 5   # an active query older than this is "long running"
# Sizes come from pg_class.relpages, not pg_total_relation_size(): that function locks each
# table, and one ACCESS EXCLUSIVE lock (the very situation the report must show) would cancel the
# whole section. relpages is updated by VACUUM, ANALYZE and CREATE INDEX, so it is an estimate.
# The lock_timeout stays as a backstop, so no section can wait out the whole statement_timeout.
_HEALTH_LOCK_TIMEOUT_MS = 1000

# The tools' own sessions are left out of every activity section, so the report never shows itself.
_OURS = list(db.APP_NAMES.values())
_CLIENTS = "datname = current_database() AND backend_type = 'client backend' AND application_name <> ALL(%(ours)s)"

_CONNECTIONS_SQL = f"""
SELECT coalesce(state, 'unknown'), count(*) FROM pg_stat_activity
WHERE {_CLIENTS} GROUP BY 1 ORDER BY 1
"""

_LONG_RUNNING_SQL = f"""
SELECT pid, round(extract(epoch FROM now() - query_start)::numeric, 1), left(query, 200)
FROM pg_stat_activity
WHERE {_CLIENTS} AND state = 'active' AND now() - query_start > make_interval(secs => %(secs)s)
ORDER BY query_start
"""

_BLOCKING_SQL = f"""
SELECT pid, pg_blocking_pids(pid), round(extract(epoch FROM now() - query_start)::numeric, 1), left(query, 200)
FROM pg_stat_activity
WHERE {_CLIENTS} AND cardinality(pg_blocking_pids(pid)) > 0
ORDER BY query_start
"""

_CACHE_SQL = """
SELECT round(100.0 * blks_hit / nullif(blks_hit + blks_read, 0), 2)
FROM pg_stat_database WHERE datname = current_database()
"""

# reltuples, not n_live_tup: n_live_tup reads 0 after a restart (see describe_schema).
# Timestamps to whole seconds: microseconds cost tokens and tell a DBA nothing.
_HEALTH_TABLES_SQL = """
SELECT c.relname, c.reltuples::bigint, s.n_dead_tup,
       date_trunc('second', greatest(s.last_vacuum, s.last_autovacuum)),
       date_trunc('second', greatest(s.last_analyze, s.last_autoanalyze)),
       s.seq_scan, s.idx_scan, pg_size_pretty(p.pages * current_setting('block_size')::bigint)
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
CROSS JOIN LATERAL (
  SELECT c.relpages::bigint
         + coalesce((SELECT t.relpages FROM pg_class t WHERE t.oid = c.reltoastrelid), 0)
         + coalesce((SELECT sum(i.relpages) FROM pg_index x JOIN pg_class i ON i.oid = x.indexrelid
                     WHERE x.indrelid = c.oid), 0) AS pages
) p
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
ORDER BY p.pages DESC, c.relname
"""

_INVALID_INDEXES_SQL = """
SELECT i.relname, t.relname
FROM pg_index x
JOIN pg_class i ON i.oid = x.indexrelid
JOIN pg_class t ON t.oid = x.indrelid
JOIN pg_namespace n ON n.oid = t.relnamespace
WHERE n.nspname = 'public' AND NOT x.indisvalid
ORDER BY 2, 1
"""

# Primary keys and unique indexes enforce constraints, so "never scanned" is fine for them.
_UNUSED_INDEXES_SQL = """
SELECT s.indexrelname, s.relname, pg_size_pretty(i.relpages::bigint * current_setting('block_size')::bigint)
FROM pg_stat_user_indexes s
JOIN pg_index x ON x.indexrelid = s.indexrelid
JOIN pg_class i ON i.oid = s.indexrelid
WHERE s.schemaname = 'public' AND s.idx_scan = 0 AND NOT x.indisprimary AND NOT x.indisunique
ORDER BY i.relpages DESC, 1
"""

_STATS_SINCE_SQL = "SELECT date_trunc('second', stats_reset) FROM pg_stat_database WHERE datname = current_database()"

_TOP_QUERIES_SQL = """
SELECT left(query, 200), calls, round(total_exec_time)::bigint, round(mean_exec_time::numeric, 1), rows
FROM pg_stat_statements
WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
  AND userid NOT IN (SELECT oid FROM pg_roles WHERE rolname IN ('pokedex_agent', 'pokedex_dba'))
ORDER BY total_exec_time DESC LIMIT 5
"""

_REPLICATION_SQL = "SELECT client_addr::text, state, replay_lag::text FROM pg_stat_replication"


# When the database itself is gone, every section would wait out the pool timeout in turn.
_DATABASE_GONE = {db._UNREACHABLE, db._LOST}


def _health_section(sql: str, shape: Any, params: dict[str, Any] | None = None) -> Any:
    """Run one section in its own read-only block, so a failure hides only that section.
    If the database is unreachable, stop the whole report at once instead."""
    try:
        with db.read_only() as cur:
            cur.execute("SELECT set_config('lock_timeout', %s, true)", (f"{_HEALTH_LOCK_TIMEOUT_MS}ms",))
            rows = cur.execute(sql, {"ours": _OURS, **(params or {})}).fetchall()
        return _jsonable(shape(rows))
    except ToolError as err:
        if str(err) in _DATABASE_GONE:
            raise
        return {"error": str(err)}


def _replication(rows: list[tuple[Any, ...]]) -> Any:
    if not rows:
        return "no replica configured"
    return [{"client_addr": a, "state": st, "replay_lag": lag} for a, st, lag in rows]


def check_health() -> dict[str, Any]:
    """One-call health report: nine sections, each run on its own so one failure hides nothing else.

    Empty lists are information ("nothing blocking"), so they stay. `stats_since`
    says when the statistics began, because "unused index" only means unused since then.
    Replication is reported as 'no replica configured' and never invented.
    """
    return {
        "connections": _health_section(_CONNECTIONS_SQL, lambda rows: {state: n for state, n in rows}),
        "long_running": _health_section(
            _LONG_RUNNING_SQL,
            lambda rows: [{"pid": p, "seconds": sec, "query": q} for p, sec, q in rows],
            {"secs": LONG_RUNNING_S}),
        "blocking": _health_section(
            _BLOCKING_SQL,
            lambda rows: [{"pid": p, "blocked_by": by, "seconds_waiting": sec, "query": q}
                          for p, by, sec, q in rows]),
        "cache_hit_pct": _health_section(_CACHE_SQL, lambda rows: rows[0][0] if rows else None),
        "tables": _health_section(
            _HEALTH_TABLES_SQL,
            lambda rows: [{"name": n, "rows_estimate": r if r >= 0 else None, "dead_rows": dead,
                           "last_vacuum": v, "last_analyze": a, "seq_scan": seq, "idx_scan": idx, "size": size}
                          for n, r, dead, v, a, seq, idx, size in rows]),
        "invalid_indexes": _health_section(
            _INVALID_INDEXES_SQL, lambda rows: [{"name": i, "table": t} for i, t in rows]),
        "unused_indexes": _health_section(
            _UNUSED_INDEXES_SQL, lambda rows: [{"name": i, "table": t, "size": size} for i, t, size in rows]),
        "stats_since": _health_section(_STATS_SINCE_SQL, lambda rows: rows[0][0] if rows else None),
        "top_queries": _health_section(
            _TOP_QUERIES_SQL,
            lambda rows: [{"query": q, "calls": c, "total_ms": t, "mean_ms": m, "rows": r}
                          for q, c, t, m, r in rows]),
        "replication": _health_section(_REPLICATION_SQL, _replication),
    }


_INDEX_NAMES_SQL = """
SELECT t.oid IS NOT NULL,
       ARRAY(SELECT i.relname FROM pg_index x JOIN pg_class i ON i.oid = x.indexrelid WHERE x.indrelid = t.oid)
FROM (SELECT to_regclass(%s) AS oid) t
"""

_INDEX_INFO_SQL = """
SELECT pg_get_indexdef(i.oid), x.indisvalid, pg_size_pretty(pg_relation_size(i.oid))
FROM pg_index x JOIN pg_class i ON i.oid = x.indexrelid
WHERE x.indrelid = to_regclass(%s) AND i.relname = %s
"""


def _quoted(table: str) -> str:
    return ".".join('"' + part.replace('"', '""') + '"' for part in table.split("."))


def _index_names(table: str) -> set[str] | None:
    """The names of the table's indexes, or None if the table can't be found."""
    with db.read_only() as cur:
        found, names = cur.execute(_INDEX_NAMES_SQL, (_quoted(table),)).fetchone()
    return set(names) if found else None


def apply_index(index_sql: str, confirm: bool = False) -> dict[str, Any]:
    """The only write: build one index with CREATE INDEX CONCURRENTLY, through db.create_index().

    CONCURRENTLY is added when the agent left it out, so a build never blocks
    writes (DECISIONS A1). The new index is found by comparing the table's index
    names before and after, because the agent may omit the name.
    `confirm` is unused for now: v1 policy needs no confirmation; v2 may add a
    dry-run step that uses it.
    """
    verdict = sqlguard.classify(index_sql)
    if verdict.kind == "read":
        raise ToolError("apply_index only creates indexes. Use run_read_query for queries.")
    if verdict.kind != "create_index":
        raise ToolError(verdict.reason)
    assert verdict.table is not None

    sql = sqlguard.strip_terminator(index_sql)
    added = not verdict.concurrently
    if added:
        sql = sqlguard.add_concurrently(sql)
        again = sqlguard.classify(sql)
        if again.kind != "create_index" or not again.concurrently:
            raise ToolError("Could not add CONCURRENTLY to this statement. Send it with CONCURRENTLY "
                            "written out: CREATE INDEX CONCURRENTLY ... ON table (columns).")

    table = verdict.table
    before = _index_names(table)
    if before is None:
        # Checked before the build: afterwards we could not tell what was built.
        raise ToolError(f"Could not find the table {table}. Check the name with describe_schema. "
                        "Nothing was built.")
    built = db.create_index(sql)
    new = (_index_names(table) or set()) - before
    if len(new) > 1:
        raise ToolError(f"The index was built, but other indexes also appeared on {table} during the "
                        f"build: {', '.join(sorted(new))}. Check with describe_schema which one is yours.")
    if not new:
        return {
            "created": False,
            "table": table,
            "note": "Nothing was built because an index with that name already exists.",
        }
    (name,) = new
    with db.read_only() as cur:
        definition, valid, size = cur.execute(_INDEX_INFO_SQL, (_quoted(table), name)).fetchone()
    result: dict[str, Any] = {
        "created": True,
        "index": name,
        "table": table,
        "definition": definition,
        "valid": valid,
        "size": size,
        "elapsed_ms": built["elapsed_ms"],
        "concurrently_added": added,
    }
    if added:
        result["note"] = "CONCURRENTLY was added, so the build did not block writes to the table."
    return result
