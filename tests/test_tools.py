"""Tests for the tool handlers in server/tools.py: describe_schema and run_read_query.

The `db` tests run against the seeded database at any scale, so they compare
against live counts rather than fixed numbers.
"""

from __future__ import annotations

import datetime
import decimal
import threading
import time

import psycopg
import pytest

from server import config, db, sqlguard, tools
from server.errors import ToolError


@pytest.fixture(autouse=True)
def fresh_pools():
    db.close()
    yield
    db.close()


def exact_count(table: str) -> int:
    with psycopg.connect(config.ADMIN_DSN) as c:
        return c.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


# --------------------------------------------------------------------------- value conversion (no database)

@pytest.mark.parametrize("value, expected", [
    (None, None), (True, True), (7, 7), (1.5, 1.5),
    (decimal.Decimal("32.48"), 32.48),
    (decimal.Decimal("NaN"), "NaN"),
    (float("inf"), "inf"),
    (datetime.datetime(2023, 2, 17, 19, 54, 10, tzinfo=datetime.timezone.utc), "2023-02-17T19:54:10+00:00"),
    (datetime.date(2024, 1, 2), "2024-01-02"),
    (b"\x01\xff", "\\x01ff"),
    ([1, decimal.Decimal("2.5")], [1, 2.5]),
    ({"a": decimal.Decimal("1")}, {"a": 1.0}),
    (datetime.timedelta(seconds=90), "0:01:30"),
])
def test_jsonable(value, expected):
    assert tools._jsonable(value) == expected


def test_long_values_are_cut(monkeypatch):
    monkeypatch.setattr(config, "MAX_VALUE_CHARS", 10)
    assert tools._jsonable("x" * 10) == "x" * 10
    assert tools._jsonable("x" * 25) == "x" * 10 + "… [cut: 25 chars]"


# --------------------------------------------------------------------------- describe_schema

@pytest.mark.db
def test_describe_schema_lists_every_table():
    tables = {t["name"]: t for t in tools.describe_schema()["tables"]}
    assert {"pokemon", "battles", "encounters", "team_members", "ops_audit_log"} <= set(tables)
    assert not any(name.startswith("pg_") for name in tables)


@pytest.mark.db
def test_describe_schema_one_table():
    (t,) = tools.describe_schema("battles")["tables"]
    assert t["name"] == "battles"
    assert t["rows_estimate"] == exact_count("battles")   # the seed ANALYZEs, so the estimate is exact
    assert t["size"].endswith(("kB", "MB", "GB"))
    assert t["columns"][0] == "id bigint not null"
    assert "played_at timestamp with time zone not null" in t["columns"]
    assert t["indexes"] == [{
        "name": "battles_pkey",
        "definition": "CREATE UNIQUE INDEX battles_pkey ON public.battles USING btree (id)",
        "valid": True,
        "size": t["indexes"][0]["size"],
    }]


@pytest.mark.db
def test_describe_schema_nullable_columns_say_so():
    (t,) = tools.describe_schema("team_members")["tables"]
    assert "nickname text" in t["columns"]


@pytest.mark.db
@pytest.mark.parametrize("name", ["public.battles", ' "battles" '])
def test_describe_schema_accepts_qualified_or_quoted_names(name):
    assert tools.describe_schema(name)["tables"][0]["name"] == "battles"


@pytest.mark.db
def test_describe_schema_unknown_table_lists_the_real_ones():
    with pytest.raises(ToolError, match=r"No table named 'battle'\. Tables: .*battles.*trainers"):
        tools.describe_schema("battle")


@pytest.mark.db
def test_describe_schema_shows_invalid_indexes():
    """A failed CREATE INDEX CONCURRENTLY leaves an INVALID index; the agent must see it."""
    with psycopg.connect(config.DBA_DSN, autocommit=True) as c:
        c.execute("DROP TABLE IF EXISTS zz_pytest_tools")
        c.execute("CREATE TABLE zz_pytest_tools (v int)")
        c.execute("INSERT INTO zz_pytest_tools SELECT g % 3 FROM generate_series(1, 100) g")
        with pytest.raises(psycopg.errors.UniqueViolation):
            c.execute("CREATE UNIQUE INDEX CONCURRENTLY zz_pytest_dup ON zz_pytest_tools (v)")
    try:
        (t,) = tools.describe_schema("zz_pytest_tools")["tables"]
        assert [(i["name"], i["valid"]) for i in t["indexes"]] == [("zz_pytest_dup", False)]
    finally:
        db.close()
        with psycopg.connect(config.DBA_DSN, autocommit=True) as c:
            c.execute("DROP TABLE IF EXISTS zz_pytest_tools")


