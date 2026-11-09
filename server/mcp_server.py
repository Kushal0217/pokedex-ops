"""MCP server entry point: a thin adapter from a Toolset to MCP.

Owns: transport (stdio) and registration. No tool logic lives here, so the
eval runner can call the exact same ToolSpecs directly and measure the same thing
Claude Code gets.

Usage: python -m server.mcp_server [--toolset v1]
"""

from __future__ import annotations

import argparse


def build(version: str):
    """Create an MCPServer (mcp>=2: `from mcp.server.mcpserver import MCPServer`)
    and register every ToolSpec in the chosen toolset."""
    raise NotImplementedError


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--toolset", default="v1")
    args = parser.parse_args()
    build(args.toolset).run()


if __name__ == "__main__":
    main()
