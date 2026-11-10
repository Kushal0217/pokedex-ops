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
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg


@contextmanager
def read_only() -> Iterator[psycopg.Cursor]:
    """Cursor inside a READ ONLY transaction that is always rolled back."""
    raise NotImplementedError


@contextmanager
def dba_autocommit() -> Iterator[psycopg.Cursor]:
    """Autocommit cursor as the table owner. For apply_index only."""
    raise NotImplementedError