# --------------------------------------------------------------------------- run_read_query

@pytest.mark.db
def test_run_read_query_returns_columns_and_rows():
    r = tools.run_read_query("SELECT id, name FROM pokemon WHERE id IN (1, 25) ORDER BY id")
    assert r["columns"] == ["id", "name"]
    assert r["rows"] == [[1, "bulbasaur"], [25, "pikachu"]]
    assert r["row_count"] == 2 and r["truncated"] is False
    assert isinstance(r["elapsed_ms"], float)


@pytest.mark.db
def test_run_read_query_stops_at_the_row_limit_without_reading_everything():
    r = tools.run_read_query("SELECT * FROM encounters")      # 500k+ rows
    assert r["row_count"] == config.MAX_ROWS and len(r["rows"]) == config.MAX_ROWS
    assert r["truncated"] is True
    assert r["elapsed_ms"] < 1000   # LIMIT reaches Postgres; the full table isn't transferred


@pytest.mark.db
def test_run_read_query_exactly_at_the_limit_is_not_truncated():
    r = tools.run_read_query(f"SELECT g FROM generate_series(1, {config.MAX_ROWS}) g")
    assert r["row_count"] == config.MAX_ROWS and r["truncated"] is False


@pytest.mark.db
def test_run_read_query_keeps_order():
    r = tools.run_read_query("SELECT id FROM pokemon ORDER BY id DESC")
    ids = [row[0] for row in r["rows"]]
    assert ids == sorted(ids, reverse=True)


@pytest.mark.db
@pytest.mark.parametrize("sql", [
    "SELECT 1;",
    "SELECT 1 -- trailing comment",
    "SELECT 1; -- comment after the terminator",
    "/* leading */ SELECT 1",
    "TABLE types",
    "VALUES (1)",
    "WITH a AS (SELECT 1 AS n) SELECT n FROM a",
    "(SELECT 1) UNION (SELECT 2)",
    "SELECT 1 AS a, 2 AS a",
])
def test_run_read_query_handles_every_read_form(sql):
    assert tools.run_read_query(sql)["row_count"] >= 1


@pytest.mark.db
def test_run_read_query_runs_show_unwrapped():
    r = tools.run_read_query("SHOW statement_timeout")
    assert r["columns"] == ["statement_timeout"]
    assert r["rows"] == [[f"{config.STATEMENT_TIMEOUT_MS // 1000}s"]]


@pytest.mark.db
def test_run_read_query_converts_values():
    r = tools.run_read_query(
        "SELECT round(2.345, 2) AS d, timestamptz '2024-01-02 03:04:05+00' AS t, NULL AS n, repeat('x', 300) AS long"
    )
    d, t, n, long = r["rows"][0]
    assert d == 2.35 and t == "2024-01-02T03:04:05+00:00" and n is None
    assert long.endswith("… [cut: 300 chars]") and len(long) < 300


@pytest.mark.db
@pytest.mark.parametrize("sql, message", [
    ("DELETE FROM battles", "DELETE"),
    ("EXPLAIN SELECT 1", "explain_query"),
    ("CREATE INDEX ON battles (winner_team_id)", "apply_index"),
    ("SELECT 1; SELECT 2", "one statement"),
])
def test_run_read_query_refuses_with_a_reason(sql, message):
    with pytest.raises(ToolError, match=message):
        tools.run_read_query(sql)


@pytest.mark.db
def test_run_read_query_error_positions_point_into_the_agents_sql():
    """The wrapper adds text in front; error positions must still match what the agent sent."""
    with pytest.raises(ToolError, match=r'column "nope" does not exist \(at character 8\)'):
        tools.run_read_query("SELECT nope FROM pokemon")


# --------------------------------------------------------------------------- explain_query

@pytest.mark.db
def test_explain_query_returns_the_raw_analyzed_plan():
    r = tools.explain_query("SELECT * FROM pokemon WHERE id = 25")
    assert r["analyzed"] is True and "note" not in r
    assert isinstance(r["plan"], str) and "\n" in r["plan"]
    assert "actual time=" in r["plan"] and "Buffers:" in r["plan"] and "Execution Time:" in r["plan"]


@pytest.mark.db
@pytest.mark.parametrize("sql", [
    "SELECT 1 FROM pokemon;",
    "SELECT 1 FROM pokemon -- trailing comment",
    "SELECT 1 FROM pokemon; -- comment after the terminator",
])
def test_explain_query_handles_terminators_and_comments(sql):
    r = tools.explain_query(sql)
    assert r["analyzed"] is True and "actual time=" in r["plan"]


