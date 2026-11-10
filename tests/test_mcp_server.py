"""The MCP adapter exposes exactly the toolset's interface (no database needed)."""

from __future__ import annotations

import asyncio

from server.mcp_server import build
from server.toolsets import load


def test_build_exposes_toolset_names_descriptions_and_schemas():
    toolset = load("v1")
    listed = {t.name: t for t in asyncio.run(build("v1").list_tools())}
    assert set(listed) == {s.name for s in toolset.tools}
    for spec in toolset.tools:
        assert listed[spec.name].description == spec.description
        assert listed[spec.name].input_schema == spec.input_schema
