"""Errors shared by db.py and tools.py (kept separate so neither imports the other's module)."""

from __future__ import annotations


class ToolError(Exception):
    """Expected failure (bad SQL, guardrail block, timeout). Message goes to the agent."""
