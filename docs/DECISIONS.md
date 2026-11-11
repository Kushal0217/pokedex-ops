# Decisions

Choices made while building, and why. ARCHITECTURE.md holds the original design
decisions (1 to 7); this log records what was decided after that, newest last.
Add an entry whenever a choice would otherwise be hard to reconstruct from the
code: what was decided, why, what else was considered, and what it costs.

---

## D1. `prepare=True` on every execute (2026-11-09)

**Decision.** `db.py` passes `prepare=True` on every execute, on both paths.

**Why.** Checked against the live container: psycopg 3 sends a query with no
parameters over the simple protocol, which runs `SELECT 1; SELECT 2` as two
statements. A server-side prepared statement is one statement, enforced by
Postgres itself. This is guardrail layer 2.

**Also checked.** The privilege layer alone already blocks INSERT, CREATE INDEX
and DROP for `pokedex_agent`, even with read-only switched off.

## D2. How `sqlguard` classifies SQL (2026-11-10, PR #1)

**Decision.** A small hand-written lexer drops comments (including nested
`/* */`) and treats string, escape-string (`E'...'`), dollar-quoted and
quoted-identifier bodies as opaque. Statements are split on the remaining `;`
and classified as read, create_index or forbidden.

**Why.** Keywords and `;` inside quotes or comments must not count, in either
direction: `SELECT 'DROP TABLE x'` is a read, and `SELECT 1 -- ;` is one
statement. A full SQL parser would be a large dependency for layer 1 of 4.

**Details worth knowing.**
- **`EXPLAIN` is refused,** with a pointer to `explain_query`, because
  `EXPLAIN ANALYZE` really executes its query.
- **Write keywords are matched anywhere in a read.** That also catches writes
  hidden in `WITH` clauses. The cost: an unquoted column literally named
  `update` is refused. Accepted, because it's rare and quoting the name avoids it.
- **Side-effecting functions are a deny-list:** `nextval`, `setval`,
  `set_config`, `pg_terminate_backend`, advisory locks, `lo_*`, `dblink*`, and
  others. A deny-list can miss one; layers 2 to 4 are the backstop.
- **`CREATE INDEX` returns the table as written,** schema-qualified if given,
  with quoted names keeping their case.

## D3. The MCP server advertises the toolset's schema (2026-11-10, PR #2)

**Decision.** `build()` registers each handler but replaces the input schema
inferred from its Python signature with the schema in `toolsets/vN.py`.

**Why.** The toolset is the versioned interface the eval measures (ARCHITECTURE
decision 1). The agent should see exactly what v1 or v2 defines, not an
accident of a handler's signature.

## D4. Launching the MCP server on every platform (2026-11-10, PRs #2 and #3)

**Decision.** `.mcp.json` runs `${POKEDEX_PYTHON:-.venv/bin/python}`. Windows
sets `POKEDEX_PYTHON` once with `setx` (README).

**Why.** The original `.venv/Scripts/python.exe` only exists on Windows, so the
server failed on Linux, macOS and cloud sessions.

**Considered.** A launcher script that finds the venv itself. Rejected as more
moving parts than one environment variable.

## D5. Docker in the cloud, with an HTTPS mode for apt (2026-11-10, PR #5)

**Decision.** Cloud sessions run the same Docker image as the laptop. The
Dockerfile gets an opt-in `APT_HTTPS=1` mode, turned on by
`scripts/build_db_image.sh`, which switches apt to `https://` and points it at
the proxy's CA certificate for that one build step.

**Why.** One database setup everywhere. Plans and costs must match between
machines, and a second install path would drift.

**Considered.**
- **Installing Postgres directly in the container, without Docker.** Likely to
  work, but it means a second setup to keep in sync, and the container ships
  Postgres 16, not 17.
- **A separate cloud-only Dockerfile.** Same drift problem.

**Costs.**
- **The Dockerfile is more complex** for the sake of one environment.
- **It needs BuildKit,** because of `RUN --mount`. Current Docker and
  `docker compose` use BuildKit by default.
- **The Docker service doesn't start by itself** in a new cloud session; it has
  to be started by hand (see CLAUDE.md). It was left out of the environment's
  setup script because that would run a background service in every session.

## D6. A separate cloud environment for this repo (2026-11-10)

