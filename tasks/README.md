# Eval tasks

One YAML file per task. `dev/` is for iterating; `heldout/` is never read while tuning tools.

```yaml
id: slow-shiny-encounters          # unique, kebab-case
prompt: >                          # what the user says to the agent, verbatim
  The shiny tracker page is slow. Diagnose it and fix it.
setup:                             # optional fixtures, run as admin before the agent starts
  - sql: SELECT 1
teardown:                          # optional, run as postgres after the checks
  - sql: SELECT 1
checks:                            # all must pass for the task to count as a success
  - index_exists: {table: encounters, leading_columns: [is_shiny]}
  - tool_called: explain_query
  - tool_not_called: apply_index   # e.g. for read-only tasks
  - answer_matches: {query: "SELECT ...", tolerance: 0.05}
tags: [diagnose, index]            # for the failure breakdown in the report
```

Every check is computed from the database or the transcript. No LLM judge.

`setup` and `teardown` are lists of `- sql:` items. Each runs as `postgres`, in
autocommit, one statement per item. `teardown` runs after the checks and before
the runner's own reset. A setup that writes rows (INSERT, UPDATE, DELETE) needs a
teardown that restores them exactly. A setup that only creates indexes needs
none, because the runner drops every index that is not in the baseline.
