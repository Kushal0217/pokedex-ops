"""The two connection paths enforce their guardrails (needs the docker compose Postgres)."""

from __future__ import annotations

import psycopg
import pytest

from server import config, db

pytestmark = pytest.mark.db


def test_read_path_runs_a_select():
    with db.read_only() as cur:
        cur.execute("SELECT count(*) FROM pokemon")
        assert cur.fetchone()[0] > 0


@pytest.mark.parametrize("prepare", [None, False])
def test_read_path_refuses_two_statements_even_if_caller_opts_out(prepare):
    with pytest.raises(psycopg.errors.SyntaxError, match="multiple commands"):
        with db.read_only() as cur:
            cur.execute("SELECT 1; SELECT 2", prepare=prepare)


def test_read_path_refuses_writes():
    with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
        with db.read_only() as cur:
            cur.execute("INSERT INTO types (id, name) VALUES (999, 'test')")


def test_read_path_session_settings():
    with db.read_only() as cur:
        # Compared as intervals: Postgres displays 20000ms as "20s".
        cur.execute("SELECT current_setting('transaction_read_only'),"
                    " current_setting('statement_timeout')::interval = make_interval(secs => %s / 1000.0),"
                    " current_user, current_setting('application_name')", (config.STATEMENT_TIMEOUT_MS,))
        read_only, timeout_matches, user, app = cur.fetchone()
    assert read_only == "on"
    assert timeout_matches
    assert user == "pokedex_agent"
    assert app == db.READ_APP_NAME


def test_read_path_statement_timeout_fires():
    with pytest.raises(psycopg.errors.QueryCanceled):
        with db.read_only() as cur:
            cur.execute("SELECT set_config('statement_timeout', '50ms', true)")
            cur.execute("SELECT pg_sleep(1)")


def test_write_path_can_create_index_concurrently():
    # CONCURRENTLY refuses to run inside a transaction block, so this proves the
    # write path is really autocommit, even through a prepared statement.
    name = "test_db_write_path_idx"
    with db.dba_autocommit() as cur:
        cur.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
        try:
            cur.execute(f"CREATE INDEX CONCURRENTLY {name} ON types (name)")
            cur.execute("SELECT current_user, count(*) FROM pg_indexes WHERE indexname = %s", (name,))
            assert cur.fetchone() == ("pokedex_dba", 1)
        finally:
            cur.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")


def test_write_path_refuses_two_statements():
    with pytest.raises(psycopg.errors.SyntaxError, match="multiple commands"):
        with db.dba_autocommit() as cur:
            cur.execute("SELECT 1; SELECT 2")