**Decision.** Cloud sessions for this repo use a personal environment named
`pokedex-ops`, not the shared Default. It allows three extra hosts:
`apt.postgresql.org` and `deb.debian.org` (the image build) and `pokeapi.co`
(the snapshot fetch). This is configured in claude.ai, not in the repo.

**Why.** The Default environment applies to every repository, and these hosts
are only needed here. Each host was added after the proxy actually refused it.

## D7. Fetch the PokeAPI snapshot once and commit it (2026-11-10, PR #6)

**Decision.** The snapshot was fetched once, in the cloud, and committed.
Every machine loads that file. `seed.py --refresh` re-fetches it, and should
be used only as a deliberate data update, committed in its own PR.

**Why.** The snapshot is the eval's ground truth. PokeAPI changes over time,
so two separate fetches could differ and make results incomparable.

**What the snapshot contains.**
- **Pokémon:** the default form of each species in generations 1 to 9, 1,025
  in all. Alternate forms are excluded, since the tables are keyed by Pokémon id.
- **Moves:** only those at least one of those Pokémon learns, 797 of PokeAPI's 937.
- **One row per (Pokémon, move, learn method),** taken from the most recently
  *released* version group, ranked by PokeAPI's `order`. PokeAPI lists a move
  once per game version, and the schema's primary key allows one row. (Until
  2026-11-11 this ranked by id, which was wrong; see D17.)
- **Byte-reproducible output:** sorted keys, no whitespace, gzip mtime 0. A
  re-fetch that changes nothing produces an identical file.

## D8. The seed runs as `pokedex_dba` (2026-11-10, PR #6)

**Decision.** `seed.py` creates and loads every table as `pokedex_dba`, not the
superuser.

**Why.** Only a table's owner may `CREATE INDEX`, and `apply_index` connects as
`pokedex_dba`. Tables created by that role also get SELECT granted to
`pokedex_agent` automatically, through the default privileges in
`docker/init/01-setup.sql`.

## D9. Where work runs (2026-11-10)

**Decision.**
- **Cloud sessions are for development:** code, tests, database checks.
- **The laptop is for the real eval runs:** the v1 baseline and v2.

**Why.**
- **The database persists on the laptop.** A cloud container is wiped when
  it's reclaimed, though rebuilding takes about 31 seconds at full scale and
  the result is identical.
- **The eval makes many Claude API calls,** so it's better run where it can be
  watched and stopped.
- **Eval results must be kept:** they go in `runs/` and get copied out or
  committed.

**Scale.** Development was first planned at `--scale 0.1` out of concern for
disk space. Measured: full scale is a 1.0 GB database built in 31 seconds, so
the cloud can use `--scale 1.0` too, and `0.1` remains an option for speed.

## D10. Workflow (2026-11-10)

- **One branch per piece of work,** made from `main`. Never reuse a merged PR's branch.
- **Claude announces code changes before making them,** so the model can be
  switched first (Opus for heavy work, Sonnet for routine).
- **PRs are merged only when asked,** and only after CI is green.
- **Progress and decisions are recorded** in `docs/PROGRESS.md` and
  `docs/DECISIONS.md`, in the same PR as the work.

## D11. Persistent, pooled connections (2026-11-11)

**Decision.** `db.py` keeps connections open in two pools (`psycopg_pool`):
- **reads:** up to 4 connections, so parallel tool calls don't wait for each other;
- **writes:** 1 connection, so index builds run one at a time.

The pools open on the first tool call.

**Why.** Speed is the priority. Measured on localhost: a pooled call costs
0.65 ms, against 7.6 ms for a new connection each time. Opening on first use
keeps the MCP server starting even when the database is down; the tool then
says "start it with `docker compose up -d`" instead of the server failing.

**Considered.** A new connection per call: simpler and fully isolated, but
about 12 times slower per call.

**Handling.** These are the costs we chose to take on:
- **Dead connections** (the server restarted) are found by the first
  statement of a call, which is the call's own setup (`BEGIN READ ONLY`, or
  setting the write timeouts), so there's no separate ping. Nothing of the
  caller's has run at that point, so the call retries once on a fresh
  connection, after dropping the pool's other dead idle connections. A
  connection that dies mid-query is reported, not retried.
- **The index build itself is never retried.** A cut-off build may or may not
  have finished. Only the setup step before it is retried.
- **No state leaks between calls.** Every read rolls back, which also undoes
  any settings changed during it. A connection returned mid-transaction or in
  an error state is closed instead of reused. Tested in `tests/test_db.py`.
