"""Toolset v2: written from the v1 baseline transcripts (DECISIONS D32).

v1 passed every task, so v2 targets effort rather than success: fewer round
trips for the same result. Tool names are unchanged, so task checks still apply.
- explain_query takes a list of queries (v1 needed one call per query).
- apply_index can verify the build itself (v1 always needed one more explain_query).
- Descriptions say when a call can be skipped.
"""

from __future__ import annotations

from server import tools
from server.toolsets import Toolset, ToolSpec

TOOLSET = Toolset(
    version="v2",
    policy={"apply_index_requires_confirm": False},
    tools=[
        ToolSpec(
            "describe_schema",
            "List tables with their columns, estimated row counts, sizes and existing indexes. "
            "Pass `table` whenever you know which table matters: the whole database is a long "
            "answer. Skip this call when the question already names the tables and columns you need.",
            {"type": "object", "properties": {"table": {"type": "string"}}},
            tools.describe_schema,
        ),
        ToolSpec(
            "run_read_query",
            "Run one read-only SQL query (SELECT, WITH, VALUES, TABLE or SHOW) and return its "
            "columns and up to 50 rows. Statements that change data or schema are refused. For a "
            "question about the data (a count, a lookup), this one call is usually all you need.",
            {"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]},
            tools.run_read_query,
        ),
        ToolSpec(
            "explain_query",
            "Show the execution plans of 1 to 5 read-only queries in one call: PostgreSQL's "
            "EXPLAIN (ANALYZE, BUFFERS) text for each. The queries really run, inside a transaction "
            "that is rolled back. Send every query you want to compare in `sqls` at once, without the "
            "EXPLAIN keyword. A query that fails gets an `error` and the others still run.",
            {"type": "object",
             "properties": {"sqls": {"type": "array", "items": {"type": "string"},
                                     "minItems": 1, "maxItems": 5}},
             "required": ["sqls"]},
            tools.explain_queries,
        ),
        ToolSpec(
            "propose_index",
            "Test a CREATE INDEX statement against a query without building it, using a hypothetical "
            "index (hypopg). Returns the planner's estimated cost before and after, whether the "
            "planner would use the index, an estimated size, and the new plan. If it is not used or "
            "the cost barely drops, an index won't help this query as written.",
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
            "CONCURRENTLY, so writes are not blocked. This is the only change these tools can make. "
            "Pass the slow query as `verify_sql` to get its new plan back and `index_used`, so no "
            "separate explain_query is needed afterwards.",
            {"type": "object",
             "properties": {"index_sql": {"type": "string"}, "verify_sql": {"type": "string"}},
             "required": ["index_sql"]},
            tools.apply_index,
        ),
    ],
)
