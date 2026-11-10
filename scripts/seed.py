"""Build the database: schema -> reference data -> synthetic workload.

Stages (each idempotent, each runnable alone with --only):
  1. fetch   PokeAPI -> data/pokeapi_snapshot.json.gz   (only with --refresh; cached HTTP)
  2. load    snapshot -> reference tables                 (as pokedex_dba, so it owns them)
  3. scale   db/workload.sql with :scale                  (millions of rows, generated in SQL)

A full run (no --only) also resets the schema first, so it always ends in the
pristine state the eval expects: workload tables with primary keys and nothing
else, even if an earlier run left agent-built indexes behind.

The snapshot is committed, so every rebuild has identical ground truth and CI
never calls PokeAPI. --refresh rebuilds the snapshot from .cache/pokeapi/ where
it can; delete that folder to re-download everything.

This script opens its own connections rather than going through server/db.py:
db.py is the agent's two narrow paths, while seeding needs multi-statement SQL
files and COPY. It only ever runs trusted files from this repo, never agent input.

Usage: python scripts/seed.py [--refresh] [--gens 1-9] [--scale 1.0] [--only fetch|load|scale]
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import psycopg
from psycopg import sql

from server import config

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "data" / "pokeapi_snapshot.json.gz"
CACHE = ROOT / ".cache" / "pokeapi"
SCHEMA_SQL = ROOT / "db" / "schema.sql"
WORKLOAD_SQL = ROOT / "db" / "workload.sql"

API = "https://pokeapi.co/api/v2/"
CONCURRENCY = 8          # polite to a free public API; ~3k requests takes a few minutes cold
RETRIES = 4

# Load order follows the foreign keys: parents before children.
REFERENCE_TABLES = ["types", "abilities", "pokemon", "pokemon_types",
                    "pokemon_abilities", "moves", "pokemon_moves"]
WORKLOAD_TABLES = ["trainers", "teams", "team_members", "battles", "encounters", "ops_audit_log"]

STAT_COLUMNS = {"hp": "hp", "attack": "attack", "defense": "defense",
                "special-attack": "sp_attack", "special-defense": "sp_defense", "speed": "speed"}

COLUMNS = {
    "types": ["id", "name"],
    "abilities": ["id", "name"],
    "pokemon": ["id", "name", "generation", "height_dm", "weight_hg", "base_experience",
                "hp", "attack", "defense", "sp_attack", "sp_defense", "speed",
                "is_legendary", "is_mythical"],
    "pokemon_types": ["pokemon_id", "type_id", "slot"],
    "pokemon_abilities": ["pokemon_id", "ability_id", "is_hidden", "slot"],
    "moves": ["id", "name", "type_id", "damage_class", "power", "accuracy", "pp", "generation"],
    "pokemon_moves": ["pokemon_id", "move_id", "learn_method", "level_learned"],
}


# ---------------------------------------------------------------- helpers (pure)

def parse_gens(text: str) -> range:
    """'1-9' -> range(1, 10); '4' -> range(4, 5)."""
    lo, _, hi = text.partition("-")
    first, last = int(lo), int(hi or lo)
    if not 1 <= first <= last:
        raise ValueError(f"bad --gens {text!r}; expected e.g. 1-9 or 4")
    return range(first, last + 1)


def url_id(url: str) -> int:
    """'https://pokeapi.co/api/v2/type/13/' -> 13."""
    return int(url.rstrip("/").rsplit("/", 1)[1])


def substitute_scale(script: str, scale: float) -> str:
    """Replace psql-style :scale with a numeric literal, leaving ::casts alone."""
    if scale <= 0:
        raise ValueError("--scale must be positive")
    return re.sub(r"(?<![:\w]):scale\b", repr(float(scale)), script)


def latest_learnset(moves: list[dict[str, Any]], vg_order: dict[int, int]) -> list[list[Any]]:
    """[(move_id, move_name, learn_method, level)] from a /pokemon response's moves.

    A move is listed once per game (version group). The table keys on
    (move, method), so for each pair we keep the most recently released version
    group and its level. "Most recent" comes from the version group's `order`,
    not its id: ids follow when PokeAPI added a row, so red-green-japan (1996)
    has id 28, after scarlet-violet.
    """
    best: dict[tuple[int, str], tuple[int, list[Any]]] = {}
    for m in moves:
        move_id = url_id(m["move"]["url"])
        for d in m["version_group_details"]:
            key = (move_id, d["move_learn_method"]["name"])
            rank = vg_order[url_id(d["version_group"]["url"])]
            if key not in best or rank > best[key][0]:
                best[key] = (rank, [move_id, m["move"]["name"], key[1], d["level_learned_at"]])
    return sorted(row for _, row in best.values())


# ---------------------------------------------------------------- 1. fetch

def _trim_species(d: dict[str, Any]) -> dict[str, Any]:
    default = next(v for v in d["varieties"] if v["is_default"])
    return {"name": d["name"], "generation": url_id(d["generation"]["url"]),
            "is_legendary": d["is_legendary"], "is_mythical": d["is_mythical"],
            "pokemon_id": url_id(default["pokemon"]["url"])}


def _trim_pokemon(d: dict[str, Any]) -> dict[str, Any]:
    # The raw response is ~300 KB (sprites, per-game details). Keep only what we
    # load, but keep every game's move entry: picking the learnset happens later,
    # so fixing that logic never needs a re-download.
    return {"height": d["height"], "weight": d["weight"], "base_experience": d["base_experience"],
            "stats": {STAT_COLUMNS[s["stat"]["name"]]: s["base_stat"] for s in d["stats"]},
            "types": [[t["slot"], url_id(t["type"]["url"]), t["type"]["name"]] for t in d["types"]],
            "abilities": [[a["slot"], url_id(a["ability"]["url"]), a["ability"]["name"], a["is_hidden"]]
                          for a in d["abilities"]],
            "moves": [{"move": m["move"],
                       "version_group_details": [
                           {"level_learned_at": v["level_learned_at"],
                            "move_learn_method": {"name": v["move_learn_method"]["name"]},
                            "version_group": {"url": v["version_group"]["url"]}}
                           for v in m["version_group_details"]]}
                      for m in d["moves"]]}


def _trim_version_group_list(d: dict[str, Any]) -> dict[str, Any]:
    return {"ids": sorted(url_id(v["url"]) for v in d["results"])}


def _trim_version_group(d: dict[str, Any]) -> dict[str, Any]:
    return {"order": d["order"]}


def _trim_move(d: dict[str, Any]) -> dict[str, Any]:
    return {"name": d["name"], "type_id": url_id(d["type"]["url"]), "type_name": d["type"]["name"],
            "damage_class": d["damage_class"]["name"] if d["damage_class"] else None,
            "power": d["power"], "accuracy": d["accuracy"], "pp": d["pp"],
            "generation": url_id(d["generation"]["url"])}


def _trim_generation(d: dict[str, Any]) -> dict[str, Any]:
    return {"species": sorted(url_id(s["url"]) for s in d["pokemon_species"])}


async def _get(client: httpx.AsyncClient, sem: asyncio.Semaphore, path: str, trim,
               key: str | None = None) -> dict[str, Any]:
    """GET api/v2/<path>, caching the trimmed JSON under .cache/pokeapi/<key or path>.json."""
    cached = CACHE / f"{key or path}.json"
    if cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))
    async with sem:
        # Retry only what can succeed on a second try: network errors, rate
        # limiting (429) and server errors (5xx). A 404 fails immediately.
        for attempt in range(RETRIES):
            last = attempt == RETRIES - 1
            try:
                resp = await client.get(path)
            except httpx.TransportError:
                if last:
                    raise
            else:
                if resp.status_code != 429 and resp.status_code < 500:
                    resp.raise_for_status()
                    break
                if last:
                    resp.raise_for_status()
            await asyncio.sleep(2 ** attempt)  # exponential backoff: 1s, 2s, 4s
    data = trim(resp.json())
    cached.parent.mkdir(parents=True, exist_ok=True)
    # Write then rename: an interrupted run never leaves a half-written cache file.
    tmp = cached.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(cached)
    return data


async def _fetch(gens: range) -> dict[str, Any]:
    sem = asyncio.Semaphore(CONCURRENCY)
    headers = {"User-Agent": "pokedex-ops-seed (snapshot builder)"}
    async with httpx.AsyncClient(base_url=API, timeout=30, headers=headers) as client:
        async def many(paths: list[str], trim) -> list[dict[str, Any]]:
            return await asyncio.gather(*(_get(client, sem, p, trim) for p in paths))

        generations = await many([f"generation/{g}" for g in gens], _trim_generation)
        species_ids = sorted({s for g in generations for s in g["species"]})
        print(f"  {len(species_ids)} species in generations {gens.start}-{gens.stop - 1}")

        species = await many([f"pokemon-species/{i}" for i in species_ids], _trim_species)
        pokemon = await many([f"pokemon/{s['pokemon_id']}" for s in species], _trim_pokemon)
        print(f"  {len(pokemon)} pokemon fetched")

        vg_list = await _get(client, sem, "version-group?limit=1000", _trim_version_group_list,
                             key="version-group/_list")  # '?' is not allowed in a Windows filename
        vg_details = await many([f"version-group/{i}" for i in vg_list["ids"]], _trim_version_group)
        vg_order = {i: d["order"] for i, d in zip(vg_list["ids"], vg_details)}
        for p in pokemon:
            p["moves"] = latest_learnset(p["moves"], vg_order)

        move_ids = sorted({m[0] for p in pokemon for m in p["moves"]})
        moves = await many([f"move/{i}" for i in move_ids], _trim_move)
        print(f"  {len(moves)} moves fetched")

    rows: dict[str, list[list[Any]]] = {t: [] for t in REFERENCE_TABLES}
    types: dict[int, str] = {}
    abilities: dict[int, str] = {}
    for s, p in zip(species, pokemon):
        pid = s["pokemon_id"]
        # The species name ("giratina"), not the default form's ("giratina-altered"):
        # it is what people actually type in a WHERE clause.
        rows["pokemon"].append([pid, s["name"], s["generation"], p["height"], p["weight"],
                                p["base_experience"], *(p["stats"][c] for c in STAT_COLUMNS.values()),
                                s["is_legendary"], s["is_mythical"]])
        for slot, type_id, type_name in p["types"]:
            types[type_id] = type_name
            rows["pokemon_types"].append([pid, type_id, slot])
        for slot, ability_id, ability_name, hidden in p["abilities"]:
            abilities[ability_id] = ability_name
            rows["pokemon_abilities"].append([pid, ability_id, hidden, slot])
        for move_id, _name, method, level in p["moves"]:
            rows["pokemon_moves"].append([pid, move_id, method, level])
    for move_id, m in zip(move_ids, moves):
        types[m["type_id"]] = m["type_name"]
        rows["moves"].append([move_id, m["name"], m["type_id"], m["damage_class"],
                              m["power"], m["accuracy"], m["pp"], m["generation"]])
    rows["types"] = [[i, n] for i, n in types.items()]
    rows["abilities"] = [[i, n] for i, n in abilities.items()]

    # No timestamp in the file: identical data must give identical bytes, so a
    # re-fetch with nothing new upstream shows up as "no change" in git.
    return {"source": API, "generations": [gens.start, gens.stop - 1],
            "tables": {t: {"columns": COLUMNS[t], "rows": sorted(rows[t])} for t in REFERENCE_TABLES}}


def fetch_snapshot(gens: range) -> None:
    snapshot = asyncio.run(_fetch(gens))
    payload = json.dumps(snapshot, separators=(",", ":"), sort_keys=True).encode()
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    # mtime=0 keeps the gzip header stable too (it otherwise embeds the write time).
    with open(SNAPSHOT, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
        gz.write(payload)
    counts = ", ".join(f"{t}={len(v['rows'])}" for t, v in snapshot["tables"].items())
    print(f"  wrote {SNAPSHOT.relative_to(ROOT)} ({SNAPSHOT.stat().st_size // 1024} KB): {counts}")


def read_snapshot() -> dict[str, Any]:
    if not SNAPSHOT.exists():
        sys.exit(f"{SNAPSHOT.relative_to(ROOT)} is missing. Build it with: python scripts/seed.py --refresh")
    with gzip.open(SNAPSHOT, "rt", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- 2. load

def reset_schema() -> None:
    """Drop and recreate every table, as pokedex_dba so it owns them all."""
    with psycopg.connect(config.DBA_DSN, autocommit=True) as conn:
        conn.execute(SCHEMA_SQL.read_text(encoding="utf-8"))


def load_reference() -> None:
    tables = read_snapshot()["tables"]
    # One transaction: a failure part-way leaves the old reference data intact.
    with psycopg.connect(config.DBA_DSN) as conn:
        # Truncating all reference tables in one statement satisfies their
        # foreign keys without CASCADE, which could silently empty other tables.
        conn.execute(sql.SQL("TRUNCATE {}").format(sql.SQL(", ").join(map(sql.Identifier, REFERENCE_TABLES))))
        with conn.cursor() as cur:
            for table in REFERENCE_TABLES:
                cols = tables[table]["columns"]
                copy_sql = sql.SQL("COPY {} ({}) FROM STDIN").format(
                    sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, cols)))
                with cur.copy(copy_sql) as copy:
                    for row in tables[table]["rows"]:
                        copy.write_row(row)
        conn.execute("ANALYZE " + ", ".join(REFERENCE_TABLES))
    print("  " + ", ".join(f"{t}={len(tables[t]['rows'])}" for t in REFERENCE_TABLES))


# ---------------------------------------------------------------- 3. scale

def load_workload(scale: float) -> None:
    script = substitute_scale(WORKLOAD_SQL.read_text(encoding="utf-8"), scale)
    truncate = "TRUNCATE " + ", ".join(WORKLOAD_TABLES) + " RESTART IDENTITY;\n"
    with psycopg.connect(config.DBA_DSN, autocommit=True) as conn:
        if conn.execute("SELECT count(*) FROM pokemon").fetchone()[0] == 0:
            sys.exit("pokemon is empty; the workload draws from it. Run the load stage first.")
        # A multi-statement string runs as one implicit transaction, so if
        # generation fails the old workload is still there, not half-deleted.
        conn.execute(truncate + script)
        # VACUUM sets the visibility map. Without it, freshly inserted tables
        # can't use index-only scans, and plans wouldn't look like a settled
        # production database. (VACUUM can't run inside a transaction, hence separate.)
        for table in WORKLOAD_TABLES:
            conn.execute(sql.SQL("VACUUM (ANALYZE) {}").format(sql.Identifier(table)))
        counts = conn.execute(
            "SELECT relname, n_live_tup FROM pg_stat_user_tables WHERE relname = ANY(%s) ORDER BY relname",
            (WORKLOAD_TABLES,)).fetchall()
    print("  " + ", ".join(f"{name}={n}" for name, n in counts))


def reset_query_stats() -> None:
    """Forget the seed's own INSERTs, so pg_stat_statements starts clean.

    Needs the superuser: the only reason this script touches ADMIN_DSN.
    """
    with psycopg.connect(config.ADMIN_DSN, autocommit=True) as conn:
        conn.execute("SELECT pg_stat_statements_reset()")


# ---------------------------------------------------------------- main

def _stage(label: str, fn, *args) -> None:
    print(f"{label} ...")
    start = time.perf_counter()
    fn(*args)
    print(f"  done in {time.perf_counter() - start:.1f}s")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--refresh", action="store_true", help="re-fetch PokeAPI into the snapshot")
    parser.add_argument("--gens", default="1-9", help="generations to fetch (with --refresh), e.g. 1-9 or 4")
    parser.add_argument("--scale", type=float, default=1.0, help="workload size; 1.0 is ~10M rows")
    parser.add_argument("--only", choices=["fetch", "load", "scale"], help="run one stage alone")
    args = parser.parse_args()
    gens = parse_gens(args.gens)

    if args.only == "fetch" or args.refresh:
        _stage("fetch: PokeAPI -> snapshot", fetch_snapshot, gens)
    if args.only == "load":
        _stage("load: snapshot -> reference tables", load_reference)
    elif args.only == "scale":
        _stage(f"scale: workload at scale {args.scale}", load_workload, args.scale)
    elif args.only is None:
        read_snapshot()  # fail fast, before dropping anything, if there is no snapshot
        _stage("schema: drop and recreate all tables", reset_schema)
        _stage("load: snapshot -> reference tables", load_reference)
        _stage(f"scale: workload at scale {args.scale}", load_workload, args.scale)
        _stage("stats: reset pg_stat_statements", reset_query_stats)


if __name__ == "__main__":
    main()
