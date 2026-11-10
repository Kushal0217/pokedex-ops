# Progress

Where the build stands, what has been verified and how, and what is still open.
Update this file in the same PR as the work it describes. The reasons behind
choices live in [DECISIONS.md](DECISIONS.md); the design is in
[ARCHITECTURE.md](../ARCHITECTURE.md).

_Last updated: 2026-11-10._

## Build order

Steps from ARCHITECTURE.md, "Build order".

| # | step | status |
|---|------|--------|
| 1 | Postgres in Docker, `seed.py`, check that the data loads | **done** |
| 2 | `sqlguard` + `db` + read-only tools, with tests | **in progress**: `sqlguard` done; `db.py` and `tools.py` not started |
| 3 | SKILL.md and the task set | not started |
| 4 | Baseline eval with v1, recorded honestly | not started |
| 5 | v2 toolset from the transcripts, re-run and compare | not started |
| 6 | README with the number, one real failure, and what it turned into | not started |

## Module status

| module | status | tests |
|--------|--------|-------|
| `server/sqlguard.py` | implemented | `tests/test_sqlguard.py`, 141 cases |
| `server/mcp_server.py` | implemented: starts over stdio and lists the toolset's tools | `tests/test_mcp_server.py` |
| `server/toolsets/v1.py` | names and schemas done; descriptions are still `TODO` | `tests/test_scaffold.py` |
| `server/db.py` | stub | none |
| `server/tools.py` | stubs (all six tools) | none |
| `scripts/seed.py` | implemented | `tests/test_seed.py`, 29 cases |
| `scripts/eval.py` | stub | none |
| `.claude/skills/pokedex-ops/` | stub | none |
| `tasks/dev`, `tasks/heldout` | empty | none |

Test suite: 172 passing. None of them need the database yet; CI runs
`pytest -m "not db"`.

## Verified

Each item says what was checked and what was seen, so it can be re-checked later.

**SQL guard (`sqlguard.classify`).** 141 unit tests: allowed reads; quotes and
comments ignored when looking for keywords and `;`; one statement per call;
writes, DDL, transaction control and session commands refused; writes hidden
in `WITH` clauses, row locks, `SELECT ... INTO` and side-effecting functions
refused; `CREATE INDEX` parsed for its table name and `CONCURRENTLY`; and junk
input such as a lone `'`, which returns a verdict instead of raising.

**MCP server.** Launched over stdio with a real MCP client: the handshake
succeeds and all six v1 tools are listed with the toolset's own descriptions
and schemas. Calling a tool still fails with `NotImplementedError`.

**Database image (cloud).** `scripts/build_db_image.sh` builds the image,
installing hypopg 1.4.5, and `docker compose up -d` comes up healthy, with
PostgreSQL 17.11, `hypopg` and `pg_stat_statements` installed, and
`pokedex_agent` and `pokedex_dba` present as non-superusers.

**Seed.** Verified in the cloud at both scales:

| scale | rows | time | database size |
|-------|------|------|---------------|
| 0.1 | 1.07M workload rows | 6 s | not measured |
| 1.0 | 10.7M workload rows (200k trainers, 500k teams, 3M team members, 2M battles, 5M encounters) | 31 s | 1.0 GB (encounters 492 MB, team_members 246 MB, battles 207 MB) |

- **Reproducible.** Fetching the snapshot twice gave byte-identical files, and
  regenerating the workload gave identical rows (md5 of the `battles` table
  matched).
- **Ownership and indexes.** Every table is owned by `pokedex_dba`, and the
  workload tables have no indexes beyond their primary keys.
- **Agent role.** `pokedex_agent` can SELECT. An INSERT fails with "cannot
  execute INSERT in a read-only transaction", and with `BEGIN READ WRITE`
  forced it fails with "permission denied for table types".
- **Reference data.** 1,025 Pokémon, 797 moves, 284 abilities, 18 types,
  115,026 Pokémon-move rows; spot checks: Pikachu is Electric, Charizard is
  Fire/Flying.

**The workload has real index problems.** Checked at scale 1.0:
- **Missing index.** `SELECT count(*) FROM battles WHERE winner_team_id = 4242`
  runs a parallel sequential scan over 2M rows: 97 ms to return 2 rows. With a
  hypopg hypothetical index on `battles (winner_team_id)`, the plan becomes an
  index-only scan and the estimated cost drops from 32,364 to 24. The 97 ms is
  modest because the table fits in memory, so tasks should judge plans and
  costs, not wall-clock time alone.
- **Skew.** It matches the design in `workload.sql` (half the team slots drawn
  from 60 popular Pokémon), and the planner sees it: the statistics hold 68
  most-common values for `team_members.pokemon_id`. Estimated vs actual rows:
  28,400 vs 26,774 for the most popular Pokémon, 1,446 vs 1,342 for the rarest.

**Fully populated at scale 1.0** (checked 2026-11-10). All 13 tables match
their expected row counts exactly, and no `team_members` row points at a
missing team and no `teams` row at a missing trainer. Between sessions the
Docker service had stopped, so Postgres ran crash recovery on restart. It
recovered cleanly and the planner statistics survived for all 13 tables, but
the activity counters in `pg_stat_user_tables` were reset (`last_analyze`
reads null). That's expected after an unclean stop, and harmless.

