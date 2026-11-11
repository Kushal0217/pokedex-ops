"""Unit tests for scripts/seed.py (no network, no database) and the committed snapshot."""

from __future__ import annotations

import gzip
import json

import pytest

from scripts import seed

# ---------------------------------------------------------------- argument parsing


@pytest.mark.parametrize("spec, expected", [
    ("1-9", range(1, 10)), ("3", range(3, 4)), (" 2 - 4 ", range(2, 5)), ("9-9", range(9, 10)),
])
def test_parse_gens(spec, expected):
    assert seed.parse_gens(spec) == expected


@pytest.mark.parametrize("spec", ["0-3", "1-10", "5-2", "x", "", "1-", "1,2"])
def test_parse_gens_rejects_bad_input(spec):
    with pytest.raises(ValueError):
        seed.parse_gens(spec)


def test_substitute_scale_replaces_variable_but_not_casts():
    sql = "SELECT (200000 * :scale)::bigint, :scale"
    assert seed.substitute_scale(sql, 0.1) == "SELECT (200000 * 0.1)::bigint, 0.1"


@pytest.mark.parametrize("scale", [0, -1.0, float("nan")])
def test_substitute_scale_rejects_non_positive(scale):
    with pytest.raises(ValueError):
        seed.substitute_scale("", scale)


def test_workload_sql_has_no_unsubstituted_variables():
    sql = seed.substitute_scale(seed.WORKLOAD_SQL.read_text(encoding="utf-8"), 0.5)
    assert ":scale" not in sql


# ---------------------------------------------------------------- record extraction

def _ref(kind: str, name: str, i: int) -> dict:
    return {"name": name, "url": f"https://pokeapi.co/api/v2/{kind}/{i}/"}


def _detail(method: str, level: int, version_group: int) -> dict:
    return {"move_learn_method": _ref("move-learn-method", method, 0),
            "level_learned_at": level,
            "version_group": _ref("version-group", f"vg{version_group}", version_group)}


POKEMON = {
    "id": 25, "name": "pikachu", "height": 4, "weight": 60, "base_experience": 112,
    "stats": [{"base_stat": v, "stat": _ref("stat", n, 0)} for n, v in [
        ("hp", 35), ("attack", 55), ("defense", 40),
        ("special-attack", 50), ("special-defense", 50), ("speed", 90)]],
    "types": [{"slot": 1, "type": _ref("type", "electric", 13)}],
    "abilities": [{"slot": 3, "is_hidden": True, "ability": _ref("ability", "lightning-rod", 31)},
                  {"slot": 1, "is_hidden": False, "ability": _ref("ability", "static", 9)}],
    "moves": [
        {"move": _ref("move", "thunder-shock", 84),
         "version_group_details": [_detail("level-up", 1, 1), _detail("level-up", 5, 20),
                                   _detail("level-up", 3, 10)]},
        {"move": _ref("move", "thunderbolt", 85),
         "version_group_details": [_detail("machine", 0, 1), _detail("level-up", 26, 25)]},
    ],
}
SPECIES = {"generation": _ref("generation", "generation-i", 1), "is_legendary": False, "is_mythical": False}

# version-group id -> release order. Here release order matches id, except 28,
# which (like PokeAPI's red-green-japan) has a high id but is the oldest game.
VG_ORDER = {1: 3, 10: 10, 20: 20, 25: 27, 28: 1}


def test_pokemon_record_core_fields():
    r = seed.pokemon_record(POKEMON, SPECIES, VG_ORDER)
    assert (r["id"], r["name"], r["generation"]) == (25, "pikachu", 1)
    assert (r["height_dm"], r["weight_hg"], r["base_experience"]) == (4, 60, 112)
    assert (r["hp"], r["attack"], r["defense"], r["sp_attack"], r["sp_defense"], r["speed"]) == \
        (35, 55, 40, 50, 50, 90)
    assert r["is_legendary"] is False and r["is_mythical"] is False


def test_pokemon_record_types_and_abilities_are_sorted_by_slot():
    r = seed.pokemon_record(POKEMON, SPECIES, VG_ORDER)
    assert r["types"] == [[1, 13]]
    assert r["abilities"] == [[1, 9, False], [3, 31, True]]