def count_explain_runs(monkeypatch) -> list[str]:
    """Record the options of each EXPLAIN that explain_query runs."""
    runs: list[str] = []
    real = tools._explain

    def spy(body: str, options: str) -> str:
        runs.append(options)
        return real(body, options)

    monkeypatch.setattr(tools, "_explain", spy)
    return runs


@pytest.mark.db
def test_explain_query_falls_back_to_plain_explain_on_timeout(monkeypatch):
    monkeypatch.setattr(config, "STATEMENT_TIMEOUT_MS", 200)
    runs = count_explain_runs(monkeypatch)
    r = tools.explain_query("SELECT count(*) FROM generate_series(1, 1000000000)")   # slow at any scale
    assert runs == ["(ANALYZE, BUFFERS)", ""]
    assert r["analyzed"] is False
    assert "statement_timeout" in r["note"] and "0.2 s" in r["note"]
    assert "Aggregate" in r["plan"]
    assert "actual" not in r["plan"] and "Buffers" not in r["plan"]


@pytest.mark.db
@pytest.mark.parametrize("sql", ["SELECT nope FROM pokemon", "SELECT 1/0"])
def test_explain_query_does_not_fall_back_on_other_errors(monkeypatch, sql):
    runs = count_explain_runs(monkeypatch)
    with pytest.raises(ToolError):
        tools.explain_query(sql)
    assert runs == ["(ANALYZE, BUFFERS)"]


@pytest.mark.db
def test_explain_query_does_not_fall_back_when_another_session_cancels(monkeypatch):
    """A cancel from another session is the same error as a timeout, but someone
    wanted the query stopped: report it, don't run a second query (review finding)."""
    runs = count_explain_runs(monkeypatch)
    cancelled: list[bool] = []

    def cancel_when_running() -> None:
        with psycopg.connect(config.ADMIN_DSN, autocommit=True) as a:
            for _ in range(50):
                rows = a.execute(
                    "SELECT pg_cancel_backend(pid) FROM pg_stat_activity "
                    "WHERE query LIKE %s AND pid <> pg_backend_pid()", ("%pg_sleep(5)%",)).fetchall()
                if any(ok for (ok,) in rows):
                    cancelled.append(True)
                    return
                time.sleep(0.1)

    canceller = threading.Thread(target=cancel_when_running)
    canceller.start()
    started = time.monotonic()
    with pytest.raises(ToolError, match="cancel"):
        tools.explain_query("SELECT pg_sleep(5)")
    canceller.join()
    assert cancelled and runs == ["(ANALYZE, BUFFERS)"]
    assert time.monotonic() - started < 4   # stopped by the cancel, not by finishing


@pytest.mark.db
@pytest.mark.parametrize("sql, message", [
    ("EXPLAIN SELECT 1", "adds EXPLAIN itself"),
    ("CREATE INDEX ON battles (winner_team_id)", "apply_index"),
    ("DELETE FROM battles", "DELETE"),
    ("SELECT 1; SELECT 2", "one statement"),
    ("SHOW work_mem", "run_read_query"),
])
def test_explain_query_refuses_with_a_reason(sql, message):
    with pytest.raises(ToolError, match=message):
        tools.explain_query(sql)


@pytest.mark.db
def test_explain_query_error_positions_point_into_the_agents_sql():
    with pytest.raises(ToolError, match=r'column "nope" does not exist \(at character 8\)'):
        tools.explain_query("SELECT nope FROM pokemon")


@pytest.mark.db
def test_explain_analyze_cannot_write_even_if_sqlguard_lets_a_write_through(monkeypatch):
    """EXPLAIN ANALYZE really executes its query. If sqlguard ever misclassified a
    write as a read, the read-only transaction (layer 3) must still refuse it."""
    monkeypatch.setattr(sqlguard, "classify", lambda sql: sqlguard.Verdict("read"))
    before = exact_count("types")
    with pytest.raises(ToolError, match="Refused"):
        tools.explain_query("INSERT INTO types (id, name) VALUES (9999, 'zz_pytest')")
    assert exact_count("types") == before


# --------------------------------------------------------------------------- apply_index

SCRATCH = "zz_pytest_apply"


