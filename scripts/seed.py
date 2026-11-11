"""Build the database: schema -> reference data -> synthetic workload.

Stages (each idempotent, each runnable alone with --only):
  1. fetch      PokeAPI -> data/pokeapi_snapshot.json.gz  (only with --refresh; cached HTTP)
  2. reference  schema + snapshot -> reference tables     (as pokedex_dba, so it owns them)
  3. workload   db/workload.sql with :scale                (millions of rows, generated in SQL)

The snapshot is committed, so every rebuild has identical ground truth and CI
never calls PokeAPI. Fetch it once, on one machine, and commit it.

Usage: python scripts/seed.py [--refresh] [--gens 1-9] [--scale 1.0] [--only STAGE]
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "data" / "pokeapi_snapshot.json.gz"
CACHE = ROOT / ".cache" / "pokeapi"
SCHEMA_SQL = ROOT / "db" / "schema.sql"
WORKLOAD_SQL = ROOT / "db" / "workload.sql"

API = "https://pokeapi.co/api/v2/"
FETCH_WORKERS = 8  # PokeAPI asks clients to be gentle; responses are cached on disk.

STAT_COLUMNS = {
    "hp": "hp", "attack": "attack", "defense": "defense",
    "special-attack": "sp_attack", "special-defense": "sp_defense", "speed": "speed",
}
ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9}

WORKLOAD_TABLES = ("ops_audit_log", "encounters", "battles", "team_members", "teams", "trainers")


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- pure helpers

def parse_gens(spec: str) -> range:
    """'1-9' -> range(1, 10); '3' -> range(3, 4). Generations are 1..9."""
    m = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+)\s*)?", spec)
    if not m:
        raise ValueError(f"bad --gens {spec!r}; expected N or N-M, e.g. 1-9")
    lo = int(m.group(1))
    hi = int(m.group(2) or lo)
    if not 1 <= lo <= hi <= 9:
        raise ValueError(f"bad --gens {spec!r}; generations run from 1 to 9")
    return range(lo, hi + 1)


def substitute_scale(sql: str, scale: float) -> str:
    """Replace psql-style :scale with a literal. Leaves ::casts alone."""
    if not scale > 0:
        raise ValueError(f"--scale must be positive, got {scale}")
    return re.sub(r"(?<!:):scale\b", repr(float(scale)), sql)


def url_id(url: str) -> int:
    return int(url.rstrip("/").rsplit("/", 1)[1])


def generation_number(name: str) -> int:
    """'generation-iv' -> 4."""
    return ROMAN[name.split("-", 1)[1]]


def pokemon_record(pokemon: dict[str, Any], species: dict[str, Any],
                   vg_order: dict[int, int]) -> dict[str, Any]:
    """Compact, deterministic record from a /pokemon and its /pokemon-species response.

    `vg_order` maps a version-group id to its release order (PokeAPI's `order`).
    """
    stats = {STAT_COLUMNS[s["stat"]["name"]]: s["base_stat"] for s in pokemon["stats"]}

    # A move is listed once per version group (game) it appeared in. Keep one row
    # per (move, learn method), from the most recently *released* version group,
    # so the data is current. Rank by `order`, not id: ids follow when PokeAPI
    # added a row, so red-green-japan (1996) has id 28, after scarlet-violet (25).
    # Ranking by id took Bulbasaur's Vine Whip from Japanese Blue (level 13)
    # instead of Scarlet/Violet (level 3). Found in PR #4; DECISIONS D17.
    learned: dict[tuple[int, str], tuple[int, int]] = {}
    for entry in pokemon["moves"]:
        move_id = url_id(entry["move"]["url"])
        for d in entry["version_group_details"]:
            key = (move_id, d["move_learn_method"]["name"])
            rank = vg_order[url_id(d["version_group"]["url"])]
            if key not in learned or rank > learned[key][0]:
                learned[key] = (rank, d["level_learned_at"])

    return {
        "id": pokemon["id"],
        "name": pokemon["name"],
        "generation": generation_number(species["generation"]["name"]),
        "height_dm": pokemon["height"],
        "weight_hg": pokemon["weight"],
        "base_experience": pokemon["base_experience"],
        **{col: stats[col] for col in STAT_COLUMNS.values()},
        "is_legendary": species["is_legendary"],
        "is_mythical": species["is_mythical"],
        "types": sorted([t["slot"], url_id(t["type"]["url"])] for t in pokemon["types"]),
        "abilities": sorted(
            [a["slot"], url_id(a["ability"]["url"]), a["is_hidden"]] for a in pokemon["abilities"]
        ),
        "moves": sorted([m, method, level] for (m, method), (_, level) in learned.items()),
    }


def move_record(move: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": move["id"],
        "name": move["name"],
        "type_id": url_id(move["type"]["url"]) if move.get("type") else None,
        "damage_class": move["damage_class"]["name"] if move.get("damage_class") else None,
        "power": move["power"],
        "accuracy": move["accuracy"],
        "pp": move["pp"],
        "generation": generation_number(move["generation"]["name"]) if move.get("generation") else None,
    }


def write_snapshot(snapshot: dict[str, Any], path: Path = SNAPSHOT) -> None:
    """Byte-for-byte reproducible: sorted keys, no whitespace, gzip mtime 0."""
    data = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
        gz.write(data)


def read_snapshot(path: Path = SNAPSHOT) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(
            f"{path.relative_to(ROOT)} is missing. Fetch it once with: python scripts/seed.py --refresh"
        )
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------------------------------- stage 1: fetch

def _get(client: Any, path: str) -> dict[str, Any]:
    """GET one API path, cached on disk under .cache/pokeapi/ (gitignored)."""
    cached = CACHE / (path.strip("/").replace("/", "_") + ".json")
    if cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))
    for attempt in range(5):
        try:
            r = client.get(path)
            r.raise_for_status()
            break
        except Exception as e:  # network blips and 429/5xx: back off and retry
            if attempt == 4:
                raise RuntimeError(f"GET {path} failed: {e}") from e
            time.sleep(2 ** attempt)
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(r.text, encoding="utf-8")
    return r.json()


def fetch_snapshot(gens: range) -> None:
    import httpx

    with httpx.Client(base_url=API, timeout=30, headers={"User-Agent": "pokedex-ops-seed"}) as client:
        def get_many(paths: list[str]) -> list[dict[str, Any]]:
            with ThreadPoolExecutor(FETCH_WORKERS) as pool:
                return list(pool.map(lambda p: _get(client, p), paths))

        species_ids = sorted({
            url_id(s["url"])
            for g in get_many([f"generation/{n}" for n in gens])
            for s in g["pokemon_species"]
        })
        log(f"fetch: {len(species_ids)} species in generations {gens.start}-{gens.stop - 1}")
        vg_ids = sorted(url_id(v["url"]) for v in _get(client, "version-group?limit=1000")["results"])
        vg_order = {g["id"]: g["order"] for g in get_many([f"version-group/{i}" for i in vg_ids])}
        log(f"fetch: {len(vg_order)} version groups (games), ranked by release order")
        species = get_many([f"pokemon-species/{i}" for i in species_ids])
        default_ids = [
            url_id(next(v for v in s["varieties"] if v["is_default"])["pokemon"]["url"]) for s in species
        ]
        pokemon = get_many([f"pokemon/{i}" for i in default_ids])
        records = [pokemon_record(p, s, vg_order) for p, s in zip(pokemon, species)]

        move_ids = sorted({m[0] for r in records for m in r["moves"]})
        log(f"fetch: {len(move_ids)} moves")
        moves = [move_record(m) for m in get_many([f"move/{i}" for i in move_ids])]

    types: dict[int, str] = {}
    abilities: dict[int, str] = {}
    for p in pokemon:
        for t in p["types"]:
            types[url_id(t["type"]["url"])] = t["type"]["name"]
        for a in p["abilities"]:
            abilities[url_id(a["ability"]["url"])] = a["ability"]["name"]
    for m in moves:
        if m["type_id"] is not None and m["type_id"] not in types:
            raise RuntimeError(f"move {m['name']} has a type no pokemon has ({m['type_id']})")

    write_snapshot({
        "source": API,
        "generations": [gens.start, gens.stop - 1],
        "types": sorted([i, n] for i, n in types.items()),
        "abilities": sorted([i, n] for i, n in abilities.items()),
        "moves": sorted(moves, key=lambda m: m["id"]),
        "pokemon": sorted(records, key=lambda r: r["id"]),
    })
    log(f"fetch: wrote {SNAPSHOT.relative_to(ROOT)} ({SNAPSHOT.stat().st_size // 1024} KiB)")


# --------------------------------------------------------------------------- stage 2: reference

def load_reference() -> None:
    """Rebuild every table from db/schema.sql and load the snapshot into the reference tables.

    Runs as pokedex_dba, so that role owns the tables (apply_index needs the owner),
    and its default privileges grant SELECT to pokedex_agent. This drops the
    workload tables too, so run the workload stage afterwards.
    """
    import psycopg

    from server import config

    snap = read_snapshot()
    pokemon_cols = ["id", "name", "generation", "height_dm", "weight_hg", "base_experience",
                    *STAT_COLUMNS.values(), "is_legendary", "is_mythical"]
    move_cols = ["id", "name", "type_id", "damage_class", "power", "accuracy", "pp", "generation"]

    with psycopg.connect(config.DBA_DSN) as conn, conn.cursor() as cur:
        cur.execute(SCHEMA_SQL.read_text(encoding="utf-8"))

        def copy(table: str, cols: list[str], rows: Any) -> int:
            n = 0
            with cur.copy(f"COPY {table} ({', '.join(cols)}) FROM STDIN") as cp:
                for row in rows:
                    cp.write_row(row)
                    n += 1
            return n

        counts = {
            "types": copy("types", ["id", "name"], snap["types"]),
            "abilities": copy("abilities", ["id", "name"], snap["abilities"]),
            "pokemon": copy("pokemon", pokemon_cols, ([p[c] for c in pokemon_cols] for p in snap["pokemon"])),
            "moves": copy("moves", move_cols, ([m[c] for c in move_cols] for m in snap["moves"])),
            "pokemon_types": copy("pokemon_types", ["pokemon_id", "slot", "type_id"],
                                  ([p["id"], *t] for p in snap["pokemon"] for t in p["types"])),
            "pokemon_abilities": copy("pokemon_abilities", ["pokemon_id", "slot", "ability_id", "is_hidden"],
                                      ([p["id"], *a] for p in snap["pokemon"] for a in p["abilities"])),
            "pokemon_moves": copy("pokemon_moves", ["pokemon_id", "move_id", "learn_method", "level_learned"],
                                  ([p["id"], *m] for p in snap["pokemon"] for m in p["moves"])),
        }
        cur.execute("ANALYZE types, abilities, pokemon, moves, pokemon_types, pokemon_abilities, pokemon_moves")
    log("reference: " + ", ".join(f"{t}={n}" for t, n in counts.items()))


# --------------------------------------------------------------------------- stage 3: workload

def load_workload(scale: float) -> None:
    """Regenerate the synthetic workload tables. Idempotent: truncates them first."""
    import psycopg

    from server import config

    sql = substitute_scale(WORKLOAD_SQL.read_text(encoding="utf-8"), scale)
    started = time.monotonic()
    with psycopg.connect(config.DBA_DSN) as conn, conn.cursor() as cur:
        cur.execute(f"TRUNCATE {', '.join(WORKLOAD_TABLES)} RESTART IDENTITY")
        cur.execute(sql)  # many statements, no parameters: sent as one script
        counts = {}
        for t in reversed(WORKLOAD_TABLES):
            cur.execute(f"SELECT count(*) FROM {t}")
            counts[t] = cur.fetchone()[0]
    log(f"workload (scale {scale}): " + ", ".join(f"{t}={n}" for t, n in counts.items())
        + f" in {time.monotonic() - started:.0f}s")


# --------------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refresh", action="store_true", help="re-fetch PokeAPI into the snapshot first")
    parser.add_argument("--gens", default="1-9", help="generations to fetch (with --refresh), e.g. 1-9")
    parser.add_argument("--scale", type=float, default=1.0, help="workload size; 1.0 is ~10.7M rows")
    parser.add_argument("--only", choices=["fetch", "reference", "workload"], help="run just one stage")
    args = parser.parse_args(argv)

    gens = parse_gens(args.gens)
    substitute_scale("", args.scale)  # validate before doing any work

    stages = [args.only] if args.only else [*(["fetch"] if args.refresh else []), "reference", "workload"]
    sys.path.insert(0, str(ROOT))  # so `from server import config` works when run as a script
    for stage in stages:
        if stage == "fetch":
            fetch_snapshot(gens)
        elif stage == "reference":
            load_reference()
        else:
            load_workload(args.scale)


if __name__ == "__main__":
    main()
