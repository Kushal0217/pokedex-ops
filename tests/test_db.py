"""Tests for server/db.py: guardrail layers 2 to 4, the pools, and the write path.

Tests marked `db` run against the local Postgres (docker compose) and are skipped
when it isn't running. They only read, except the write-path tests, which work on a
scratch table they create and drop themselves.
"""

from __future__ import annotations

import psycopg
import pytest
from psycopg import errors as pgerr

from server import config, db
from server.errors import ToolError

SCRATCH = "zz_pytest_scratch"


@pytest.fixture(autouse=True)
def fresh_pools():
    """Each test starts with no pools, so settings patched by the test take effect."""
    db.close()
    yield
    db.close()


def admin() -> psycopg.Connection:
    return psycopg.connect(config.ADMIN_DSN, autocommit=True)


def warm_read_pool() -> None:
    """Wait for the pool's first connection. Without this, the first call can race the
    pool's background connect and open a second connection, so pids alternate."""
    db._pool("read").wait(timeout=5)


def read_one(sql: str, params=None):
    with db.read_only() as cur:
        return cur.execute(sql, params).fetchone()


# --------------------------------------------------------------------------- read path

@pytest.mark.db
def test_read_returns_rows():
    assert read_one("SELECT name FROM pokemon WHERE id = %s", (25,)) == ("pikachu",)


@pytest.mark.db
def test_read_runs_in_a_read_only_transaction_with_the_configured_timeout(monkeypatch):
    monkeypatch.setattr(config, "STATEMENT_TIMEOUT_MS", 1234)
    assert read_one("SHOW transaction_read_only") == ("on",)
    assert read_one("SHOW statement_timeout") == ("1234ms",)


@pytest.mark.db
def test_a_new_read_call_starts_with_no_hypothetical_indexes(monkeypatch):
    """hypopg indexes outlive ROLLBACK, so a pooled connection must clear them on checkout."""
    monkeypatch.setattr(config, "READ_POOL_MAX", 1)
    db.close()
    with db.read_only() as cur:
        cur.execute("SELECT * FROM hypopg_create_index('CREATE INDEX ON battles (turns)')").fetchall()
        assert cur.execute("SELECT count(*) FROM hypopg()").fetchone()[0] == 1
    assert read_one("SELECT count(*) FROM hypopg()") == (0,)


@pytest.mark.db
def test_a_new_read_call_starts_with_no_hidden_indexes(monkeypatch):
    """hypopg_hide_index() hides a real index from the planner for the whole session, survives
    ROLLBACK, and is not undone by hypopg_reset(). The agent can call it via run_read_query."""
    monkeypatch.setattr(config, "READ_POOL_MAX", 1)
    db.close()
    with db.read_only() as cur:
        cur.execute("SELECT hypopg_hide_index('battles_pkey'::regclass)").fetchall()
        assert cur.execute("SELECT count(*) FROM hypopg_hidden_indexes()").fetchone()[0] == 1
    assert read_one("SELECT count(*) FROM hypopg_hidden_indexes()") == (0,)


@pytest.mark.db
def test_multiple_statements_are_refused_by_postgres():
    """Layer 2: prepared statements hold one statement, whatever sqlguard said."""
    with pytest.raises(ToolError, match="multiple commands"):
        read_one("SELECT 1; SELECT 2")


@pytest.mark.db
@pytest.mark.parametrize("sql", [
    "INSERT INTO types (id, name) VALUES (999, 'x')",
    "UPDATE pokemon SET name = 'x' WHERE id = 25",
    "CREATE TABLE zz_nope (id int)",
])
def test_writes_are_refused_by_the_read_only_transaction(sql):
    """Layer 3."""
    with pytest.raises(ToolError, match="read-only"):
        read_one(sql)


@pytest.mark.db
def test_agent_role_cannot_write_even_in_a_read_write_transaction():
    """Layer 4, independent of db.py: the role itself has no write rights."""
    with psycopg.connect(config.AGENT_DSN, autocommit=True) as conn:
        conn.execute("BEGIN READ WRITE")
        with pytest.raises(pgerr.InsufficientPrivilege):
            conn.execute("INSERT INTO types (id, name) VALUES (999, 'x')")
        conn.execute("ROLLBACK")


@pytest.mark.db
def test_nothing_leaks_between_calls_on_a_pooled_connection():
    """Everything in a call is rolled back, including session settings."""
    warm_read_pool()
    pid1 = read_one("SELECT pg_backend_pid(), set_config('pokedex.test', 'leaked', false)")[0]
    pid2, value = read_one("SELECT pg_backend_pid(), current_setting('pokedex.test', true)")
    assert pid1 == pid2              # same pooled connection...
    assert value in (None, "")       # ...but the setting was rolled back