- **`prepare=True` can't be forgotten.** Tools get a `Cursor` wrapper that
  adds it, never the raw psycopg cursor.

**Also checked.** `SHOW`, `set_config` and `CREATE INDEX CONCURRENTLY` all
work as prepared statements, and a multi-statement string is refused with
"cannot insert multiple commands into a prepared statement".

## D12. A narrow write path (2026-11-11)

**Decision.** The scaffold's general `dba_autocommit()` cursor is replaced by
`db.create_index(sql)`. It classifies the statement again with `sqlguard`,
refuses anything that isn't a single CREATE INDEX, and only then runs it.

**Why.** The write role owns every table and could DROP or TRUNCATE them. A
general-purpose cursor on it would rely on every caller checking first. With
this, the only write is checked in two places (`apply_index` and `db.py`).

**Timeouts.** A write gets its own `statement_timeout` of 5 minutes, since
builds on millions of rows take a while, and a `lock_timeout` of 5 seconds, so
a build never queues behind other sessions' locks (which would also block
everyone queued behind it).

**Failures are reported precisely.** A failed `CREATE INDEX CONCURRENTLY` can
leave an INVALID index behind. `create_index` names any it finds and says that
dropping them needs a human, because the agent cannot drop anything. Otherwise
it says nothing was built.

## D13. Database tests run against the dev database (2026-11-11)

**Decision.** Tests that need Postgres are marked `@pytest.mark.db` and run
against the local database from `docker compose`. `tests/conftest.py` skips
them, with a reason, when it isn't reachable. Write tests use a scratch table
(`zz_pytest_scratch`) that they create and drop. CI still runs
`pytest -m "not db"`.

**CI.** They run there too since PR #10 (D15).

**Small change alongside.** `ToolError` moved to `server/errors.py`, because
`db.py` raises it and can't import `tools.py`, which imports `db.py`.
`tools.ToolError` still works.

## D14. Cloud sessions stop background processes between turns (2026-11-11)

**Observed.** Between turns, while the session is idle, every process in the
cloud container stops (Docker, containerd, Postgres), but files survive: a
leftover `docker.pid` remained with no processes running. Postgres then runs
crash recovery when restarted, which has always come back clean.

**Consequence.**
- **Restart Docker and the database at the start of any turn that needs
  them.** The commands are in CLAUDE.md.
- **Docker can take more than 3 seconds to start,** so wait for `docker info`
  to succeed rather than sleeping for a fixed time.
- **The pool's retry (D11) covers the same event** from the application's side.

## D15. Database tests run in CI, against an image built every run (2026-11-11)

**Decision.** CI has two jobs:
- **`test`:** the fast job without a database, as before.
- **`db-test`:** builds the image with plain `docker compose build`, starts
  it, seeds at `--scale 0.1`, and runs `pytest -m db`.

The image is built fresh on every run, with no caching.

