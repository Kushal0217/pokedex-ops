"""Connection settings. Read from the environment, with defaults for the local docker compose DB."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Minimal .env loader (no extra dependency). Real env vars win."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

AGENT_DSN = os.environ.get("POKEDEX_AGENT_DSN", "postgresql://pokedex_agent:agent@localhost:5433/pokedex")
DBA_DSN = os.environ.get("POKEDEX_DBA_DSN", "postgresql://pokedex_dba:dba@localhost:5433/pokedex")
ADMIN_DSN = os.environ.get("POKEDEX_ADMIN_DSN", "postgresql://postgres:postgres@localhost:5433/pokedex")

# Tool-level limits. Kept small: tool output is context the agent pays for.
STATEMENT_TIMEOUT_MS = int(os.environ.get("POKEDEX_STATEMENT_TIMEOUT_MS", "20000"))
MAX_ROWS = int(os.environ.get("POKEDEX_MAX_ROWS", "50"))

# Write path (apply_index only). Index builds on millions of rows take seconds to
# minutes, so they get a longer limit; they must never queue behind other locks.
WRITE_STATEMENT_TIMEOUT_MS = int(os.environ.get("POKEDEX_WRITE_STATEMENT_TIMEOUT_MS", "300000"))
WRITE_LOCK_TIMEOUT_MS = int(os.environ.get("POKEDEX_WRITE_LOCK_TIMEOUT_MS", "5000"))

# Connection pools (see docs/DECISIONS.md, D11).
READ_POOL_MAX = int(os.environ.get("POKEDEX_READ_POOL_MAX", "4"))
POOL_TIMEOUT_S = float(os.environ.get("POKEDEX_POOL_TIMEOUT_S", "5"))
