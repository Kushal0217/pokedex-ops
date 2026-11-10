"""Database access: the only module that opens connections.

Two paths, two roles, nothing else (see ARCHITECTURE.md, "Two connection paths"):

  read path   -> role pokedex_agent (SELECT only, default read-only)
                 every call: BEGIN READ ONLY; SET LOCAL statement_timeout; ...; ROLLBACK
  write path  -> role pokedex_dba (table owner), autocommit, used ONLY by apply_index,
                 because CREATE INDEX CONCURRENTLY cannot run inside a transaction.

Tools never build connections themselves; they ask this module.

Every execute on either path MUST pass prepare=True. Without it, psycopg 3 sends
parameterless SQL over the simple protocol, which runs "SELECT 1; DROP ..." as two
statements. A prepared statement is one statement, enforced by Postgres.
OneStatementCursor enforces that here, so no caller can forget it.

Each call opens a fresh connection and closes it afterwards. That costs a few
milliseconds against a local database, and in exchange no session state (SET,
temp tables, a half-finished transaction) can ever leak from one tool call into
the next.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg

from server import config

CONNECT_TIMEOUT_S = 5

# Shown in pg_stat_activity, so a health check can tell the tools' own sessions
# apart from the workload's.
READ_APP_NAME = "pokedex-ops:read"
WRITE_APP_NAME = "pokedex-ops:write"


class OneStatementCursor(psycopg.Cursor):
    """A cursor whose execute() always uses a server-side prepared statement.

    Postgres refuses to prepare a string holding more than one statement
    ("cannot insert multiple commands into a prepared statement"), so this
    turns "SELECT 1; DROP TABLE x" into an error instead of two statements.
    The caller's own prepare= argument is ignored on purpose.
    """

    def execute(self, query: Any, params: Any = None, *, prepare: bool | None = None,
                binary: bool | None = None) -> OneStatementCursor:
        return super().execute(query, params, prepare=True, binary=binary)


@contextmanager
def read_only() -> Iterator[psycopg.Cursor]:
    """Cursor inside a READ ONLY transaction that is always rolled back."""
    conn = psycopg.connect(
        config.AGENT_DSN,
        connect_timeout=CONNECT_TIMEOUT_S,
        application_name=READ_APP_NAME,
        cursor_factory=OneStatementCursor,
    )
    try:
        # With autocommit off, psycopg opens the transaction on the first
        # execute, and read_only makes that "BEGIN READ ONLY".
        conn.read_only = True
        with conn.cursor() as cur:
            # set_config(..., true) is SET LOCAL: it ends with the transaction.
            # Unlike SET, it takes a bound parameter, so no string formatting.
            cur.execute("SELECT set_config('statement_timeout', %s, true)",
                        (f"{config.STATEMENT_TIMEOUT_MS}ms",))
            yield cur
    finally:
        # Never commit: even if something slipped past every other layer,
        # its effects are thrown away here.
        if not conn.broken:
            conn.rollback()
        conn.close()


@contextmanager
def dba_autocommit() -> Iterator[psycopg.Cursor]:
    """Autocommit cursor as the table owner. For apply_index only."""
    conn = psycopg.connect(
        config.DBA_DSN,
        autocommit=True,
        connect_timeout=CONNECT_TIMEOUT_S,
        application_name=WRITE_APP_NAME,
        cursor_factory=OneStatementCursor,
    )
    try:
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.close()
