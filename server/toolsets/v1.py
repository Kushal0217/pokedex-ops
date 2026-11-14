"""Toolset v1: the prototype. Descriptions are deliberately the first, plain draft.

Do not tune these against eval results. Improvements go into v2.
"""

from __future__ import annotations

from server import tools
from server.toolsets import Toolset, ToolSpec

_SQL = {"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]}

TOOLSET = Toolset(
    version="v1",
    policy={"apply_index_requires_confirm": False},
    tools=[
        ToolSpec(
            "describe_schema",
            "List the tables of the Pokédex database with their columns, estimated row counts, "
            "sizes and existing indexes. Pass `table` to describe one table only.",
            {"type": "object", "properties": {"table": {"type": "string"}}},
            tools.describe_schema,
        ),
        ToolSpec(
            "run_read_query",
            "Run one read-only SQL query (SELECT, WITH, VALUES, TABLE or SHOW) and return its "
            "columns and up to 50 rows. Statements that change data or schema are refused.",
            _SQL,
            tools.run_read_query,
        ),
        ToolSpec(
            "explain_query",
            "Show the execution plan of one read-only query: PostgreSQL's EXPLAIN (ANALYZE, BUFFERS) "
            "output as text. The query really runs, inside a transaction that is rolled back. "
            "Send the query without the EXPLAIN keyword.",
            _SQL,
            tools.explain_query,
        ),
        ToolSpec(
            "propose_index",
            "Test a CREATE INDEX statement against a query without building it, using a hypothetical "
            "index (hypopg). Returns the planner's estimated cost before and after, whether the "
            "planner would use the index, an estimated size, and the new plan.",
            {"type": "object",
             "properties": {"sql": {"type": "string"}, "index_sql": {"type": "string"}},
             "required": ["sql", "index_sql"]},
            tools.propose_index,
        ),
        ToolSpec(
            "check_health",
            "Report the database's health in one call: connections, long-running queries, blocked "
            "sessions, cache hit ratio, per-table statistics, invalid and unused indexes, the top "
            "queries by total time, and replication.",
            {"type": "object", "properties": {}},
            tools.check_health,
        ),
        ToolSpec(
            "apply_index",
            "Build one index. Takes one CREATE INDEX statement; the index is always built "
            "CONCURRENTLY, so writes to the table are not blocked. This is the only change these "
            "tools can make to the database.",
            {"type": "object", "properties": {"index_sql": {"type": "string"}}, "required": ["index_sql"]},
            tools.apply_index,
        ),
    ],
)