def test_pokemon_record_keeps_newest_version_group_per_move_and_method():
    r = seed.pokemon_record(POKEMON, SPECIES, VG_ORDER)
    # thunder-shock: three level-up entries, newest version group (20) wins with level 5.
    # thunderbolt: learned two ways, so one row per method.
    assert r["moves"] == [[84, "level-up", 5], [85, "level-up", 26], [85, "machine", 0]]


def test_pokemon_record_ranks_games_by_release_order_not_id():
    """Regression: a high version-group id is not a recent game (red-green-japan is id 28)."""
    pokemon = {**POKEMON, "moves": [
        {"move": _ref("move", "vine-whip", 22),
         "version_group_details": [_detail("level-up", 3, 25),     # scarlet-violet: newest by order
                                   _detail("level-up", 13, 28)]},  # red-green-japan: highest id, oldest
    ]}
    assert seed.pokemon_record(pokemon, SPECIES, VG_ORDER)["moves"] == [[22, "level-up", 3]]


def test_pokemon_record_fails_loudly_on_an_unknown_game():
    pokemon = {**POKEMON, "moves": [{"move": _ref("move", "tackle", 33),
                                     "version_group_details": [_detail("level-up", 1, 99)]}]}
    with pytest.raises(KeyError):
        seed.pokemon_record(pokemon, SPECIES, VG_ORDER)


def test_move_record_handles_missing_values():
    move = {"id": 14, "name": "swords-dance", "power": None, "accuracy": None, "pp": 20,
            "type": _ref("type", "normal", 1), "damage_class": _ref("move-damage-class", "status", 1),
            "generation": _ref("generation", "generation-i", 1)}
    assert seed.move_record(move) == {"id": 14, "name": "swords-dance", "type_id": 1, "damage_class": "status",
                                      "power": None, "accuracy": None, "pp": 20, "generation": 1}


@pytest.mark.parametrize("name, n", [("generation-i", 1), ("generation-iv", 4), ("generation-ix", 9)])
def test_generation_number(name, n):
    assert seed.generation_number(name) == n


def test_write_snapshot_is_byte_reproducible(tmp_path):
    a, b = tmp_path / "a.json.gz", tmp_path / "b.json.gz"
    seed.write_snapshot({"z": 1, "a": [2, "é"]}, a)
    seed.write_snapshot({"a": [2, "é"], "z": 1}, b)
    assert a.read_bytes() == b.read_bytes()
    with gzip.open(a, "rt", encoding="utf-8") as f:
        assert json.load(f) == {"a": [2, "é"], "z": 1}


# ---------------------------------------------------------------- the committed snapshot

@pytest.fixture(scope="module")
def snap():
    return seed.read_snapshot()


def test_snapshot_covers_all_generations(snap):
    assert snap["generations"] == [1, 9]
    assert len(snap["pokemon"]) == 1025
    assert {p["generation"] for p in snap["pokemon"]} == set(range(1, 10))


def test_snapshot_ids_and_names_are_unique(snap):
    for key in ("types", "abilities"):
        rows = snap[key]
        assert len({r[0] for r in rows}) == len(rows)
        assert len({r[1] for r in rows}) == len(rows)
    for key in ("pokemon", "moves"):
        rows = snap[key]
        assert len({r["id"] for r in rows}) == len(rows)
        assert len({r["name"] for r in rows}) == len(rows)


def test_snapshot_references_resolve(snap):
    """Every foreign key in the schema points at a row that will exist."""
    types = {t[0] for t in snap["types"]}
    abilities = {a[0] for a in snap["abilities"]}
    moves = {m["id"] for m in snap["moves"]}
    for p in snap["pokemon"]:
        assert {t[1] for t in p["types"]} <= types
        assert {a[1] for a in p["abilities"]} <= abilities
        assert {m[0] for m in p["moves"]} <= moves
    assert {m["type_id"] for m in snap["moves"]} - {None} <= types


def test_snapshot_respects_primary_keys(snap):
    for p in snap["pokemon"]:
        assert len({t[0] for t in p["types"]}) == len(p["types"])            # (pokemon_id, slot)
        assert len({a[0] for a in p["abilities"]}) == len(p["abilities"])    # (pokemon_id, slot)
        assert len({(m[0], m[1]) for m in p["moves"]}) == len(p["moves"])   # (pokemon, move, method)


