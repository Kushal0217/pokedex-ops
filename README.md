# pokedex-ops

An MCP server and Agent Skill that let Claude operate a Pokémon Postgres database as
a DBA: diagnosing slow queries, proposing and applying indexes, and checking health.
An eval loop measures how well it does this before and after the tools are redesigned.

> Status: scaffolding. The interfaces are defined and the logic is not implemented yet.
> See [ARCHITECTURE.md](ARCHITECTURE.md).

## Quick start (once implemented)

```sh
docker compose up -d                 # Postgres 17 + hypopg on localhost:5433
python -m venv .venv && .venv/bin/pip install -e ".[dev]"   # Windows: .venv/Scripts/pip
python scripts/seed.py               # snapshot -> reference tables -> workload
pytest
python scripts/eval.py --toolset v1 --split dev
```

The MCP server in `.mcp.json` runs `${POKEDEX_PYTHON:-.venv/bin/python}`, so Linux and
macOS need no setup. On Windows the venv interpreter lives in `.venv/Scripts/`, so set a
user environment variable once (PowerShell or cmd):

```powershell
setx POKEDEX_PYTHON .venv/Scripts/python.exe
```

Then fully restart Claude Code (and the terminal app it runs in) so it picks up the
variable. Check with `claude mcp list`, which should show `pokedex-ops ... ✔ Connected`.
The path is relative, so start Claude Code from the repo root, or use the absolute path to
`python.exe` instead.

## Results

| toolset | task success | tool errors | tokens/task | destructive calls |
|---------|--------------|-------------|-------------|-------------------|
| v1      | –            | –           | –           | –                 |
| v2      | –            | –           | –           | –                 |
