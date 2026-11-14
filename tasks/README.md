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

`answers` (optional) scripts replies for when the agent asks a question:

```yaml
answers:
  - when_all: [index, go ahead]      # every word must appear in the agent's last message (any case)
    reply: Yes, go ahead and build it.
```

When a `claude -p` session ends, the runner checks the agent's final message
against each entry in order. The first entry whose `when_all` words all appear
is sent back in the same session (`--resume`), at most 3 times per trial. No
match ends the trial. A final message with a `?` that no entry answered is
recorded as `unanswered_question`.

How `answer_matches` is graded:
- **When the truth is computed.** The query runs as `postgres` after `setup`
  and before the agent starts, so nothing the agent does can change it.
- **Numbers.** The answer passes if any number in the agent's final message
  is within `tolerance` (relative; default 0, exact). `1,234`, `1_234`,
  decimals, and `12 thousand` / `1.5 million` are understood.
- **Text** (a table, index, user or column name). The value must appear as a
  whole word, case-insensitive: `teams` does not match `teams_pkey` or
  `teamsters`.

The runner validates every task file before it runs anything
(`python scripts/eval.py --split <split> --dry-run`). Unknown keys or check
types, an `id` that differs from the file name, a malformed `answers` entry,
or a writing `setup` without a `teardown` stop it with the file name and the
reason. For held-out files the message names only the file, never its content.
