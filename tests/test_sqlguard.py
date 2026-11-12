"""Unit tests for server.sqlguard.classify (guardrail layer 1).

Pure: no database. These pin down the rules in classify()'s docstring:
  * comments and quoted literals are ignored when looking for keywords and ';'
  * exactly one statement per call
  * SELECT / WITH / VALUES / TABLE / SHOW are reads unless they write or have side effects
  * CREATE [UNIQUE] INDEX [CONCURRENTLY] ... ON <table> (...) is create_index
  * everything else is forbidden, with a reason the agent can act on
"""

from __future__ import annotations

import pytest

from server.sqlguard import Verdict, classify


def kind(sql: str) -> str:
    return classify(sql).kind


# --------------------------------------------------------------------------- reads

@pytest.mark.parametrize("sql", [
    "SELECT 1",
    "select * from pokemon",
    "  \n\tSELECT name FROM pokemon WHERE id = 25  ",
    "SELECT 1;",
    "SELECT 1 ;  \n",
    "SELECT count(*) FROM battles b JOIN trainers t ON t.id = b.winner_id GROUP BY t.id",
    "WITH top AS (SELECT * FROM trainers LIMIT 10) SELECT * FROM top",
    "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r WHERE n < 5) SELECT * FROM r",
    "VALUES (1, 'a'), (2, 'b')",
    "TABLE pokemon",
    "SHOW work_mem",
    "SHOW ALL",
    "(SELECT 1) UNION (SELECT 2)",
    "SELECT lower(name), pg_size_pretty(pg_total_relation_size('battles')) FROM pokemon",
    "SELECT * FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 5",
    "SELECT updated_at, deleted, created_by FROM trainers",   # keywords as prefixes only
    "SELECT setval FROM t",                                   # name without a call
    "SELECT 'café' AS ünïcode",
])
def test_reads(sql):
    v = classify(sql)
    assert v == Verdict("read")


# ---------------------------------------------- literals and comments are ignored

@pytest.mark.parametrize("sql", [
    "SELECT 'DROP TABLE pokemon'",
    "SELECT 'a;b'",
    "SELECT 'it''s; DELETE FROM pokemon'",
    r"SELECT E'it\'s; DELETE FROM pokemon'",
    "SELECT $$; DELETE FROM pokemon $$",
    "SELECT $tag$ ; DROP TABLE x; $not$ $tag$",
    'SELECT 1 AS "a;b"',
    'SELECT "delete", "update" FROM t',
    "SELECT 1 -- ; DROP TABLE pokemon",
    "SELECT 1; -- trailing comment",
    "SELECT 1 /* ; DROP TABLE pokemon */",
    "SELECT 1 /* outer /* nested */ ; DROP TABLE pokemon */",
    "/* leading */ SELECT 1",
    "-- leading\nSELECT 1",
])
def test_literals_and_comments_are_ignored(sql):
    assert kind(sql) == "read"


@pytest.mark.parametrize("sql", [
    "SELECT 'unterminated",
    "SELECT $$ unterminated",
    "SELECT 1 /* unterminated",
    'SELECT "unterminated',
])
def test_unterminated_literals_are_forbidden(sql):
    v = classify(sql)
    assert v.kind == "forbidden"
    assert v.reason


# --------------------------------------------------------------- one statement only

@pytest.mark.parametrize("sql", [
    "SELECT 1; SELECT 2",
    "SELECT 1; DROP TABLE pokemon",
    "SELECT 1;DELETE FROM battles",
    "SELECT 1; /* sneaky */ SELECT 2",
    "CREATE INDEX ON battles (winner_id); DROP TABLE battles",
])
def test_multiple_statements_are_forbidden(sql):
    v = classify(sql)
    assert v.kind == "forbidden"
    assert "one statement" in v.reason.lower()


@pytest.mark.parametrize("sql", ["", "   ", ";", " ; ; ", "-- only a comment", "/* only */"])
def test_empty_input_is_forbidden(sql):
    v = classify(sql)
    assert v.kind == "forbidden"
    assert v.reason


# --------------------------------------------------------------- writes and DDL

