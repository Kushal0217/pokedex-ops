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