@pytest.fixture
def scratch():
    """A small table owned by pokedex_dba, with duplicate values in `v`. Never build on the real tables."""
    with psycopg.connect(config.DBA_DSN, autocommit=True) as c:
        c.execute(f"DROP TABLE IF EXISTS {SCRATCH}")
        c.execute(f"CREATE TABLE {SCRATCH} (id int PRIMARY KEY, v int)")
        c.execute(f"INSERT INTO {SCRATCH} SELECT g, g % 100 FROM generate_series(1, 10000) g")
    yield SCRATCH
    db.close()
    with psycopg.connect(config.DBA_DSN, autocommit=True) as c:
        c.execute(f"DROP TABLE IF EXISTS {SCRATCH}")


def spy_create_index(monkeypatch) -> list[str]:
    """Record the SQL that apply_index hands to db.create_index."""
    seen: list[str] = []
    real = db.create_index

    def spy(sql: str):
        seen.append(sql)
        return real(sql)

    monkeypatch.setattr(db, "create_index", spy)
    return seen


@pytest.mark.db
def test_apply_index_adds_concurrently_and_finds_the_generated_name(scratch, monkeypatch):
    seen = spy_create_index(monkeypatch)
    r = tools.apply_index(f"CREATE INDEX ON {scratch} (v);")
    assert seen == [f"CREATE INDEX CONCURRENTLY ON {scratch} (v)"]
    assert set(r) == {"created", "index", "table", "definition", "valid", "size", "elapsed_ms",
                      "concurrently_added", "note"}
    assert r["created"] is True and r["index"] == f"{scratch}_v_idx" and r["table"] == scratch
    assert r["valid"] is True and r["concurrently_added"] is True
    assert r["definition"].startswith(f"CREATE INDEX {scratch}_v_idx ON public.{scratch}")
    assert r["size"].endswith(("kB", "MB", "bytes")) and isinstance(r["elapsed_ms"], int)
    assert "CONCURRENTLY was added" in r["note"]


@pytest.mark.db
def test_apply_index_with_a_name_and_concurrently_already_present(scratch, monkeypatch):
    seen = spy_create_index(monkeypatch)
    sql = f"create index concurrently zz_pytest_named on {scratch} (v)"
    r = tools.apply_index(sql)
    assert seen == [sql]
    assert r["index"] == "zz_pytest_named" and r["concurrently_added"] is False and "note" not in r
    assert set(r) == {"created", "index", "table", "definition", "valid", "size", "elapsed_ms",
                      "concurrently_added"}


@pytest.mark.db
def test_apply_index_if_not_exists_on_an_existing_name_builds_nothing(scratch):
    tools.apply_index(f"CREATE INDEX zz_pytest_named ON {scratch} (v)")
    r = tools.apply_index(f"CREATE INDEX IF NOT EXISTS zz_pytest_named ON {scratch} (v)")
    assert r["created"] is False and r["table"] == scratch
    assert "already exists" in r["note"] and "index" not in r


@pytest.mark.db
@pytest.mark.parametrize("sql, message", [
    ("SELECT 1", "run_read_query"),
    (f"DROP TABLE {SCRATCH}", "DROP"),
])
def test_apply_index_refuses_without_touching_the_database(scratch, monkeypatch, sql, message):
    seen = spy_create_index(monkeypatch)
    with pytest.raises(ToolError, match=message):
        tools.apply_index(sql)
    assert seen == []


@pytest.mark.db
def test_apply_index_unique_on_duplicates_fails_with_a_tool_error(scratch):
    with pytest.raises(ToolError, match="zz_pytest_dup"):
        tools.apply_index(f"CREATE UNIQUE INDEX zz_pytest_dup ON {scratch} (v)")


@pytest.mark.db
def test_apply_index_accepts_leading_semicolons_and_a_schema(scratch):
    r = tools.apply_index(f";CREATE INDEX zz_pytest_semi ON public.{scratch} (v)")
    assert r["created"] is True and r["index"] == "zz_pytest_semi" and r["concurrently_added"] is True


@pytest.mark.db
def test_apply_index_refuses_a_table_it_cannot_find_before_building(monkeypatch):
    seen = spy_create_index(monkeypatch)
    with pytest.raises(ToolError, match="describe_schema"):
        tools.apply_index("CREATE INDEX ON zz_pytest_no_such_table (v)")
    assert seen == []


@pytest.mark.db
def test_apply_index_says_so_when_another_session_added_an_index_too(scratch, monkeypatch):
    """Another session's index appearing during the build must not be reported as ours."""
    real = tools._index_names
    calls = iter([lambda t: real(t), lambda t: real(t) | {"zz_someone_elses"}])
    monkeypatch.setattr(tools, "_index_names", lambda t: next(calls)(t))
    with pytest.raises(ToolError, match="zz_someone_elses"):
        tools.apply_index(f"CREATE INDEX zz_pytest_mine ON {scratch} (v)")
