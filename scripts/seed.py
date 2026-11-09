"""Build the database: schema -> reference data -> synthetic workload.

Stages (each idempotent, each runnable alone):
  1. fetch   PokeAPI -> data/pokeapi_snapshot.json.gz   (only with --refresh; cached HTTP)
  2. load    snapshot -> reference tables                 (as pokedex_dba, so it owns them)
  3. scale   db/workload.sql with :scale                  (millions of rows, generated in SQL)

The snapshot is committed, so every rebuild has identical ground truth and CI
never calls PokeAPI.

Usage: python scripts/seed.py [--refresh] [--gens 1-9] [--scale 1.0]
"""

from __future__ import annotations

import argparse


def fetch_snapshot(gens: range) -> None:
    raise NotImplementedError


def load_reference() -> None:
    raise NotImplementedError


def load_workload(scale: float) -> None:
    raise NotImplementedError


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="re-fetch PokeAPI into the snapshot")
    parser.add_argument("--gens", default="1-9")
    parser.add_argument("--scale", type=float, default=1.0)
    parser.parse_args()
    raise NotImplementedError


if __name__ == "__main__":
    main()
