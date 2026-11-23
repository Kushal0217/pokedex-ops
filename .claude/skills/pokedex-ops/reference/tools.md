# Tool reference

What each `pokedex-ops` tool returns, and its limits. Every read runs as a
read-only role, in a transaction that is always rolled back, with a 20 s
statement timeout.

## describe_schema(table?)

`{"tables": [{"name", "rows_estimate", "size", "columns", "indexes"}]}`.
`rows_estimate` is the planner's estimate (null if the table was never
analyzed). `columns` are strings such as `"trainer_id integer not null"`.
Each index has `name`, `definition`, `valid` and `size`. An unknown table name
gives an error that lists the real ones.

## run_read_query(sql)

`{"columns", "rows", "row_count", "truncated", "elapsed_ms"}`. At most 50
rows; `truncated: true` means there were more. Values longer than 200
characters are cut. Timestamps are ISO 8601. One statement per call.

## explain_query(sqls)

`{"results": [{"sql", "plan", "analyzed"}, ...]}`, one entry per query (1 to
5), in order: the text output of `EXPLAIN (ANALYZE, BUFFERS)`. If a query runs
longer than the timeout, its plan comes from plain EXPLAIN instead:
`analyzed: false`, a `note`, and estimates only. A query that fails gets
`{"sql", "error"}` and the others still run.

## propose_index(sql, index_sql)

`{"index_sql", "used_by_planner", "cost_before", "cost_after",
"cost_reduction_pct", "estimated_size_mb", "plan"}`. Costs are the
planner's estimates from plain EXPLAIN, in the planner's units, not
milliseconds. Nothing is built. `estimated_size_mb` is hypopg's estimate. In
the plan, the hypothetical index has a generated name such as
`<13630>btree_battles_winner_team_id`.

## check_health()

Ten keys: `connections` (count per state), `long_running` (active over 5 s),
`blocking` (waiting sessions and the pids that block them), `cache_hit_pct`,
`tables` (rows estimate, dead rows, last vacuum and analyze, sequential and
index scans, size), `invalid_indexes`, `unused_indexes` (never scanned;
primary keys and unique indexes are left out), `stats_since` (when those
counts began), `top_queries` (top 5 by total time) and `replication`. The
tools' own sessions and queries are left out. A section that fails shows
`{"error": ...}`.

## apply_index(index_sql, verify_sql?)

`{"created": true, "index", "table", "definition", "valid", "size",
"elapsed_ms", "concurrently_added"}`, plus a `note` when CONCURRENTLY was
added. With `verify_sql`, also `verify`: `{"index_used", "plan",
"analyzed"}` for that query after the build, or `{"error"}` if it failed (the
index is still built). With `IF NOT EXISTS` and a name that exists: `{"created": false,
"table", "note"}`. The build waits at most 5 s for a lock and runs at most
300 s. If a concurrent build fails, it can leave an INVALID index; the error
names it.
