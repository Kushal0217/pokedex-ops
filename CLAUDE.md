# CLAUDE.md

Read these first: `docs/PROGRESS.md` (where things stand, what's open, what's
next), `docs/DECISIONS.md` (why things are the way they are), and
`ARCHITECTURE.md` (the design).

## Workflow

- **Branches.** Start each piece of work on a new branch from `main`. Never add
  commits to a branch whose PR is already merged.
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

The `pokedex-ops` cloud environment allows the hosts needed below. The Docker
service does not start by itself:

```sh
pgrep dockerd >/dev/null || (setsid nohup dockerd >/tmp/dockerd.log 2>&1 < /dev/null &)
scripts/build_db_image.sh        # only if the image isn't built yet; plain `docker compose build` on a laptop
docker compose up -d             # Postgres 17 + hypopg on localhost:5433
python scripts/seed.py           # about 31 s and 1.0 GB at full scale; add --scale 0.1 for a quick one
```

## Tests

`pytest` runs everything. CI runs `pytest -m "not db"`. Mark tests that need
Postgres with `@pytest.mark.db`.

## Don't

- **Re-fetch the PokeAPI snapshot** (`seed.py --refresh`) unless the user wants
  a deliberate data update (DECISIONS D7).
- **Tune `server/toolsets/v1.py` against eval results.** Improvements go into v2.
- **Read `tasks/heldout/`** while designing tools.
