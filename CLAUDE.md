# CLAUDE.md

**Main session:** read these first: `docs/PROGRESS.md` (where things stand,
what's open, what's next), `docs/DECISIONS.md` (why things are the way they
are), and `ARCHITECTURE.md` (the design).

**Subagents:** skip that list. Read only the files your contract names. The
orchestrator puts the context you need into the contract (see Orchestration).

## Workflow

- **Branches.** Start each piece of work on a new branch from `main`. Never add
  commits to a branch whose PR is already merged.
- **Design decisions belong to the user.** When there's a real choice
  (interfaces, behaviour, trade-offs), lay out the options with a
  recommendation and wait for the user's decision. Don't just implement.
- **Announce code changes first.** Before changing code, say what will change
  and wait for a go-ahead. This doesn't apply to questions, reading files, or
  running checks. For orchestrated work, one go-ahead covers the whole plan:
  show the plan and its task contracts once, then run the subagents without
  asking again. Anything outside the approved plan needs a new go-ahead
  (DECISIONS D18).
- **Merging.** Merge a PR only when asked, and only with CI green.
- **Keep the docs current.** In the same PR as the work, update
  `docs/PROGRESS.md`, and add an entry to `docs/DECISIONS.md` for any choice
  that wouldn't be obvious from the code.
- **Record evidence.** When verifying something, write down what was run and
  what was seen.

## Database in a cloud session

The `pokedex-ops` cloud environment allows the hosts needed below. Every
process stops while the session is idle between turns (DECISIONS D14), so
start Docker and the database again in any turn that needs them:

```sh
pgrep dockerd >/dev/null || (setsid nohup dockerd >/tmp/dockerd.log 2>&1 < /dev/null &)
timeout 60 sh -c 'until docker info >/dev/null 2>&1; do sleep 1; done' \
  || { echo "Docker didn't start"; tail -5 /tmp/dockerd.log; }   # can take more than 3 s; never wait forever
scripts/build_db_image.sh        # only if the image isn't built yet; plain `docker compose build` on a laptop
docker compose up -d             # Postgres 17 + hypopg on localhost:5433
python scripts/seed.py           # about 31 s and 1.0 GB at full scale; add --scale 0.1 for a quick one
```

## Tests

`pytest` runs everything; tests marked `@pytest.mark.db` need Postgres and
are skipped when it isn't running. CI has two jobs: `test` runs
`pytest -m "not db"`, and `db-test` builds the image, seeds at scale 0.1 and
runs `pytest -m db` with `POKEDEX_REQUIRE_DB=1`, so a missing database fails
the run instead of skipping (DECISIONS D15).

## Don't

- **Re-fetch the PokeAPI snapshot** (`seed.py --refresh`) unless the user wants
  a deliberate data update (DECISIONS D7).
- **Tune `server/toolsets/v1.py` against eval results.** Improvements go into v2.
- **Read `tasks/heldout/`** while designing tools. Only the `task-author`
  subagent may read or write it, and its reports never reveal heldout content.
- **Compute eval ground truth with the pokedex-ops MCP tools.** They are the
  thing under test; use psql.

## Orchestration (main session only; subagents skip this section)

The main session runs on Opus and orchestrates. The workers in
`.claude/agents/` run on Sonnet (DECISIONS D18).

**Keep in the main session:** design decisions and the questions to the user,
the agent-facing interface (`server/toolsets/`), task contracts, all git work,
`docs/PROGRESS.md` and `docs/DECISIONS.md`, final verification, and the
explanations to the user.

**Delegate:**
- `implementer`: a scoped code change that touches several files or needs a
  lot of reading.
- `reviewer`: after each implementer change, before the commit.
- `task-author`: every eval task, dev and heldout.

**Do not delegate** a change you can finish in a few minutes. A subagent starts
with no context, so the cold start costs more than the work.

**Contract for each delegation:**
1. Goal: one or two sentences.
2. Files allowed to change.
3. Context: the files and DECISIONS entries to read, and the facts the agent
   needs from this conversation.
4. Acceptance: the exact command that must pass.
5. Out of scope.

**Parallel work:** only when the agents change different files. Otherwise pass
`isolation: "worktree"` on the Agent call.

**Verify:** after an implementer reports done, run the tests yourself before
the review or the commit. Never trust a "tests pass" report alone.

**Measure:** add one row per delegation to `docs/orchestration-log.md`, so the
setup can be tuned from data.