**Why.** The database tests are the guardrail tests (layers 2 to 4) and the
write-path tests, so they should run on every PR. Building fresh costs a
minute or two, but a cached image could hide a broken Dockerfile. It also
exercises the plain build without a proxy, which until now had never been run
outside the cloud (open item since PR #5).

**Considered.** Caching the image between runs: faster, but more
configuration, and a stale cache can mask Dockerfile breakage.

**Guard.** The job sets `POKEDEX_REQUIRE_DB=1`. Without it, `conftest.py`
would *skip* the database tests when Postgres is unreachable, and a broken
setup would show as a green run. With it, an unreachable database stops
pytest with exit code 1. Locally, without the variable, they're still skipped.

**Verified before pushing.**
- **The CI steps:** run in the cloud against a fresh volume (0 tables at
  start). The seed at scale 0.1 took 4.4 s, and all 22 database tests passed.
- **The guard:** with `POKEDEX_REQUIRE_DB=1` and no database, pytest exits 1.
- **Not reproducible here:** the plain build without a proxy. CI is the test
  for it.

## D16. What `describe_schema` and `run_read_query` return (2026-11-11)

**Decided by the user,** from options measured on the full-scale database
(tokens are estimated as characters divided by 4).

**`describe_schema(table=None)`**
- **S1. With no table named, it returns every table in full** (about 1,100
  tokens), not an overview (about 230 tokens) followed by a call per table
  (about 90 each). One call, which suits the speed priority.
- **S2. Row counts are the planner's estimates,** labelled `rows_estimate`.
  They're instant, and exact right after the seed's ANALYZE. An exact
  `count(*)` takes seconds on the 5M-row tables.
- **S3. Each index has its name, definition, `valid` flag and size.** The
  `valid` flag is there so the agent can see the INVALID indexes a failed
  concurrent build leaves (D12). Usage counts belong to `check_health`.
- **S4. No column statistics.** Those are `explain_query`'s and
  `propose_index`'s job.

**Format details** (not separate decisions):
- **Columns are compact strings,** such as `"turns integer not null"`.
- **The result is always `{"tables": [...]}`,** even for one table.
- **Names:** `public.` prefixes and quotes are accepted, and an unknown name
  lists the real tables.

**`run_read_query(sql)`**
- **R1. Column names once, then rows as lists.** For 50 rows of `battles`
  that's about 1,035 tokens, against about 2,110 for a `{column: value}`
  object per row.
- **R2. A fixed limit of `MAX_ROWS` (50) with a `truncated` flag,** found by
  fetching one extra row. There's no `limit` parameter in v1, and no total
  count, which would mean running the query twice.
- **R3. Values over 200 characters are cut** (`MAX_VALUE_CHARS`), with a
  marker like `… [cut: 300 chars]`.
- **R4. Timestamps are ISO 8601 strings,** and decimals are JSON numbers
  (`round(avg(turns), 2)` gives `32.48`).
- **R5. `elapsed_ms` is included.**

Output: `{"columns", "rows", "row_count", "truncated", "elapsed_ms"}`.

**How the row limit is enforced.** psycopg's normal cursor downloads a
query's whole result before returning anything, so `SELECT * FROM
encounters` would pull 5M rows to show 50. The query is therefore sent as
`SELECT * FROM (<query>) AS q LIMIT 51`: Postgres stops at 51 rows (measured
under 1 s on `encounters`, and a test checks it).
- **It stays one prepared statement,** so layer 2 still holds.
- **A server-side cursor was rejected:** psycopg sends `DECLARE ... CURSOR`
  without a prepared statement, which would weaken layer 2.
- **The wrapper itself:**
  - **Before wrapping,** the query's own trailing `;` is removed with
    `sqlguard.strip_terminator`, which ignores any `;` inside quotes or
    comments.
  - **The closing parenthesis goes on a new line,** so a trailing
    `-- comment` can't swallow it.
  - **`SHOW` can't be wrapped,** and returns few rows, so it runs as is.
- **Error positions are corrected** for the 16 characters the wrapper adds,
  so "at character N" points into the agent's own SQL.

**Also fixed while doing this.** `db.py` now closes its pools when the
process exits. Without that, exit waited about 5 s per pool thread (20 s
seen), which would have slowed every MCP server shutdown.

## D17. Two seed bugs, found in PR #4 and fixed (2026-11-11)

PR #4 was an earlier, parallel implementation of `db.py` and `seed.py`,
opened from another session and never merged. Its description reported two
bugs, and both turned out to be in the code merged in #6. #4 was closed after
its two fixes were ported here.

**Bug 1: learnsets came from the wrong game.**
- **What went wrong.** For each (Pokémon, move, learn method), `seed.py` kept
  the version group with the highest id, as "newest". But PokeAPI ids follow
  when a row was added: `red-green-japan` (release order 1) has id 28 and
  `blue-japan` (order 2) has id 29, above `scarlet-violet` (25). So Generation
  1 Pokémon got levels from the 1996 Japanese games. Bulbasaur's Vine Whip was
  stored at level 13 instead of 3.
- **Fix.** The fetch stage loads all 32 version groups and ranks by their
  release `order`. An unknown version group raises instead of guessing.
- **Data update.** The snapshot was re-fetched, approved by the user as a
  deliberate update under D7.
  - **Changed:** only learnset levels, in 690 level-up rows across 141
    Pokémon (0.6% of 115,026 rows).
  - **Unchanged:** types, abilities, moves, the Pokémon list and every stat.
  - **Reproducible:** a second fetch gives the same bytes.
- **Tests.** Regression: a high-id old game loses to a newer one. Also, an
  unknown game fails loudly.

**Bug 2: the workload wasn't reproducible at full scale.**
- **What went wrong.** `setseed()` fixes the *sequence* of `random()` values,
  but which row receives which value followed the join order of
  `teams × generate_series × pool`. That order depends on table statistics
  and planner settings. At scale 1.0 a fresh build and a rebuild produced
  different `team_members`, and, because the `random()` sequence continues
  into the next statements, different `battles` as well.
- **Why our checks missed it.** The earlier check compared rebuild with
  rebuild, at scale 0.1, where the plan happened not to change.
- **Fix** (from #4). `team_members` rows come from a subquery sorted by
  (team, slot). Postgres doesn't flatten a subquery with ORDER BY, so
  `random()` always runs in that order.
- **Verified.**
  - **Full scale:** after the fix, a fresh build and a rebuild give identical
    md5s for `team_members`, `battles`, `encounters` and `pokemon_moves`.
  - **The fresh-build md5s for `team_members` and `battles`** equal the ones
    taken before the fix. So the earlier fresh-build data (on which PR #8's
    query timings were measured) is unchanged.
- **Test.** `tests/test_seed.py::test_workload_rows_do_not_depend_on_the_query_plan`
  generates a tiny workload inside a rolled-back transaction, with default
  planner settings and three non-default ones, and compares. Without the fix,
  the `enable_material = off` case fails, so this test catches the bug at
  CI's small scale.

**Not ported from #4.** Its alternative `db.py` (ours carries D11 and D12),
a `VACUUM ANALYZE` after seeding, and resetting `pg_stat_statements` (still
an open item).

**Also in this change.** The Docker start-up command in CLAUDE.md now gives
up after 60 s. Once this session, Docker exited during start-up, and the old
loop waited for it forever.

## D18. An Opus orchestrator with Sonnet subagents (2026-11-11)

**Decision.** The main session runs on Opus and orchestrates. Three workers in
`.claude/agents/` run on Sonnet:

| agent | job | tools | effort |
|-------|-----|-------|--------|
| `implementer` | one scoped code change from a contract; runs the tests | Read, Edit, Write, Glob, Grep, Bash | medium |
| `reviewer` | finds defects in a diff and reports them; never edits | Read, Glob, Grep, Bash | high |
| `task-author` | writes and validates eval tasks; the only reader of `tasks/heldout/` | Read, Write, Edit, Glob, Grep, Bash | high |

**Why.** D10 already split the work: Opus for heavy work, Sonnet for routine.
Until now the user switched models by hand. The agent files make that split
automatic. Opus keeps what needs judgment (design, contracts, verification,
docs, git). Sonnet does the bulk work in its own context, so that context does
not fill the main session.

**Safety.**
- **An explicit `tools` list on every agent.** Without one, a subagent
  inherits every MCP tool, `apply_index` included. The list also leaves out
  `Agent`, so workers cannot start more workers.
- **`permissionMode` is not overridden.** Workers follow the user's normal
  permission rules.
- **Workers do no git and do not edit `docs/`.** The orchestrator owns both,
  so the work of two agents cannot mix in one commit, and the docs stay in one
  voice.

**Eval integrity.** If the session that designs the tools writes the heldout
tasks, it knows the test (ARCHITECTURE decision 7). The `task-author` has its
own context, writes them, and reports only counts. **Limit:** this rule is an
instruction. The `tools` field cannot limit a tool to a folder. If the log
shows a breach, the next step is a hook that blocks reads of `tasks/heldout/`.

**Context cost.** Subagents read CLAUDE.md. Its "read these first" list (about
725 lines of docs) now applies to the main session only. Each contract carries
the context a worker needs instead.

**Go-ahead rule (amends D10).** The user decided: one go-ahead covers a whole
orchestrated plan. The orchestrator shows the plan and its task contracts,
waits once, and then runs the workers without asking again. Anything outside
the approved plan needs a new go-ahead. The old reason for asking before each
change, switching models, no longer applies.

**Not chosen.**
- **More agent types** (for example a separate test writer or explorer). Each
  description is in the orchestrator's context on every turn, and agents with
  overlapping jobs make the choice unclear. The built-in Explore agent already
  covers broad searches.
- **`isolation: worktree` in the agent files.** It is chosen per call instead,
  only for parallel work. One worker in the main checkout is simpler, and its
  changes are visible at once.

**Measurement.** Each delegation gets a row in `docs/orchestration-log.md`:
tokens, time, rework and review findings. The setup is tuned from that data.