@pytest.mark.db
def test_connections_are_reused():
    warm_read_pool()
    pids = {read_one("SELECT pg_backend_pid()")[0] for _ in range(5)}
    assert len(pids) == 1


@pytest.mark.db
def test_long_query_is_cancelled_by_statement_timeout(monkeypatch):
    monkeypatch.setattr(config, "STATEMENT_TIMEOUT_MS", 200)
    with pytest.raises(ToolError, match=r"cancelled after 0\.2 s"):
        read_one("SELECT pg_sleep(2)")
    assert read_one("SELECT 1") == (1,)  # the connection is still usable


@pytest.mark.db
def test_sql_errors_are_readable_and_leave_the_pool_usable():
    with pytest.raises(ToolError, match=r"syntax error.*at character"):
        read_one("SELEC 1")
    with pytest.raises(ToolError, match='relation "no_such_table" does not exist'):
        read_one("SELECT * FROM no_such_table")
    assert read_one("SELECT 1") == (1,)


@pytest.mark.db
def test_recovers_when_its_connection_is_killed():
    pid1 = read_one("SELECT pg_backend_pid()")[0]
    with admin() as a:
        a.execute("SELECT pg_terminate_backend(%s)", (pid1,))
    pid2 = read_one("SELECT pg_backend_pid()")[0]   # retried once, transparently
    assert pid2 != pid1


@pytest.mark.db
def test_recovers_when_every_connection_is_killed():
    """What a database restart looks like from the pool's side."""
    read_one("SELECT 1")
    with admin() as a:
        a.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename = 'pokedex_agent'")
    assert read_one("SELECT 1") == (1,)


def test_unreachable_database_gives_a_clear_error(monkeypatch):
    """No database needed: points the pool at a port nothing listens on."""
    monkeypatch.setattr(config, "AGENT_DSN", "postgresql://pokedex_agent:agent@localhost:1/pokedex")
    monkeypatch.setattr(config, "POOL_TIMEOUT_S", 0.5)
    with pytest.raises(ToolError, match="not reachable.*docker compose up -d"):
        read_one("SELECT 1")


# --------------------------------------------------------------------------- write path

@pytest.fixture
def scratch():
    """A small table owned by pokedex_dba, with duplicate values in `v`."""
    with psycopg.connect(config.DBA_DSN, autocommit=True) as c:
        c.execute(f"DROP TABLE IF EXISTS {SCRATCH}")
        c.execute(f"CREATE TABLE {SCRATCH} (id int PRIMARY KEY, v int)")
        c.execute(f"INSERT INTO {SCRATCH} SELECT g, g % 100 FROM generate_series(1, 10000) g")
    yield SCRATCH
    db.close()
    with psycopg.connect(config.DBA_DSN, autocommit=True) as c:
        c.execute(f"DROP TABLE IF EXISTS {SCRATCH}")


def indexes(table: str) -> dict[str, bool]:
    """index name -> valid?"""
    with admin() as a:
        rows = a.execute(
            "SELECT indexrelid::regclass::text, indisvalid FROM pg_index WHERE indrelid = %s::regclass",
            (table,),
        ).fetchall()
    return dict(rows)


@pytest.mark.db
def test_create_index_builds_the_index(scratch):
    result = db.create_index(f"CREATE INDEX CONCURRENTLY zz_pytest_v ON {scratch} (v)")
    assert result["table"] == scratch and result["concurrently"] is True
    assert isinstance(result["elapsed_ms"], int)
    assert indexes(scratch).get("zz_pytest_v") is True


@pytest.mark.db
def test_tool_sessions_are_labelled_in_pg_stat_activity(scratch):
    """D19: a health check can tell the tools' own sessions from everyone else's."""
    assert read_one("SHOW application_name") == (db.APP_NAMES["read"],)
    db.create_index(f"CREATE INDEX CONCURRENTLY zz_pytest_label ON {scratch} (v)")
    with admin() as a:
        names = {r[0] for r in a.execute(
            "SELECT application_name FROM pg_stat_activity WHERE usename = 'pokedex_dba'").fetchall()}
    assert db.APP_NAMES["write"] in names


@pytest.mark.db
@pytest.mark.parametrize("sql", [
    f"DROP TABLE {SCRATCH}",
    f"TRUNCATE {SCRATCH}",
    "SELECT 1",
    f"CREATE INDEX ON {SCRATCH} (v); DROP TABLE {SCRATCH}",
    f"ALTER TABLE {SCRATCH} ADD COLUMN x int",
])
def test_create_index_refuses_anything_else(scratch, sql):
    with pytest.raises(ToolError):
        db.create_index(sql)
    with admin() as a:
        assert a.execute(f"SELECT count(*) FROM {scratch}").fetchone() == (10000,)