**Query timings at scale 1.0** (2026-11-10). For each query: one warm-up run,
then the median of 3 runs, as `postgres` against the cloud database. "Cost" is
the planner's estimate (`EXPLAIN`); "cost with index" is the same plan with
the listed index created hypothetically with hypopg (nothing built).

| query | SQL | median | cost now | cost with index | index tried |
|-------|-----|--------|----------|-----------------|-------------|
| Primary-key lookup (baseline) | `SELECT * FROM battles WHERE id = 123456` | 0.6 ms | 8 | n/a | already indexed |
| Teams of one trainer | `SELECT * FROM teams WHERE trainer_id = 4412` | 15.8 ms | 8,759 | 16 | `teams (trainer_id)` |
| Battles won by a team | `SELECT count(*) FROM battles WHERE winner_team_id = 4242` | 47.6 ms | 32,364 | 4 | `battles (winner_team_id)` |
| A trainer's rosters | `SELECT t.name, m.slot, m.pokemon_id FROM teams t JOIN team_members m ON m.team_id = t.id WHERE t.trainer_id = 4412` | 15.6 ms | 8,778 | 68 | `teams (trainer_id)` |
| Latest 20 encounters of a trainer | `SELECT * FROM encounters WHERE trainer_id = 123 ORDER BY encountered_at DESC LIMIT 20` | 83.0 ms | 76,238 | 83 | `encounters (trainer_id, encountered_at)` |
| Teams using Pikachu | `SELECT count(DISTINCT team_id) FROM team_members WHERE pokemon_id = 25` | 55.8 ms | 36,573 | 4,615 | `team_members (pokemon_id)` |
| Ranked battles in one week | `SELECT count(*) FROM battles WHERE is_ranked AND played_at >= '2023-03-01' AND played_at < '2023-03-08'` | 66.4 ms | 34,455 | 17,756 | `battles (played_at)` |
| A trainer's win count | `SELECT count(*) FROM battles b JOIN teams t ON t.id = b.winner_team_id WHERE t.trainer_id = 4412` | 65.7 ms | 40,227 | 8,764 | `battles (winner_team_id)` only |
| Top 10 most-used Pokémon | `SELECT p.name, count(*) FROM team_members m JOIN pokemon p ON p.id = m.pokemon_id GROUP BY p.name ORDER BY 2 DESC LIMIT 10` | 225.1 ms | 43,180 | n/a | none would help |
| Shiny catches per location | `SELECT location, count(*) FROM encounters WHERE is_shiny AND caught GROUP BY location` | 101.9 ms | 71,035 | n/a | none would help |

What this means for the task set (step 3):
- **Clear wins.** Lookups on an unindexed column scan the whole table, and the
  right index cuts the estimated cost by 100 to 8,000 times. These make good
  "find the missing index" tasks.
- **Harder cases worth a task each.**
  - **The win-count join needs two indexes.** With only `battles
    (winner_team_id)` it still scans `teams`; `teams (trainer_id)` is needed too.
  - **The one-week range only halves** with `battles (played_at)`, because
    `is_ranked` is filtered after the index.
  - **Pikachu is in the popular pool,** so an index helps far less there than
    for a rare Pokémon.
- **"No index will help" is a valid answer.** The two aggregates read every
  row by nature, and a good agent should say so instead of adding an index.
- **Wall-clock times are small** (all under 250 ms) because the 1.0 GB database
  fits in memory. Grade on plans and estimated costs, not timings.

## Open items

- [ ] **Plain Docker build on the laptop.** `docker compose build` with no
  proxy has not been run since PR #5. In the cloud, the build steps it adds
  work, and so does the empty placeholder mount it uses when no certificate is
  supplied. Needs: run it once on the laptop and record the result here.
- [ ] **v1 tool descriptions** in `server/toolsets/v1.py` are `TODO`. They
  must be written before the baseline eval (step 4), as a plain first draft,
  not tuned.
- [ ] **pg_stat_statements is not reset after seeding**, so the seed's own
  statements show up in it. Decide whether `seed.py` or the eval fixtures
  should reset it.
- [ ] **No database tests yet.** The `db` pytest marker exists, but no test
  uses it, and CI never runs a database.

## Next

`server/db.py`: the read-only path and the write path, plus `@pytest.mark.db`
tests for guardrail layers 2 to 4 (one statement per call, rollback, the
read-only role, `statement_timeout`).

## History

| date | PR | what |
|------|----|------|
| 2026-11-09 | (initial commits) | Scaffold: architecture, interfaces, infra; `prepare=True` rule for single-statement execution |
| 2026-11-10 | #1 | `sqlguard.classify` with 141 unit tests |
| 2026-11-10 | #2 | MCP server starts: `build()` implemented, portable launch path in `.mcp.json` |
| 2026-11-10 | #3 | Windows setup for the MCP server documented |
| 2026-11-10 | #5 | Database image builds behind the cloud's HTTPS-only proxy |
| 2026-11-10 | #6 | `seed.py` implemented; PokeAPI snapshot committed |
| 2026-11-10 | #7 | Progress and decision docs, CLAUDE.md |
| 2026-11-10 | this PR | Population check and query timings at scale 1.0 recorded |
