"""Seed helpers and the committed snapshot (no database needed, so these run in CI)."""

from __future__ import annotations

import pytest

from scripts import seed


def test_parse_gens():
    assert seed.parse_gens("1-9") == range(1, 10)
    assert seed.parse_gens("4") == range(4, 5)
    with pytest.raises(ValueError):
        seed.parse_gens("5-2")


def test_url_id():
    assert seed.url_id("https://pokeapi.co/api/v2/type/13/") == 13
    assert seed.url_id("https://pokeapi.co/api/v2/type/13") == 13


def test_substitute_scale_leaves_casts_alone():
    out = seed.substitute_scale("SELECT (200000 * :scale)::bigint, :scale", 0.5)
    assert out == "SELECT (200000 * 0.5)::bigint, 0.5"
    with pytest.raises(ValueError):
        seed.substitute_scale(":scale", 0)


def _detail(level, method, vg_id):
    return {"level_learned_at": level, "move_learn_method": {"name": method},
            "version_group": {"url": f"https://pokeapi.co/api/v2/version-group/{vg_id}/"}}


def test_latest_learnset_uses_release_order_not_id():
    # Version group 28 (red-green-japan) was added to PokeAPI last but released first.
    vg_order = {25: 27, 28: 1}
    moves = [{"move": {"name": "vine-whip", "url": "https://pokeapi.co/api/v2/move/22/"},
              "version_group_details": [_detail(13, "level-up", 28), _detail(3, "level-up", 25),
                                        _detail(0, "machine", 28)]}]
    assert seed.latest_learnset(moves, vg_order) == [
        [22, "vine-whip", "level-up", 3],
        [22, "vine-whip", "machine", 0],
    ]


# ---------------------------------------------------------------- committed snapshot

@pytest.fixture(scope="module")
def tables():
    snap = seed.read_snapshot()["tables"]
    return {name: [dict(zip(t["columns"], row)) for row in t["rows"]] for name, t in snap.items()}


def test_snapshot_has_every_reference_table(tables):
    assert set(tables) == set(seed.REFERENCE_TABLES)
    assert len(tables["pokemon"]) == 1025


def test_snapshot_foreign_keys_resolve(tables):
    ids = {name: {r["id"] for r in tables[name]} for name in ("types", "abilities", "pokemon", "moves")}
    for r in tables["pokemon_types"]:
        assert r["pokemon_id"] in ids["pokemon"] and r["type_id"] in ids["types"]
    for r in tables["pokemon_abilities"]:
        assert r["pokemon_id"] in ids["pokemon"] and r["ability_id"] in ids["abilities"]
    for r in tables["pokemon_moves"]:
        assert r["pokemon_id"] in ids["pokemon"] and r["move_id"] in ids["moves"]
    for r in tables["moves"]:
        assert r["type_id"] in ids["types"]


def test_snapshot_primary_keys_unique(tables):
    keys = {"pokemon_types": ("pokemon_id", "slot"), "pokemon_abilities": ("pokemon_id", "slot"),
            "pokemon_moves": ("pokemon_id", "move_id", "learn_method")}
    for name, cols in keys.items():
        pks = [tuple(r[c] for c in cols) for r in tables[name]]
        assert len(pks) == len(set(pks)), name


def test_snapshot_known_facts(tables):
    pokemon = {p["name"]: p for p in tables["pokemon"]}
    assert (pokemon["pikachu"]["id"], pokemon["pikachu"]["speed"]) == (25, 90)
    assert pokemon["mewtwo"]["is_legendary"] and pokemon["mew"]["is_mythical"]
    assert pokemon["giratina"]["generation"] == 4  # species name, not "giratina-altered"
    moves = {m["name"]: m for m in tables["moves"]}
    assert (moves["thunderbolt"]["power"], moves["thunderbolt"]["damage_class"]) == (90, "special")
