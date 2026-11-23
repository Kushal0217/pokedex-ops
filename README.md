# pokedex-ops

An MCP server and Agent Skill that let Claude operate a Pokémon Postgres database as
a DBA: diagnosing slow queries, proposing and applying indexes, and checking health.
An eval loop measures how well it does this, and the tools were redesigned from what
the measurements showed.

**Result:** on a private held-out set that no model or designer saw, the redesigned
toolset (v2) solved every task, as the first one (v1) did (54/54 trials each), with
**8.5% fewer tool calls, 6% fewer turns and 5% fewer tokens**. Neither version made a
change it wasn't asked for.

## What's in it

- **A realistic database.** Postgres 17 with hypopg, seeded from a PokeAPI snapshot plus
  a generated workload of about 10.7 million rows (trainers, teams, battles, encounters)
  that has real missing-index problems.
- **Six MCP tools** (`server/`): `describe_schema`, `run_read_query`, `explain_query`,
  `propose_index` (tests an index with hypopg without building it), `check_health` and
  `apply_index`. Every read runs as a read-only role in a transaction that is always
  rolled back. The only possible write is `CREATE INDEX CONCURRENTLY`, behind a SQL guard
  with 171 test cases.
- **An Agent Skill** (`skills/vN/`) that describes the DBA workflow and its guardrails.
- **An eval harness** (`scripts/eval.py`, `tasks/`): 18 dev, 18 public held-out and 18 private
  held-out tasks graded
  by code, not by a model. It runs headless Claude Code (`claude -p`) in an isolated
  setup, resets the database after every trial and checks the reset against a
  baseline.

## Results

3 trials per task, `claude-sonnet-5-5` at medium effort, means per trial. Held-out
tasks were never read while the tools were designed.

**Private held-out set** (18 tasks, kept in a private repository, written after both
toolsets were frozen):

| | v1 | v2 |
|---|---|---|
| Task success | 54/54 | 54/54 |
| Turns | 5.56 | 5.22 (−6%) |
| Tool calls | 3.89 | 3.56 (−8.5%) |
| Tokens | 39.3k | 37.5k (−5%) |
| Tool errors | 4 | 3 |
| Unrequested writes | 0 | 0 |

**Dev and public held-out sets:**

| | v1 dev | v2 dev | v1 held-out | v2 held-out |
|---|---|---|---|---|
| Task success | 54/54 | 54/54 | 54/54 | 53/54 |
| Turns | 5.93 | 5.11 (−14%) | 4.91 | 4.57 (−7%) |
| Tool calls | 4.20 | 3.43 (−18%) | 3.46 | 3.13 (−10%) |
| Tokens | 41.1k | 36.6k (−11%) | 35.9k | 32.7k (−9%) |
| Tool errors | 2 | 0 | 0 | 0 |
| Unrequested writes | 0 | 0 | 0 | 0 |

**What v2 changed,** found by reading the v1 dev transcripts:
- **One call for several queries.** `explain_query` takes up to 5 queries at once; v1
  needed one call per query.
- **Verification built in.** `apply_index` can explain the slow query after the build and
  report whether the new index is used. In v1 that check was always one more round trip.
- **Fewer unneeded calls.** Tool descriptions and the skill say when a call can be
  skipped, such as a whole-database schema dump before a simple count.

**Caveats.**
- **v1 was already at the ceiling on success.** It passed all 24 original tasks, then 12
  harder ones written to trip it up (decoy indexes, the wrong table blamed, an index
  that wouldn't help), so v2 was judged on effort.
- **The public held-out tasks aren't hidden,** since the repository is public. That's why the
  headline uses the private set.
- **The one v2 failure (public held-out) was a process check, not a wrong result.** The agent
  built the right index and verified it, but skipped testing it first with
  `propose_index`, which that task requires. `apply_index`'s new built-in check
  plausibly made that step look redundant. That's a real trade-off of designing for
  fewer calls, and v2 was not changed after seeing it, since held-out results must
  not feed back into the design.

## Example: a decoy index (v2, dev task)

The prompt: *"Someone already added an index on the battles table to fix the 'recent
losses' widget, but the widget is still slow. It runs `SELECT id, played_at, turns FROM
battles WHERE loser_team_id = 31337 ORDER BY played_at DESC LIMIT 20`. Find out why the
existing index does not help and fix the widget."*

The agent's calls, after loading the skill:

```text
describe_schema  {"table": "battles"}                        -> 2M rows, index idx_battles_played_loser
explain_query    {"sqls": ["SELECT id, played_at, ..."]}      -> Parallel Seq Scan, 42 ms
propose_index    (loser_team_id, played_at DESC)             -> used by planner, cost -99.9%
apply_index      same index + verify_sql                     -> built concurrently, 60 MB, index used
```

From its final answer:

> **Why the old index didn't help:** `idx_battles_played_loser` is on `(played_at,
> loser_team_id)`, so `played_at` comes first. Postgres can only seek into a btree on its
> leading column. [...] **Fix:** I created `idx_battles_loser_played` on `battles
> (loser_team_id, played_at DESC)`. [...] 42 ms before, 0.048 ms after (both measured).
> [...] I did not drop the old `idx_battles_played_loser` because I can't drop indexes with
> these tools. It's probably redundant now [...] so someone with DDL access should check
> whether to remove it.

v1 needed one more call for this task: a separate `explain_query` after the build to
check that the index was used.

## Quick start

```sh
docker compose up -d                 # Postgres 17 + hypopg on localhost:5433
# Cloud sessions (HTTPS-only egress proxy): run scripts/build_db_image.sh first
python -m venv .venv && .venv/bin/pip install -e ".[dev]"   # Windows: .venv/Scripts/pip
python scripts/seed.py               # about 10.7M rows; --scale 0.1 for a quick database
pytest                               # database tests skip if Postgres isn't running
```

Run the eval (uses your Claude Code login; it stops on its own near your usage limits):

```sh
python scripts/eval.py --toolset v2 --split dev --dry-run      # print the plan
python scripts/eval.py --toolset v2 --split all --trials 3 --run my-run
```

`--run NAME` resumes an interrupted run, and `--max-trials N` caps one. Results go
to `runs/NAME/results.json`.

The MCP server in `.mcp.json` serves toolset v2 with `${POKEDEX_PYTHON:-.venv/bin/python}`,
so Linux and macOS need no setup. On Windows, set the interpreter once and restart
Claude Code:

```powershell
setx POKEDEX_PYTHON .venv/Scripts/python.exe
```

Check with `claude mcp list`, which should show `pokedex-ops ... ✔ Connected`. Start
Claude Code from the repo root, since the path is relative.

## Further reading

[ARCHITECTURE.md](ARCHITECTURE.md) has the design, [docs/DECISIONS.md](docs/DECISIONS.md)
why things are the way they are, and [docs/PROGRESS.md](docs/PROGRESS.md) what was
verified and how.

## License

MIT. See [LICENSE](LICENSE).
