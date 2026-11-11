"""Tool handlers: what each tool *does*.

Owns: behaviour. Each handler takes plain arguments, returns a JSON-serialisable
dict, and raises ToolError with an agent-readable message on failure.

Does NOT own: names, descriptions or input schemas. Those are the agent-facing
interface and live in server/toolsets/, versioned, because they are the thing
the eval loop changes between v1 and v2. Keeping behaviour here and interface
there means a description rewrite can never silently change behaviour.
"""

from __future__ import annotations

from typing import Any

from server.errors import ToolError  # noqa: F401  (re-exported: handlers raise it)


def describe_schema(table: str | None = None) -> dict[str, Any]:
    """Tables, columns, row estimates, existing indexes. One table if given."""
    raise NotImplementedError


def run_read_query(sql: str) -> dict[str, Any]:
    """Run one read-only query; return columns, up to MAX_ROWS rows, and whether it was truncated."""
    raise NotImplementedError


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
