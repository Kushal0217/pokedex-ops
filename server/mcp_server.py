"""MCP server entry point: a thin adapter from a Toolset to MCP.

Owns: transport (stdio) and registration. No tool logic lives here, so the
eval runner can call the exact same ToolSpecs directly and measure the same thing
Claude Code gets.

Usage: python -m server.mcp_server [--toolset v1]
"""

from __future__ import annotations

import argparse

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.tools.base import Tool

from server.toolsets import load


def build(version: str) -> MCPServer:
    """Create an MCPServer exposing every ToolSpec in the chosen toolset.

    The advertised input schema is the toolset's, not one inferred from the
    handler signature: the schema is part of the versioned interface.
    """
    toolset = load(version)
    tools = [
        Tool.from_function(spec.handler, name=spec.name, description=spec.description)
        .model_copy(update={"parameters": spec.input_schema})
        for spec in toolset.tools
    ]
    return MCPServer(name="pokedex-ops", version=toolset.version, tools=tools)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--toolset", default="v1")
    args = parser.parse_args()
    build(args.toolset).run()


if __name__ == "__main__":
    main()