@pytest.mark.db
def test_create_index_gives_up_quickly_on_a_held_lock(scratch, monkeypatch):
    monkeypatch.setattr(config, "WRITE_LOCK_TIMEOUT_MS", 300)
    with psycopg.connect(config.DBA_DSN) as holder:          # holds the lock until rollback
        holder.execute(f"LOCK TABLE {scratch} IN ACCESS EXCLUSIVE MODE")
        with pytest.raises(ToolError, match=r"Could not get a lock .* within 0\.3 s.*Nothing was built"):
            db.create_index(f"CREATE INDEX zz_pytest_v ON {scratch} (v)")
        holder.rollback()
    assert "zz_pytest_v" not in indexes(scratch)


@pytest.mark.db
def test_failed_concurrent_build_reports_the_invalid_index_it_left(scratch):
    """A unique index on duplicate values fails mid-build and leaves an INVALID index."""
    with pytest.raises(ToolError, match="INVALID index.*zz_pytest_dup.*needs a human"):
        db.create_index(f"CREATE UNIQUE INDEX CONCURRENTLY zz_pytest_dup ON {scratch} (v)")
    assert indexes(scratch).get("zz_pytest_dup") is False


@pytest.mark.db
def test_write_path_recovers_when_its_connection_is_killed(scratch):
    db.create_index(f"CREATE INDEX zz_pytest_a ON {scratch} (v)")
    with admin() as a:
        a.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                  "WHERE usename = 'pokedex_dba' AND pid <> pg_backend_pid()")
    db.create_index(f"CREATE INDEX zz_pytest_b ON {scratch} (id, v)")   # setup retried, build ran once
    assert {"zz_pytest_a", "zz_pytest_b"} <= set(indexes(scratch))


# --------------------------------------------------------------------------- timeout vs cancel by another session

def _cancel_when_waiting(predicate_sql: str, params: tuple, timeout_s: float = 10.0) -> int:
    """From an admin session, wait until a backend matching predicate_sql shows up,
    then pg_cancel_backend it. Returns the cancelled pid."""
    import time
    deadline = time.monotonic() + timeout_s
    with admin() as a:
        while time.monotonic() < deadline:
            row = a.execute(f"SELECT pid FROM pg_stat_activity WHERE pid <> pg_backend_pid() AND {predicate_sql}",
                            params).fetchone()
            if row:
                a.execute("SELECT pg_cancel_backend(%s)", (row[0],))
                return row[0]
            time.sleep(0.05)
    raise AssertionError("the backend to cancel never appeared")


def test_timed_out_rule():
    canceled = pgerr.QueryCanceled("canceling statement")
    assert db._timed_out(canceled, None, 1000)          # unknown elapsed: assume the timeout
    assert db._timed_out(canceled, 1000.0, 1000)
    assert not db._timed_out(canceled, 999.0, 1000)
    assert not db._timed_out(pgerr.SyntaxError("x"), 5000.0, 1000)


@pytest.mark.db
def test_a_cancel_from_another_session_is_not_called_a_timeout():
    """Regression: every QueryCanceled used to be reported as statement_timeout."""
    import threading
    t = threading.Thread(target=_cancel_when_waiting,
                         args=("query LIKE %s AND state = 'active'", ("%pg_sleep(5)%",)))
    t.start()
    with pytest.raises(ToolError, match="cancelled by another session") as err:
        read_one("SELECT pg_sleep(5)")
    t.join()
    assert "statement_timeout" not in str(err.value)


@pytest.mark.db
def test_a_cancelled_index_build_is_not_called_a_timeout(scratch, monkeypatch):
    """The build waits on a held lock; another session cancels it before any limit."""
    import threading
    monkeypatch.setattr(config, "WRITE_LOCK_TIMEOUT_MS", 15000)
    with psycopg.connect(config.DBA_DSN) as holder:
        holder.execute(f"LOCK TABLE {scratch} IN ACCESS EXCLUSIVE MODE")
        t = threading.Thread(target=_cancel_when_waiting,
                             args=("usename = 'pokedex_dba' AND wait_event_type = 'Lock'", ()))
        t.start()
        with pytest.raises(ToolError, match="index build was cancelled by another session"):
            db.create_index(f"CREATE INDEX zz_pytest_v ON {scratch} (v)")
        t.join()
        holder.rollback()
