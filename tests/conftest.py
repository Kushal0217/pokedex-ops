"""Shared test setup: tests marked `db` are skipped, not failed, when Postgres isn't running."""

from __future__ import annotations

import psycopg
import pytest

from server import config as cfg


def _db_reachable() -> bool:
    try:
        psycopg.connect(cfg.ADMIN_DSN, connect_timeout=2).close()
        return True
    except psycopg.Error:
        return False


def pytest_collection_modifyitems(config, items):
    db_items = [item for item in items if "db" in item.keywords]
    if db_items and not _db_reachable():
        skip = pytest.mark.skip(reason="Postgres is not running on localhost:5433 (docker compose up -d)")
        for item in db_items:
            item.add_marker(skip)
