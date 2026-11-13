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

## D19. A seeded database starts settled and with clean statistics (2026-11-11)

Three small changes, first written in PR #4 and listed in D17 as not ported.

**1. `VACUUM` after the workload stage.** Bulk inserts leave the visibility map
empty, and the first read of each page writes hint bits. So until autovacuum
gets there, a query after a seed is slower and does writes that later runs
don't. The eval measures query times, so its numbers would depend on whether
autovacuum had run yet.
- **Measured** (scale 1.0, right after a seed without the VACUUM; autovacuum
  had not run): `encounters` had 0 of 49,194 pages all-visible. An index-only
  scan over 400k ids did 400,001 heap fetches, touched 6,043 buffers (3,936
  dirtied, 4,517 written) and took 104.8 ms. After `VACUUM`: 0 heap fetches,
  1,102 buffers, 33.2 ms.
- **Cost:** about 1 s at scale 1.0. The stage's `count(*)` checks already set
  the hint bits, so the VACUUM mostly marks pages all-visible.
- Plain `VACUUM`, not `VACUUM ANALYZE`: `workload.sql` already ends with ANALYZE.

**2. `pg_stat_statements` is reset after any stage that changes the database**
(this closes the open item in PROGRESS). Otherwise the seed's own INSERTs are
the most expensive statements in it, and a health check or the agent would see
them first. The reset needs the superuser, so it is the one place `seed.py`
uses `ADMIN_DSN`, which ARCHITECTURE decision 3 allows. Eval fixtures can still
reset per task; this makes the starting state clean.

**3. The tools' connections carry `application_name`** (`pokedex-ops:read`,
`pokedex-ops:write`). In `pg_stat_activity` a health check can then tell the
tools' own sessions from everyone else's, for example to leave itself out of
"active connections".

**Tests.** Each was checked to fail without its change: the VACUUM test failed
on a database seeded by the old code (`ops_audit_log: 0 of 1 pages
all-visible`), and the label test failed without the `db.py` change.

## D20. What `explain_query` returns (2026-11-11)

**Decided by the user,** from options measured on the full-scale database
(tokens are estimated as characters divided by 4, as in D16).

- **E1. It always runs `EXPLAIN ANALYZE`,** and falls back to plain `EXPLAIN`
  if the statement_timeout cancels it. Plain EXPLAIN took 4-5 ms on two test
  queries; EXPLAIN ANALYZE took 457 and 852 ms, but only it shows actual rows
  and times, which is how a bad row estimate becomes visible. There is no
  `analyze` parameter. ANALYZE really executes the query; the read-only
  transaction that is always rolled back is what makes that safe.
- **E2. The plan is Postgres's raw text output, unchanged.** Measured on a
  filter over 5M rows and on a join with grouping: raw JSON 540 / 1,844
  tokens, raw text 139 / 642, compact JSON 110 / 411, compact text 46 / 181.
  Known cost of this choice: Postgres prints per-loop numbers, so with 3
  parallel workers `rows=3 loops=3` means 9 rows and `Rows Removed by
  Filter: 1666664` means about 5M. If the v1 transcripts show the agent
  misreading these, that is a v2 change.
- **E3. BUFFERS is on.** It adds 40-50% to the plan (99 -> 138 tokens, 428 ->
  642), and shows the pages read from memory and from disk: the clearest
  measure of a query's work, and of what an index saves.
