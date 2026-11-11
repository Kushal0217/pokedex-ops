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
- **One row per (Pokémon, move, learn method),** taken from the newest version
  group. PokeAPI lists a move once per game version, and the schema's primary
  key allows one row.
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
