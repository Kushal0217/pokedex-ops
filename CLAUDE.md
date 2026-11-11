# CLAUDE.md

Read these first: `docs/PROGRESS.md` (where things stand, what's open, what's
next), `docs/DECISIONS.md` (why things are the way they are), and
`ARCHITECTURE.md` (the design).

## Workflow

- **Branches.** Start each piece of work on a new branch from `main`. Never add
  commits to a branch whose PR is already merged.
- **Design decisions belong to the user.** When there's a real choice
  (interfaces, behaviour, trade-offs), lay out the options with a
  recommendation and wait for the user's decision. Don't just implement.
- **Announce code changes first.** Before changing code, say what will change
  and wait for a go-ahead, so the user can switch models. This doesn't apply to
  questions, reading files, or running checks.
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
- **Read `tasks/heldout/`** while designing tools.
