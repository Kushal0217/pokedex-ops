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


def test_mcp_json_serves_the_toolset_of_the_loaded_skill():
    """The loaded skill is the newest version, so .mcp.json must start that toolset too;
    otherwise the skill tells the agent about parameters the server rejects (DECISIONS D32)."""
    import json

    from server import config

    versions = sorted((config.ROOT / "skills").glob("v*"), key=lambda p: int(p.name[1:]))
    args = json.loads((config.ROOT / ".mcp.json").read_text())["mcpServers"]["pokedex-ops"]["args"]
    assert args[args.index("--toolset") + 1] == versions[-1].name


def test_v2_toolset_shape():
    ts = load("v2")
    assert ts.version == "v2"
    assert {t.name for t in ts.tools} == EXPECTED
