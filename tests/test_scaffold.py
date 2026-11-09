"""Scaffold smoke test: every module imports and the v1 toolset is well-formed."""

from server import db, mcp_server, sqlguard, tools  # noqa: F401
from server.toolsets import load

EXPECTED = {"describe_schema", "run_read_query", "explain_query", "propose_index", "check_health", "apply_index"}


def test_v1_toolset_shape():
    ts = load("v1")
    assert ts.version == "v1"
    assert {t.name for t in ts.tools} == EXPECTED
    for t in ts.tools:
        assert t.input_schema["type"] == "object"
        assert callable(t.handler)
