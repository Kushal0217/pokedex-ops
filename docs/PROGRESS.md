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
