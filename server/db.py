"""Database access: the only module that opens connections.

Two paths, two roles, nothing else (see ARCHITECTURE.md, "Two connection paths"):

  read path   -> role pokedex_agent (SELECT only, default read-only)
                 every call: BEGIN READ ONLY; set statement_timeout locally; ...; ROLLBACK
  write path  -> role pokedex_dba (table owner), autocommit, used ONLY by apply_index,
                 because CREATE INDEX CONCURRENTLY cannot run inside a transaction.
                 It accepts one thing: a statement sqlguard classifies as CREATE INDEX.

Tools never build connections themselves; they ask this module.

Every execute on either path passes prepare=True. Without it, psycopg 3 sends
parameterless SQL over the simple protocol, which runs "SELECT 1; DROP ..." as two
statements. A prepared statement is one statement, enforced by Postgres. On the read
path, tools only ever get a `Cursor` wrapper that adds the flag itself.

Connections are persistent and pooled (docs/DECISIONS.md, D11): a pooled call costs
about 0.65 ms against 7.6 ms for a new connection. Pools open on first use, so the
MCP server starts even when the database is down. A connection that turns out to be
dead (the server restarted) is detected when the call starts, before any of the
caller's SQL has run, and the call retries once on a fresh connection. The index
build itself is never retried.
"""

from __future__ import annotations

import atexit
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg import errors as pgerr
from psycopg.pq import TransactionStatus
from psycopg_pool import ConnectionPool, PoolTimeout

from server import config, sqlguard
from server.errors import ToolError

_lock = threading.Lock()
_pools: dict[str, ConnectionPool] = {}

_UNREACHABLE = "The database is not reachable. Start it with `docker compose up -d`, then try again."
_LOST = ("Lost the connection to the database. Try again; if it keeps happening, "
         "check that the database is running (`docker compose ps`).")


# --------------------------------------------------------------------------- pools

def _pool(kind: str) -> ConnectionPool:
    """The read or write pool, created on first use."""
    with _lock:
        pool = _pools.get(kind)
        if pool is None:
            dsn, max_size = (
                (config.AGENT_DSN, config.READ_POOL_MAX) if kind == "read" else (config.DBA_DSN, 1)
            )
            pool = ConnectionPool(
                dsn, min_size=1, max_size=max_size, timeout=config.POOL_TIMEOUT_S,
                kwargs={"autocommit": True}, name=f"pokedex-{kind}", open=True,
            )
            _pools[kind] = pool
        return pool


def close() -> None:
    """Close both pools (server shutdown, eval teardown, tests). They reopen on next use."""
    with _lock:
        for pool in _pools.values():
            pool.close()
        _pools.clear()


# Without this, interpreter exit waits ~5 s for each pool thread that was never stopped.
atexit.register(close)


def _release(pool: ConnectionPool, conn: psycopg.Connection) -> None:
    """Return a connection, unless it is in a state the next caller must not inherit."""
    if not conn.closed and conn.info.transaction_status != TransactionStatus.IDLE:
        conn.close()  # the pool replaces closed connections
    pool.putconn(conn)


def _checkout(pool: ConnectionPool, setup: Callable[[psycopg.Connection], None]) -> psycopg.Connection:
    """Get a connection and run `setup` on it. `setup` is the first thing sent, so it
    doubles as the liveness check: if the connection turns out dead, nothing of the
    caller's has run yet, and it is safe to retry once on a fresh connection."""
    for attempt in (1, 2):
        try:
            conn = pool.getconn()
        except PoolTimeout as e:
            raise ToolError(_UNREACHABLE) from e
        try:
            setup(conn)
            return conn
        except psycopg.Error as e:
            broken = conn.broken
            _release(pool, conn)
            if not broken:
                raise _tool_error(e) from e
            if attempt == 2:
                raise ToolError(_LOST) from e
            pool.check()  # the server probably restarted: drop the other dead idle connections too
    raise AssertionError("unreachable")


# --------------------------------------------------------------------------- errors

def _tool_error(e: psycopg.Error, timeout_ms: int | None = None, position_offset: int = 0) -> ToolError:
    """Turn a database error into a message the agent can act on."""
    if isinstance(e, pgerr.QueryCanceled):
        limit = f" after {(timeout_ms or config.STATEMENT_TIMEOUT_MS) / 1000:g} s"
        return ToolError(
            f"The query was cancelled{limit} (statement_timeout). Narrow it with a WHERE clause "
            "or LIMIT, or look at the plan with EXPLAIN (without ANALYZE), which does not run it."
        )
    diag = e.diag
    primary = diag.message_primary or str(e).strip()
    if isinstance(e, pgerr.ReadOnlySqlTransaction):
        return ToolError(
            f"Refused: {primary}. Only read-only queries run here; the only permitted write "
            "is CREATE INDEX, through apply_index."
        )
    if isinstance(e, pgerr.InsufficientPrivilege):
        return ToolError(f"Permission denied: {primary}.")
    if e.sqlstate is None:  # no server error code: the connection itself failed
        return ToolError(_LOST)
    msg = primary
    if diag.statement_position:
        pos = int(diag.statement_position) - position_offset
        if pos > 0:  # an error inside a caller's wrapper, not the caller's own SQL, has no position
            msg += f" (at character {pos})"
    if diag.message_detail:
        msg += f". Detail: {diag.message_detail}"
    if diag.message_hint:
        msg += f". Hint: {diag.message_hint}"
    return ToolError(msg)


