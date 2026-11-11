"""Tests for the tool handlers in server/tools.py: describe_schema and run_read_query.

The `db` tests run against the seeded database at any scale, so they compare
against live counts rather than fixed numbers.
"""

from __future__ import annotations

import datetime
import decimal

import psycopg
import pytest

from server import config, db, tools
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