@pytest.mark.parametrize("sql", [
    "INSERT INTO trainers (name) VALUES ('x')",
    "UPDATE trainers SET name = 'x'",
    "DELETE FROM battles",
    "MERGE INTO t USING s ON t.id = s.id WHEN MATCHED THEN DELETE",
    "TRUNCATE battles",
    "DROP TABLE battles",
    "DROP INDEX battles_winner_idx",
    "ALTER TABLE battles ADD COLUMN x int",
    "CREATE TABLE x (id int)",
    "CREATE TABLE x AS SELECT * FROM battles",
    "CREATE MATERIALIZED VIEW mv AS SELECT 1",
    "CREATE FUNCTION f() RETURNS int AS $$ SELECT 1 $$ LANGUAGE sql",
    "CREATE EXTENSION dblink",
    "REFRESH MATERIALIZED VIEW mv",
    "GRANT ALL ON battles TO public",
    "REVOKE SELECT ON battles FROM pokedex_agent",
    "COPY battles TO '/tmp/x'",
    "VACUUM battles",
    "ANALYZE battles",
    "REINDEX TABLE battles",
    "CLUSTER battles",
    "LOCK TABLE battles",
    "CALL some_proc()",
    "DO $$ BEGIN DELETE FROM battles; END $$",
    "BEGIN",
    "COMMIT",
    "ROLLBACK",
    "SET default_transaction_read_only = off",
    "RESET ALL",
    "SET ROLE postgres",
    "PREPARE p AS SELECT 1",
    "EXECUTE p",
    "DISCARD ALL",
    "LISTEN chan",
    "NOTIFY chan",
    "COMMENT ON TABLE battles IS 'x'",
])
def test_writes_and_other_statements_are_forbidden(sql):
    v = classify(sql)
    assert v.kind == "forbidden"
    assert v.reason


@pytest.mark.parametrize("sql", [
    "WITH d AS (DELETE FROM battles RETURNING *) SELECT * FROM d",
    "WITH u AS (UPDATE trainers SET name = 'x' RETURNING id) SELECT count(*) FROM u",
    "WITH i AS (INSERT INTO trainers (name) VALUES ('x') RETURNING id) SELECT * FROM i",
    "WITH x AS (SELECT 1) INSERT INTO trainers (name) SELECT 'x' FROM x",
    "WITH x AS (SELECT 1) DELETE FROM battles",
])
def test_data_modifying_ctes_are_forbidden(sql):
    assert kind(sql) == "forbidden"


@pytest.mark.parametrize("sql", [
    "SELECT * FROM trainers FOR UPDATE",
    "SELECT * FROM trainers FOR NO KEY UPDATE",
    "SELECT * FROM trainers FOR SHARE",
    "SELECT * FROM trainers FOR KEY SHARE",
    "SELECT * FROM trainers t WHERE id = 1 FOR UPDATE OF t SKIP LOCKED",
])
def test_row_locking_is_forbidden(sql):
    assert kind(sql) == "forbidden"


@pytest.mark.parametrize("sql", [
    "SELECT * INTO new_table FROM pokemon",
    "SELECT name INTO TEMP t FROM pokemon",
])
def test_select_into_is_forbidden(sql):
    assert kind(sql) == "forbidden"


@pytest.mark.parametrize("sql", [
    "SELECT pg_terminate_backend(123)",
    "SELECT pg_cancel_backend(123)",
    "select PG_TERMINATE_BACKEND (pid) from pg_stat_activity",
    "SELECT pg_catalog.setval('s', 1)",
    "SELECT nextval('trainers_id_seq')",
    "SELECT set_config('default_transaction_read_only', 'off', false)",
    "SELECT pg_advisory_lock(1)",
    "SELECT pg_advisory_xact_lock(1)",
    "SELECT lo_import('/etc/passwd')",
    "SELECT dblink_exec('dbname=pokedex', 'DROP TABLE battles')",
    "SELECT pg_reload_conf()",
    "SELECT pg_notify('chan', 'x')",
    'SELECT "setval"(\'s\', 1)',
    "WITH x AS (SELECT nextval('s')) SELECT * FROM x",
])
def test_side_effecting_functions_are_forbidden(sql):
    v = classify(sql)
    assert v.kind == "forbidden"
    assert v.reason


# --------------------------------------------------------------- CREATE INDEX

@pytest.mark.parametrize("sql, table, concurrently", [
    ("CREATE INDEX ON battles (winner_id)", "battles", False),
    ("CREATE INDEX battles_winner_idx ON battles (winner_id)", "battles", False),
    ("CREATE INDEX CONCURRENTLY battles_winner_idx ON battles (winner_id)", "battles", True),
    ("create unique index concurrently on trainers (name)", "trainers", True),
    ("CREATE INDEX IF NOT EXISTS ix ON battles USING btree (winner_id, started_at DESC)", "battles", False),
    ("CREATE INDEX ix ON ONLY battles (winner_id)", "battles", False),
    ("CREATE INDEX ix ON public.battles (winner_id)", "public.battles", False),
    ('CREATE INDEX "Ix" ON "Battles" (lower(name))', "Battles", False),
    ("CREATE INDEX ON encounters (trainer_id) INCLUDE (pokemon_id) WHERE caught", "encounters", False),
    ("CREATE INDEX ON pokemon (lower(name));", "pokemon", False),
])
def test_create_index(sql, table, concurrently):
    v = classify(sql)
    assert v.kind == "create_index"
    assert v.table == table
    assert v.concurrently is concurrently