# --------------------------------------------------------------------------- read path

class Cursor:
    """The only cursor tools get on the read path. Every execute is a server-side
    prepared statement, so Postgres itself refuses more than one statement."""

    __slots__ = ("_cur",)

    def __init__(self, cur: psycopg.Cursor) -> None:
        self._cur = cur

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> Cursor:
        self._cur.execute(sql, params, prepare=True)
        return self

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._cur.fetchone()

    def fetchmany(self, size: int) -> list[tuple[Any, ...]]:
        return self._cur.fetchmany(size)

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._cur.fetchall()

    @property
    def description(self) -> Any:
        return self._cur.description

    @property
    def rowcount(self) -> int:
        return self._cur.rowcount


def _begin_read(conn: psycopg.Connection) -> None:
    conn.execute("BEGIN READ ONLY", prepare=True)
    conn.execute("SELECT set_config('statement_timeout', %s, true)",
                 (f"{config.STATEMENT_TIMEOUT_MS}ms",), prepare=True)


@contextmanager
def read_only(position_offset: int = 0) -> Iterator[Cursor]:
    """Cursor inside a READ ONLY transaction that is always rolled back.

    Database errors raised inside the block come out as ToolError with an
    agent-readable message. `position_offset`: characters a caller added in front
    of the agent's SQL, subtracted from error positions so they point into the
    agent's own text.
    """
    pool = _pool("read")
    conn = _checkout(pool, _begin_read)
    try:
        with conn.cursor() as cur:
            try:
                yield Cursor(cur)
            except psycopg.Error as e:
                raise _tool_error(e, position_offset=position_offset) from e
    finally:
        if not conn.broken:
            try:
                conn.execute("ROLLBACK", prepare=True)
            except psycopg.Error:
                conn.close()
        _release(pool, conn)


# --------------------------------------------------------------------------- write path

def _quote_table(table: str) -> str:
    return ".".join('"' + part.replace('"', '""') + '"' for part in table.split("."))


def _invalid_indexes(conn: psycopg.Connection, table: str) -> list[str]:
    """Indexes on `table` left INVALID, e.g. by a failed CREATE INDEX CONCURRENTLY."""
    try:
        rows = conn.execute(
            "SELECT indexrelid::regclass::text FROM pg_index "
            "WHERE indrelid = to_regclass(%s) AND NOT indisvalid ORDER BY 1",
            (_quote_table(table),), prepare=True,
        ).fetchall()
        return [r[0] for r in rows]
    except psycopg.Error:
        return []


def create_index(sql: str) -> dict[str, Any]:
    """Run one CREATE INDEX as the table owner. The only write this module allows.

    The statement is classified again here, whatever the caller checked, because the
    owner role could do far more than build an index. The build gets its own,
    longer statement_timeout and a short lock_timeout, so it never sits queued
    behind other sessions' locks. It is never retried: a cut-off build may or may
    not have finished, and CONCURRENTLY can leave an INVALID index behind.
    """
    verdict = sqlguard.classify(sql)
    if verdict.kind != "create_index":
        raise ToolError(verdict.reason or "Only a CREATE INDEX statement can be applied.")
    assert verdict.table is not None

    def setup(conn: psycopg.Connection) -> None:
        conn.execute(
            "SELECT set_config('statement_timeout', %s, false), set_config('lock_timeout', %s, false)",
            (f"{config.WRITE_STATEMENT_TIMEOUT_MS}ms", f"{config.WRITE_LOCK_TIMEOUT_MS}ms"),
            prepare=True,
        )

    pool = _pool("write")
    conn = _checkout(pool, setup)
    try:
        started = time.monotonic()
        try:
            conn.execute(sql, prepare=True)
        except psycopg.Error as e:
            raise _write_error(e, conn, verdict) from e
        return {
            "table": verdict.table,
            "concurrently": verdict.concurrently,
            "elapsed_ms": round((time.monotonic() - started) * 1000),
        }
    finally:
        _release(pool, conn)


def _write_error(e: psycopg.Error, conn: psycopg.Connection, verdict: sqlguard.Verdict) -> ToolError:
    table = verdict.table or "the table"
    if conn.broken:
        return ToolError(
            "Lost the connection to the database during CREATE INDEX, so it is not known whether "
            f"the index was built. Check the indexes on {table} with describe_schema before trying again."
        )
    if isinstance(e, pgerr.LockNotAvailable):
        msg = (f"Could not get a lock on {table} within {config.WRITE_LOCK_TIMEOUT_MS / 1000:g} s: "
               "another session holds a conflicting lock. Look for blocking sessions with "
               "check_health, then try again.")
    elif isinstance(e, pgerr.QueryCanceled):
        msg = (f"The index build exceeded {config.WRITE_STATEMENT_TIMEOUT_MS / 1000:g} s "
               "(statement_timeout) and was cancelled.")
    else:
        msg = str(_tool_error(e))
    invalid = _invalid_indexes(conn, table) if verdict.concurrently else []
    if invalid:
        msg += (f" The failed build left INVALID index(es) on {table}: {', '.join(invalid)}. "
                "They are not used by queries but still slow down writes. Dropping them needs "
                "a human; it cannot be done through these tools.")
    else:
        msg += " Nothing was built."
    return ToolError(msg)
