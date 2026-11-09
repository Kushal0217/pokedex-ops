"""Versioned tool interfaces: the thing the eval loop measures and redesigns.

A toolset is the agent-facing contract: tool names, descriptions, input schemas,
and policy flags (e.g. whether apply_index requires confirmation). Each version
maps onto handlers in server/tools.py.

v1 = the prototype from the build guide. v2 is written only after reading the
v1 eval transcripts, never before, so the before/after comparison is honest.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class Toolset:
    version: str
    tools: list[ToolSpec]
    policy: dict[str, Any] = field(default_factory=dict)


def load(version: str) -> Toolset:
    """Return the toolset for a version string such as 'v1'."""
    from importlib import import_module

    return import_module(f"server.toolsets.{version}").TOOLSET