@pytest.mark.parametrize("sql", [
    "CREATE INDEX",
    "CREATE INDEX ix",
    "CREATE INDEX ix ON",
    "CREATE INDEX ix ON battles",            # no column list
    "CREATE INDEX ix battles (winner_id)",   # no ON
    "CREATE INDEX ON battles (winner_id) WHERE nextval('s') > 0",
])
def test_malformed_or_unsafe_create_index_is_forbidden(sql):
    v = classify(sql)
    assert v.kind == "forbidden"
    assert v.reason


# --------------------------------------------------------------- reasons are actionable

def test_explain_points_to_explain_tool():
    v = classify("EXPLAIN ANALYZE SELECT * FROM battles")
    assert v.kind == "forbidden"
    assert "explain_query" in v.reason


def test_drop_index_reason_mentions_only_create_index_allowed():
    v = classify("DROP INDEX battles_winner_idx")
    assert "CREATE INDEX" in v.reason


def test_write_reason_names_the_statement():
    assert "DELETE" in classify("DELETE FROM battles").reason


def test_non_forbidden_verdicts_have_no_reason():
    assert classify("SELECT 1").reason == ""
    assert classify("CREATE INDEX ON battles (winner_id)").reason == ""


# --------------------------------------------------------------- robustness

@pytest.mark.parametrize("sql", ["'", '"', "$", "$$", "/*", "*/", "--", "\x00", "(((", ")", "$1", "E'"])
def test_never_raises_on_garbage(sql):
    assert isinstance(classify(sql), Verdict)


# --------------------------------------------------------------- helpers for callers

from server.sqlguard import leading_keyword, strip_terminator  # noqa: E402


@pytest.mark.parametrize("sql, expected", [
    ("SELECT 1", "SELECT 1"),
    ("SELECT 1;", "SELECT 1"),
    ("SELECT 1 ;  \n", "SELECT 1 "),
    ("SELECT ';' ; -- trailing", "SELECT ';' "),
    ("SELECT $$;$$;", "SELECT $$;$$"),
    ('SELECT 1 AS "a;b";', 'SELECT 1 AS "a;b"'),
    ("SELECT 1 -- a comment; not a terminator", "SELECT 1 -- a comment; not a terminator"),
    ("/* ; */ SELECT 1;", "/* ; */ SELECT 1"),
    (";SELECT 1", "SELECT 1"),                 # classify() ignores empty statements
    (";; SELECT 1; ;", " SELECT 1"),
])
def test_strip_terminator(sql, expected):
    assert strip_terminator(sql) == expected


@pytest.mark.parametrize("sql, expected", [
    ("SELECT 1", "select"),
    ("  -- comment\n show work_mem", "show"),
    ("((SELECT 1))", "select"),
    ("/* x */ WITH a AS (SELECT 1) SELECT * FROM a", "with"),
    ("", None),
    ("'unterminated", None),
    ("42", None),
])
def test_leading_keyword(sql, expected):
    assert leading_keyword(sql) == expected


# --------------------------------------------------------------- add_concurrently

from server.sqlguard import add_concurrently  # noqa: E402


@pytest.mark.parametrize("sql, expected", [
    ("CREATE INDEX ON t (a)", "CREATE INDEX CONCURRENTLY ON t (a)"),
    ("CREATE INDEX idx ON t (a)", "CREATE INDEX CONCURRENTLY idx ON t (a)"),
    ("CREATE UNIQUE INDEX idx ON t (a)", "CREATE UNIQUE INDEX CONCURRENTLY idx ON t (a)"),
    ("CREATE INDEX IF NOT EXISTS idx ON t (a)", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx ON t (a)"),
    ("CREATE INDEX CONCURRENTLY idx ON t (a)", "CREATE INDEX CONCURRENTLY idx ON t (a)"),
    ("create index concurrently idx on t (a)", "create index concurrently idx on t (a)"),
    ("CREATE /* x */ UNIQUE -- y\n INDEX idx ON t (a)",
     "CREATE /* x */ UNIQUE -- y\n INDEX CONCURRENTLY idx ON t (a)"),
    ("/* index */ CREATE -- INDEX\n INDEX idx ON t (a)",
     "/* index */ CREATE -- INDEX\n INDEX CONCURRENTLY idx ON t (a)"),
    ("create unique index idx on t (a)", "create unique index CONCURRENTLY idx on t (a)"),
    ("CrEaTe InDeX idx ON t (a)", "CrEaTe InDeX CONCURRENTLY idx ON t (a)"),
    ('CREATE INDEX "index" ON t (a)', 'CREATE INDEX CONCURRENTLY "index" ON t (a)'),
    ('CREATE INDEX "My Idx" ON "T" (a)', 'CREATE INDEX CONCURRENTLY "My Idx" ON "T" (a)'),
    ("CREATE INDEX idx ON t (a);", "CREATE INDEX CONCURRENTLY idx ON t (a);"),
])
def test_add_concurrently(sql, expected):
    out = add_concurrently(sql)
    assert out == expected
    verdict = classify(out)
    assert verdict.kind == "create_index" and verdict.concurrently is True
