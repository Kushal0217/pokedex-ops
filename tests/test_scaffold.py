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


def test_loaded_skill_is_the_newest_skill_version():
    """Claude Code loads .claude/skills/pokedex-ops/; the eval loads skills/vN/. They must not
    drift apart, so the loaded copy must equal the newest version (DECISIONS D27)."""
    from server import config

    versions = sorted((config.ROOT / "skills").glob("v*"), key=lambda p: int(p.name[1:]))
    newest, live = versions[-1], config.ROOT / ".claude" / "skills" / "pokedex-ops"

    def files(root):
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}

    assert files(live) == files(newest)
