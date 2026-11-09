"""SQL classification: guardrail layer 1 of 4 (see ARCHITECTURE.md, "Guardrails").

Owns: deciding what kind of statement a string is, and producing a clear,
actionable rejection message for the agent.

Does NOT own: execution or enforcement. A wrong "read" verdict here must still be
stopped by the later layers (single-statement protocol, READ ONLY transaction,
least-privilege role). Pure functions, no DB access, fully unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Kind = Literal["read", "create_index", "forbidden"]


@dataclass(frozen=True)
class Verdict:
    kind: Kind
    reason: str = ""            # shown to the agent when kind == "forbidden"
    table: str | None = None    # create_index: target table
    concurrently: bool = False  # create_index: CREATE INDEX CONCURRENTLY?


def classify(sql: str) -> Verdict:
    """Classify exactly one SQL statement.

    Rules (to implement):
      * comments and string/identifier/dollar-quoted literals are ignored;
      * more than one statement -> forbidden;
      * SELECT / WITH / VALUES / TABLE / SHOW with no write keyword, no
        data-modifying CTE, no FOR UPDATE/SHARE, no SELECT INTO, and no
        side-effecting function -> read;
      * CREATE [UNIQUE] INDEX [CONCURRENTLY] ... ON <table> (...) -> create_index;
      * everything else -> forbidden.
    """
    raise NotImplementedError
