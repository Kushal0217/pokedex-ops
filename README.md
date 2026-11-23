# pokedex-ops

An MCP server and Agent Skill that let Claude operate a Pokémon Postgres database as
a DBA: diagnosing slow queries, proposing and applying indexes, and checking health.
An eval loop measures how well it does this, and the tools were redesigned from what
the measurements showed.

**Result:** the redesigned toolset (v2) solved held-out tasks as often as the first one
(53/54 against 54/54 trials) with **10% fewer tool calls, 9% fewer tokens and 7% fewer
turns**. Neither version made a change it wasn't asked for.

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
- **An eval harness** (`scripts/eval.py`, `tasks/`): 18 dev and 18 held-out tasks graded
  by code, not by a model. It runs headless Claude Code (`claude -p`) in an isolated
  setup, resets the database after every trial and checks the reset against a
  baseline.

## Results

3 trials per task, `claude-sonnet-5-5` at medium effort, means per trial. The held-out
tasks were never read while the tools were designed.

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
- **The held-out tasks are public,** since the repository is. Neither toolset was tuned
  on them, but they aren't hidden from future models.
- **One v2 held-out trial failed,** and its cause wasn't investigated.

## The failure that mattered: the eval leaking answers

The agent never failed in an interesting way; the eval did. A model being evaluated
will use whatever it can see, and a leak doesn't crash anything. It just makes the
score look better. These are the leaks that were found, and each became a permanent
check:

- **The answer key in a tool's output.** The runner computes each task's ground truth
  with SQL just before the agent starts. `check_health` reports the database's most
  expensive recent queries, so the agent could have read the answer query straight from
  a tool. The fix: query statistics are reset right before every trial.
- **The project's own notes.** Run from the project folder, Claude Code loaded this
  repository's `CLAUDE.md`, which discusses the held-out tasks. The fix: every trial
  runs from an empty folder with project-only settings.
- **The user's own setup.** Personal skills and tools could reach the agent under test.
  The fix: a strict tool allowlist, and a check of every trial's startup event for
  exactly the expected tools, the MCP server connected and no personal skill. A trial
  that fails this is marked `isolation_failed` and left out of every score.

Other defects found in review and fixed: a crash mid-trial skipped the database reset;
failed sessions were scored as ordinary failures; a timeout left the MCP server running.
The full list is in [docs/DECISIONS.md](docs/DECISIONS.md) (D29).

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
