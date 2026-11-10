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

The MCP server in `.mcp.json` runs `.venv/bin/python` by default. On Windows, set
`POKEDEX_PYTHON=.venv/Scripts/python.exe` in your environment before starting Claude Code.

## Results

| toolset | task success | tool errors | tokens/task | destructive calls |
|---------|--------------|-------------|-------------|-------------------|
| v1      | –            | –           | –           | –                 |
| v2      | –            | –           | –           | –                 |