def test_snapshot_has_values_the_schema_requires(snap):
    required = ["name", "height_dm", "weight_hg", "hp", "attack", "defense", "sp_attack", "sp_defense", "speed"]
    for p in snap["pokemon"]:
        assert all(p[c] is not None for c in required), p["name"]
        assert 1 <= len(p["types"]) <= 2
    pikachu = next(p for p in snap["pokemon"] if p["name"] == "pikachu")
    assert pikachu["id"] == 25 and pikachu["generation"] == 1


# ---------------------------------------------------------------- workload reproducibility (database)

def _workload_fingerprint(settings: list[str]) -> str:
    """Generate a tiny workload inside a transaction that is always rolled back,
    under the given planner settings, and fingerprint team_members."""
    import psycopg

    from server import config

    sql = seed.substitute_scale(seed.WORKLOAD_SQL.read_text(encoding="utf-8"), 0.01)
    with psycopg.connect(config.DBA_DSN) as conn:
        try:
            for s in settings:
                conn.execute(s)
            conn.execute(f"TRUNCATE {', '.join(seed.WORKLOAD_TABLES)} RESTART IDENTITY")
            conn.execute(sql)
            return conn.execute(
                "SELECT md5(string_agg(md5(m::text), '' ORDER BY team_id, slot)) FROM team_members m"
            ).fetchone()[0]
        finally:
            conn.rollback()   # the real workload tables are untouched


@pytest.mark.db
@pytest.mark.parametrize("settings", [
    ["SET LOCAL enable_material = off"],
    ["SET LOCAL enable_nestloop = off"],
    ["SET LOCAL join_collapse_limit = 1", "SET LOCAL enable_hashjoin = off"],
])
def test_workload_rows_do_not_depend_on_the_query_plan(settings):
    """Regression (D17): row order used to follow the join plan, so a fresh build and a
    rebuild at full scale differed. `enable_material = off` reproduced it at this size."""
    assert _workload_fingerprint(settings) == _workload_fingerprint([])


# ---------------------------------------------------------------- state after seeding (D19)

@pytest.mark.parametrize("argv, expected", [
    (["--only", "fetch"], ["fetch"]),
    (["--only", "reference"], ["reference", "reset"]),
    (["--only", "workload"], ["workload", "reset"]),
    ([], ["reference", "workload", "reset"]),
])
def test_query_stats_are_reset_after_any_stage_that_changes_the_database(monkeypatch, argv, expected):
    calls: list[str] = []
    monkeypatch.setattr(seed, "fetch_snapshot", lambda gens: calls.append("fetch"))
    monkeypatch.setattr(seed, "load_reference", lambda: calls.append("reference"))
    monkeypatch.setattr(seed, "load_workload", lambda scale: calls.append("workload"))
    monkeypatch.setattr(seed, "reset_query_stats", lambda: calls.append("reset"))
    seed.main(argv)
    assert calls == expected


@pytest.mark.db
def test_reset_query_stats_empties_pg_stat_statements():
    """This resets the dev database's statistics, as every seed does anyway."""
    import psycopg

    from server import config

    with psycopg.connect(config.ADMIN_DSN, autocommit=True) as conn:
        def marker_count() -> int:
            return conn.execute("SELECT count(*) FROM pg_stat_statements WHERE query LIKE %s",
                                ("%zz_pytest_marker%",)).fetchone()[0]

        conn.execute("SELECT count(*) AS zz_pytest_marker FROM types")
        assert marker_count() >= 1
        seed.reset_query_stats()
        assert marker_count() == 0


@pytest.mark.db
def test_workload_tables_are_vacuumed_after_seeding():
    """Every page is all-visible, so an index-only scan needs no heap fetches and the
    first query after a seed isn't slower than the rest. Without the VACUUM, a fresh
    seed at scale 1.0 had 0 of 49,194 encounters pages all-visible."""
    import psycopg

    from server import config

    with psycopg.connect(config.ADMIN_DSN) as conn:
        rows = conn.execute(
            "SELECT relname, relpages, relallvisible FROM pg_class WHERE relname = ANY(%s) AND relkind = 'r'",
            (list(seed.WORKLOAD_TABLES),),
        ).fetchall()
    assert len(rows) == len(seed.WORKLOAD_TABLES)
    for name, pages, visible in rows:
        assert pages > 0 and visible == pages, f"{name}: {visible} of {pages} pages all-visible"
