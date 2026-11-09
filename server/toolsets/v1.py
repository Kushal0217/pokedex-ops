"""Toolset v1: the prototype. Descriptions are deliberately the first, plain draft.

Do not tune these against eval results. Improvements go into v2.
"""

from __future__ import annotations

from server import tools
from server.toolsets import Toolset, ToolSpec

_SQL = {"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]}

TOOLSET = Toolset(
    version="v1",
    policy={"apply_index_requires_confirm": False},
    tools=[
        ToolSpec("describe_schema", "TODO: v1 description.",
                 {"type": "object", "properties": {"table": {"type": "string"}}},
                 tools.describe_schema),
        ToolSpec("run_read_query", "TODO: v1 description.", _SQL, tools.run_read_query),
        ToolSpec("explain_query", "TODO: v1 description.", _SQL, tools.explain_query),
        ToolSpec("propose_index", "TODO: v1 description.",
                 {"type": "object",
                  "properties": {"sql": {"type": "string"}, "index_sql": {"type": "string"}},
                  "required": ["sql"]},
                 tools.propose_index),
        ToolSpec("check_health", "TODO: v1 description.", {"type": "object", "properties": {}},
                 tools.check_health),
        ToolSpec("apply_index", "TODO: v1 description.",
                 {"type": "object", "properties": {"index_sql": {"type": "string"}},
                  "required": ["index_sql"]},
                 tools.apply_index),
    ],
)
