# Architecture

An MCP server and Agent Skill that let Claude act as the DBA for a Pokémon Postgres
database, plus an eval loop that measures how well it does that job. The before/after
score across tool versions is the deliverable.

## Layout

```
pokedex-ops/
├── docker-compose.yml          Postgres 17 + hypopg + pg_stat_statements, port 5433
├── docker/
│   ├── Dockerfile
│   └── init/01-setup.sql       extensions + the two roles (runs once on a fresh volume)
├── db/
│   ├── schema.sql              tables only; workload tables have primary keys and nothing else
│   └── workload.sql            synthetic rows generated in SQL, sized by :scale
├── data/
│   └── pokeapi_snapshot.json.gz  committed PokeAPI snapshot (ground truth, no network in CI)
├── server/
│   ├── config.py               DSNs and limits from env / .env
│   ├── db.py                   the ONLY place connections are opened (read path, write path)
│   ├── sqlguard.py             statement classification (pure, unit-tested)
│   ├── tools.py                tool behaviour (handlers)
│   ├── toolsets/
│   │   ├── __init__.py         ToolSpec / Toolset types, load("v1")
│   │   └── v1.py               tool names, descriptions, schemas, policy (agent-facing interface)
│   └── mcp_server.py           thin adapter: Toolset -> MCP over stdio
├── .claude/skills/pokedex-ops/
│   ├── SKILL.md                workflow + guardrails (always loaded)
│   └── reference/tools.md      detailed tool docs (loaded only when needed)
├── scripts/
│   ├── seed.py                 snapshot -> reference tables -> workload
│   └── eval.py                 tasks x trials -> transcripts + scored report
├── tasks/
│   ├── dev/*.yaml              read transcripts and redesign tools against these
│   └── heldout/*.yaml          scored only, never read while tuning
├── runs/                       eval output (gitignored)
├── dashboard/report.md         generated before/after table + failure breakdown
└── tests/
```

## Decisions

**1. Behaviour and interface are separate.** `tools.py` holds what a tool does.
`toolsets/vN.py` holds what the agent sees: name, description, schema and policy.
The eval loop redesigns the interface, so it is versioned and swappable. A
description rewrite cannot change behaviour by accident, and v1 stays runnable for
comparison.

**2. One code path for Claude Code and the eval.** `mcp_server.py` and `eval.py`
both consume the same `Toolset`. The eval calls the handlers directly rather than
through an MCP client, so it measures exactly what Claude Code gets without the
cost of a subprocess.

**3. Two connection paths and two roles.** These are set up in `docker/init`.

| path  | role            | rights                     | used by          | mode                                   |
|-------|-----------------|----------------------------|------------------|----------------------------------------|
| read  | `pokedex_agent` | SELECT, `pg_read_all_stats` | every read tool  | `BEGIN READ ONLY` … always `ROLLBACK`  |
| write | `pokedex_dba`   | table owner                | `apply_index`    | autocommit, so `CONCURRENTLY` works    |

The superuser (`postgres`) is used only by `seed.py` and eval fixtures and is
never reachable from a tool.

**4. Guardrails are layered.** No single layer is trusted on its own.
1. `sqlguard.classify` sorts each statement into read, create-index or forbidden,
   and gives the agent a clear reason when it rejects one.
2. One statement per call. psycopg 3 uses the extended protocol, which refuses
   multi-statement strings.
3. Every read runs in a `READ ONLY` transaction that is always rolled back. This
   also covers `EXPLAIN ANALYZE`, which really executes its query.
4. The role can only SELECT, and `default_transaction_read_only` is on, with a
   `statement_timeout`.

**5. The data is big enough for plans to matter.** The reference tables hold real
PokeAPI data, but there are only about 1k Pokémon, and at that size a full table
scan is always the best plan. The workload tables (trainers, teams, team_members,
battles, encounters) hold millions of rows with skewed distributions and no
secondary indexes, so the slow queries and missing indexes are real.

**6. The data is reproducible.** PokeAPI is fetched once into a committed snapshot,
and the workload is generated with `setseed()`. Every rebuild is identical, so
eval ground truth never drifts.

**7. The eval resists overfitting and is graded by code.** Tasks are split into dev
and heldout. Every check is computed from database state or the transcript, with
no LLM judge. Each task runs N trials because single runs are noisy. v2 is written
only after reading the v1 dev transcripts.

## Build order

1. Postgres in Docker, `seed.py`, and a check that the data loads.
2. `sqlguard` + `db` + read-only tools, with tests.
3. SKILL.md and the task set.
4. Baseline eval with v1, recorded honestly.
5. v2 toolset from the transcripts, then re-run and compare.
6. README with the number, one real failure, and what it turned into.