- **E4. Facts only: no diagnosis notes in v1.** Notes (for example "this scan
  removed 5M rows") are a v2 candidate, so the v1-to-v2 comparison can show
  whether they help.

**Output:** `{"plan": <text>, "analyzed": <bool>}`, plus `"note"` only when
the fallback ran.

**Details decided by the orchestrator:**
- **Refusals:** SQL starting with `EXPLAIN` gets its own message (sqlguard's
  reason, "use the explain_query tool", would be confusing here);
  `CREATE INDEX` points to `apply_index`; `SHOW` points to `run_read_query`,
  since Postgres can't explain it; anything else not a read gets sqlguard's
  reason.
- **The EXPLAIN prefix is on its own line,** so a trailing `-- comment` can't
  break the statement, and error positions are corrected for it, as in D16.
- **The fallback runs only for our own timeout.** A cancel from another
  session (`pg_cancel_backend`) raises the same `QueryCanceled`, so the code
  also requires that the time spent is at least the timeout. A real timeout
  always meets that, and another session's cancel always comes sooner.
  Message text was not used: Postgres translates it. Someone who cancels a
  query wants it stopped, so it is reported, not re-run.

**Built by the orchestrator setup (D18).** The implementer (Sonnet) wrote it
from a contract; the reviewer (Sonnet) found the cancel bug by reproducing it
(a cancel at 0.5 s gave the note "cancelled after 20 s"), and two tests that
could not fail. All three were fixed, and the new cancel test was checked to
fail without the fix. Costs are in `docs/orchestration-log.md`.

## D21. Implementers prove each new test can fail (2026-11-11)

**Decision** (user, from the first orchestrated work, D20). The implementer
subagent must break the behaviour each new test checks, see the test fail,
then restore the code, and list what it broke in its report.

**Why.** In the explain_query work, two of the implementer's tests could not
fail: one passed whether or not the fallback was wrong, and one never reached
the read-only transaction it claimed to test. The reviewer found them, but a
test that passes either way gives false confidence, and the reviewer's time is
better spent on bugs. The orchestrator already did this check by hand.

**Risk and control.** The check edits code for a moment, so a worker could
leave it broken. "Done" therefore also requires `git diff` to show the code
restored exactly, and the orchestrator still runs the tests itself (D18).

## D22. `apply_index` always builds CONCURRENTLY (2026-11-11)

**Decided by the user (A1, "Always, add it").** A plain `CREATE INDEX` blocks
every write to the table until the build ends; `CREATE INDEX CONCURRENTLY`
does not. Measured at scale 1.0, concurrent builds took 0.3-2.5 s. When the
agent leaves the keyword out, the tool adds it and says so
(`concurrently_added: true` and a note). The other options were to refuse
such a statement, which would let the eval measure whether the agent knows the
rule, or to run it as given. The user chose safety over measuring that rule.

**Output:** `{"created": true, "index", "table", "definition", "valid",
"size", "elapsed_ms", "concurrently_added"}`, plus `"note"` when CONCURRENTLY
was added. `IF NOT EXISTS` on a name that exists gives `{"created": false,
"table", "note"}`. Build failures come from `db.create_index` as before,
including the name of any INVALID index a failed concurrent build left.

**Details decided by the orchestrator:**
- **The keyword is inserted by token position** (`sqlguard.add_concurrently`),
  never by text search, so comments and quoted names cannot misplace it. The
  result is classified again and must still be a concurrent CREATE INDEX.
- **The new index is found by comparing the table's index names before and
  after the build,** because the agent may leave out the name. Two cases
  are refused or reported instead of guessed:
  - **A table that cannot be found is refused before the build.** Found in
    review: a quoted table name with a dot in it (`"a.b"`) was built, then
    reported as "nothing was built", because the name lookup failed.
  - **More than one new index** (another session built one at the same time)
    gives an error that lists them, instead of a crash or a wrong name.
- **Leading `;` are dropped** (`strip_terminator`), as `classify` already
  ignores empty statements. Found in review: `;CREATE INDEX ...` crashed
  with an AssertionError. The assert is now a ToolError.
- **`confirm` is unused** in v1 (policy `apply_index_requires_confirm: False`).
  v2 may add a dry-run step that uses it.

**Built by the orchestrator setup (D18).** The implementer showed each of its
tests failing with the behaviour broken (D21); the reviewer reproduced two
bugs and named one race. The orchestrator fixed all three and showed each new
test failing without its fix.

## D23. What `check_health` reports (2026-11-11)

**Decided by the user (H1, "All sections"):** nine sections in one call, so
an agent told only "the database is slow" can find where to look:
`connections` (per state), `long_running` (active over 5 s), `blocking`
(waiter, blocker pids, wait time), `cache_hit_pct`, `tables`,
`invalid_indexes`, `unused_indexes` (with `stats_since`, because "unused"
only means unused since the statistics began), `top_queries` (top 5 by total
time from pg_stat_statements) and `replication` ("no replica configured",
never invented).

**Size: about 820 tokens, not the 346 measured for the decision.** The
probe for H1 returned plain rows; the tool returns named fields for each of
the 13 tables, and `tables` is three quarters of the report. Timestamps were
cut to whole seconds (3,562 -> 3,269 characters). A more compact layout is a
v2 candidate, decided from the transcripts. The report takes about 90 ms.

**Details decided by the orchestrator:**
- **The tools never report themselves.** Sessions named `pokedex-ops:read`
  or `pokedex-ops:write` (D19) are left out of `connections`,
  `long_running` and `blocking`; queries run by the tool roles
  `pokedex_agent` and `pokedex_dba` are left out of `top_queries`.
  pg_stat_statements keeps one entry per user, so this is exact.
- **Row counts come from `pg_class.reltuples`,** not `n_live_tup`, which
  reads 0 after a restart.
- **Each section runs on its own,** and a failing one becomes
  `{"error": ...}` without hiding the others. One exception: if the database
  is unreachable, the whole report stops with that error. Found in review:
  otherwise each of the 10 queries waited out the 5 s pool timeout (50 s).
- **Sizes come from `pg_class.relpages`, not `pg_total_relation_size()`.**
  Found in review: that function locks each table, so one table under an
  ACCESS EXCLUSIVE lock, which is one of the problems the report must show,
  cancelled the whole `tables` section. `relpages` needs no lock; it is
  updated by VACUUM, ANALYZE and CREATE INDEX, so it is an estimate (491 MB
  against 492 MB for `encounters`). Each section also has a 1 s
  `lock_timeout` as a backstop; the implementer added it after the report
  waited 20 s behind a held lock.
- **Primary keys and unique indexes are never "unused":** they enforce
  constraints even when no query reads them.

**Known limits, for v2 to judge from the transcripts:**
- **The lists have no cap.** A real incident with many blocked sessions would
  make a long report.
- **The tools' own write session is left out of `blocking`.** An
  `apply_index` build waiting behind an open transaction does not show; the
  blocker shows only as "idle in transaction" in `connections`.

**Built by the orchestrator setup (D18).** The reviewer reproduced both
failures above and found that nothing tested the `top_queries` filter. The
orchestrator fixed all three and showed each new test failing without its fix.

## D24. What `propose_index` does, and hypopg state never leaks (2026-11-11)

**Decided by the user:**
- **P1, "Agent proposes".** The agent writes the CREATE INDEX and the tool
  only tests it, so `index_sql` is required (v1 schema changed by the
  orchestrator). The rejected option, a tool that finds candidates itself,
  would have done the agent's DBA reasoning for it, so the eval would measure
  the tool more than the agent.
- **P2, "Numbers + new plan".** Output: `{"index_sql", "used_by_planner",
  "cost_before", "cost_after", "cost_reduction_pct", "estimated_size_mb",
  "plan"}`. Measured: `encounters (trainer_id)` for one trainer's caught
  encounters gives cost 76,237 -> 103 (99.9% lower), used, 138.4 MB estimated,
  in 461 characters (about 115 tokens).

**How it works.** In one read-only transaction: plain `EXPLAIN (FORMAT JSON)`
of the query, `hypopg_create_index(index_sql)`, the same EXPLAIN again, the
plain text plan, and `hypopg_relation_size`. Plain EXPLAIN only, because
EXPLAIN ANALYZE ignores hypothetical indexes. `used_by_planner` is true when
the name hypopg generated (for example `<13630>btree_encounters_trainer_id`)
is an "Index Name" anywhere in the plan tree.
- **`index_sql` is passed to hypopg unchanged.** hypopg 1.4.5 accepts
  CONCURRENTLY, IF NOT EXISTS, a name, UNIQUE, WHERE and INCLUDE as they are,
  so the agent tests exactly what it would send to `apply_index`. hypopg
  makes up its own index name.
- **The size is hypopg's estimate,** named `estimated_size_mb`. It was 1.3 to
  3.7 times the real size on six indexes (138 MB estimated, 37 MB real here).
- **The query gets the same checks and messages as `explain_query`**
  (a shared helper); `index_sql` must classify as CREATE INDEX.

**hypopg state never leaks between calls.** Hypothetical indexes, and real
indexes hidden with `hypopg_hide_index()`, belong to the database session,
not the transaction: ROLLBACK does not undo them, so on a pooled connection
they reached the next caller and changed its plans. The agent can create
either through `run_read_query`, because sqlguard has no rule for hypopg
functions. Both are cleared in two places:
- **`db._begin_read`,** in the same statement as the existing `set_config`,
  each time a read connection is checked out (about 0.25 ms per call). This
  covers every tool, including `explain_query`'s plain-EXPLAIN fallback.
  Every read tool now needs the hypopg extension, which the image installs.
- **`propose_index`'s own `finally`,** so it never depends on the next caller.

Found in review: the first version cleared only hypothetical indexes
(`hypopg_reset()`). The reviewer hid `battles_pkey` through `run_read_query`,
and a later `propose_index` reported a cost of 32,364 instead of about 8. Now
`hypopg_unhide_all_indexes()` runs next to it.

**Built by the orchestrator setup (D18).** The implementer showed each test
failing with its behaviour broken (D21). The reviewer found the hidden-index
leak and that one test passed without the tool's own reset. The orchestrator
fixed both and showed each new test failing without its fix.

## D25. Four open-item fixes, and the lost task set (2026-11-13)

**A timeout and a cancel by another session were reported the same way.**
- **Bug.** Our `statement_timeout` and a `pg_cancel_backend` from another
  session raise the same error (57014). `db._tool_error` called both a
  timeout and advised "use EXPLAIN without ANALYZE". So did the write path.
- **Fix.** The same rule `explain_query` already used: elapsed time. A
  timeout can only fire once the limit has passed.
  - **The read path's `Cursor`** times each statement.
  - **The write path** times the build.
  - **A cancel that comes sooner** says "cancelled by another session ...
    check before running it again".
  - **Message text isn't matched,** because Postgres may translate it.
  - **When the elapsed time is unknown,** it still counts as a timeout.
- **Also fixed.** When `explain_query`'s fallback (plain EXPLAIN) also hit
  the timeout, the advice was to run plain EXPLAIN, which had just failed. It
  now says that planning alone is that slow, and to simplify the query.
- **Tests.** Four new tests, all shown failing on the old code:
  - **a unit test** of the rule;
  - **a real `pg_cancel_backend`** of a running read;
  - **a real cancel** of an index build waiting on a held lock;
  - **the fallback timing out** (monkeypatched, no database).

**A statistics test failed on a long-used database.**
`test_reset_query_stats_empties_pg_stat_statements` looked its query up by a
marker alias in the text. But pg_stat_statements keeps the text of the
*first* query of each shape, and aliases don't change the shape, so after
`SELECT count(*) FROM types` had run once, the marker was never stored.
- **Reproduced:** reset, run that query once, then the test failed.
- **Fix:** look the query up by its `queryid`, read from `EXPLAIN (VERBOSE)`.
- **Checked:** it passes in the state that broke it, and still fails if the
  reset does nothing.

**CI.** `actions/checkout@v5` and `actions/setup-python@v6` replace the
deprecated Node 20 versions.

**Docker start-up.** After a session restart, a leftover
`/var/run/docker.pid` can name a PID now used by another process, so dockerd
refuses to start. The CLAUDE.md command now removes the pid file when no
dockerd is running.

**The lost task set.** The orchestration log records the `task-author`
writing and validating 12 dev and 12 heldout tasks on 2026-11-11, with "see
the tasks PR". No such PR or branch exists, and the user doesn't have the
files. So they're lost. Step 3 writes the task set again.
- **The lesson for orchestrated work:** commit and push a worker's output in
  the same session that produced it, before reporting it as done.
