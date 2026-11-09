"""Eval runner: tasks x trials against one toolset; writes transcripts and a scored report.

Flow per (task, trial):
  reset DB to baseline indexes -> run task fixtures (as admin) -> agent loop with the
  toolset's ToolSpecs called directly (same code the MCP server serves) -> run checks
  -> record metrics -> reset.

Metrics (the before/after table):
  task success rate, tool-call error rate, tool calls per task, tokens per task,
  guardrail blocks, destructive/unrequested writes.

Splits: tasks/dev is for reading transcripts and redesigning tools.
        tasks/heldout is scored for the report only; never read while tuning.

Usage: python scripts/eval.py --toolset v1 --split dev --trials 3 [--model claude-haiku-5-5]
Outputs: runs/<timestamp>-<toolset>/{transcripts/*.json, results.json}, dashboard/report.md
"""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--toolset", default="v1")
    parser.add_argument("--split", choices=["dev", "heldout", "all"], default="dev")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--model", default="claude-haiku-5-5")
    parser.parse_args()
    raise NotImplementedError


if __name__ == "__main__":
    main()
