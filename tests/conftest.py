"""Shared test setup: tests marked `db` are skipped, not failed, when Postgres isn't running.

In CI, POKEDEX_REQUIRE_DB=1 turns that skip into a failure, so a broken database
setup can't produce a green run with the database tests silently skipped.
"""

from __future__ import annotations

import os

import psycopg
import pytest

from server import config as cfg

REQUIRE_DB = os.environ.get("POKEDEX_REQUIRE_DB") == "1"


def _db_reachable() -> bool:
    try:
        psycopg.connect(cfg.ADMIN_DSN, connect_timeout=2).close()
        return True
    except psycopg.Error:
        return False


def pytest_collection_modifyitems(config, items):
    db_items = [item for item in items if "db" in item.keywords]
    if not db_items or _db_reachable():
        return
    if REQUIRE_DB:
        pytest.exit("POKEDEX_REQUIRE_DB=1 but Postgres is not reachable on localhost:5433", returncode=1)
    skip = pytest.mark.skip(reason="Postgres is not running on localhost:5433 (docker compose up -d)")
    for item in db_items:
        item.add_marker(skip)
