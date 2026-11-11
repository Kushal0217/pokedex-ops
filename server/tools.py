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
from typing import Any

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


def explain_query(sql: str, analyze: bool = True) -> dict[str, Any]:
    """EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) inside a rolled-back read-only transaction.
    Returns total cost, execution time, and a compact plan summary (not the raw JSON)."""
    raise NotImplementedError


def propose_index(sql: str, index_sql: str | None = None) -> dict[str, Any]:
    """Estimate an index's benefit with hypopg (hypothetical index, nothing is built).
    If index_sql is omitted, derive candidates from the plan and rank them."""
    raise NotImplementedError


def check_health() -> dict[str, Any]:
    """Connections, locks/blocking, cache hit ratio, table bloat, long-running queries.
    Replication: reported as 'no replica configured', never faked."""
    raise NotImplementedError


def apply_index(index_sql: str, confirm: bool = False) -> dict[str, Any]:
    """The only write. CREATE INDEX only, via the write path.
    Whether `confirm` is required is a toolset policy (v1: no, v2: dry-run then confirm)."""
    raise NotImplementedError
