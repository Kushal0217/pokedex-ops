"""Tests for scripts/eval.py: stream parsing, grading, the temp folder, the command, and the
reset + verify cycle on the real database. No test starts a real `claude` session."""

from __future__ import annotations

import filecmp
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import psycopg
import pytest

from server import config

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "claude_p_stream.jsonl"

_spec = importlib.util.spec_from_file_location("eval_runner", ROOT / "scripts" / "eval.py")
ev = importlib.util.module_from_spec(_spec)
sys.modules["eval_runner"] = ev  # dataclasses look the module up by name
_spec.loader.exec_module(ev)


# --------------------------------------------------------------------------- stream parsing

def test_parse_stream_fixture():
    p = ev.parse_stream(FIXTURE.read_text(encoding="utf-8"))
    assert p.tool_calls == {"mcp__pokedex-ops__run_read_query": 2}
    assert p.tool_errors == 0
    assert p.final_text.startswith("The `encounters` table has about **5,000,000 rows**")
    assert p.usage == {"input": 4, "output": 244, "cache_read": 6240, "cache_write": 3717}
    assert p.result["num_turns"] == 3


def test_parse_stream_counts_tool_errors_and_dedupes_tool_use():
    use = '{"type":"assistant","message":{"content":[{"type":"tool_use","id":"a","name":"mcp__pokedex-ops__x"}]}}'
    err = '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"a","is_error":true,"content":"no"}]}}'
    p = ev.parse_stream("\n".join([use, use, err]))
    assert p.tool_calls == {"mcp__pokedex-ops__x": 1}
    assert p.tool_errors == 1


# --------------------------------------------------------------------------- answer_matches

def test_number_with_thousands_separators_matches():
    assert ev.answer_matches("There are 5,000,000 rows.", 5000000)[0]
    assert ev.answer_matches("about 5_000_000.", 5000000)[0]


def test_decimal_within_relative_tolerance():
    assert ev.answer_matches("The average is 41.9 turns", 42.0, 0.01)[0]
    assert not ev.answer_matches("The average is 41.9 turns", 42.0, 0.001)[0]


def test_string_match_ignores_case():
    assert ev.answer_matches("The biggest is ENCOUNTERS.", "encounters")[0]
    assert not ev.answer_matches("The biggest is battles.", "encounters")[0]


def test_absent_number_and_null_fail():
    assert not ev.answer_matches("I could not find out.", 5000000)[0]
    assert not ev.answer_matches("5000000", None)[0]


# --------------------------------------------------------------------------- command, folder, dry run

def test_build_command_flags():
    cmd = ev.build_command("do it", "claude-sonnet-5-5", Path("/x/mcp.json"))
    assert cmd[:3] == ["claude", "-p", "do it"]
    assert cmd[cmd.index("--model") + 1] == "claude-sonnet-5-5"
    assert cmd[cmd.index("--tools") + 1] == "Skill"
    i = cmd.index("--allowedTools")
    assert cmd[i + 1:i + 3] == ["mcp__pokedex-ops", "Skill"]
    for flag in ("--strict-mcp-config", "--no-session-persistence", "--verbose"):
        assert flag in cmd
    assert cmd[cmd.index("--setting-sources") + 1] == "project"


def test_workdir_has_only_skill_and_mcp_config():
    work, cfg = ev.make_workdir("v1")
    try:
        skill_src = ROOT / "skills" / "v1"
        files = {p.relative_to(work).as_posix() for p in work.rglob("*") if p.is_file()}
        expected = {f".claude/skills/pokedex-ops/{p.relative_to(skill_src).as_posix()}"
                    for p in skill_src.rglob("*") if p.is_file()}
        assert files == expected | {"mcp.json"}
        cmp = filecmp.dircmp(work / ".claude" / "skills" / "pokedex-ops", skill_src)
        assert not cmp.left_only and not cmp.right_only and not cmp.diff_files
        server = json.loads(cfg.read_text())["mcpServers"]["pokedex-ops"]
        assert server["args"] == ["-m", "server.mcp_server", "--toolset", "v1"]
        assert Path(server["command"]).is_absolute()
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_dry_run_prints_commands_and_touches_no_database(monkeypatch, capsys):
    def boom(*a, **k):
        raise AssertionError("dry run touched the database or started a session")
    monkeypatch.setattr(ev, "admin", boom)
    monkeypatch.setattr(ev, "run_claude", boom)
    assert ev.main(["--split", "dev", "--trials", "2", "--tasks", "slow-winner-history", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert out.count("slow-winner-history t") == 2
    assert "--strict-mcp-config" in out and "claude-sonnet-5-5" in out


def test_heldout_trial_line_hides_details(capsys):
    ev.print_trial_line({"task": "secret-id", "split": "heldout", "trial": 1, "success": True,
                         "tool_call_count": 1, "turns": 2, "duration_s": 1.0,
                         "checks": [{"check": "answer_matches", "passed": True, "reason": "secret-answer"}]})
    assert "secret" not in capsys.readouterr().out


# --------------------------------------------------------------------------- database

def conn() -> psycopg.Connection:
    return psycopg.connect(config.ADMIN_DSN, autocommit=True)


@pytest.fixture
def scratch():
    t = "zz_eval_scratch"
    with conn() as c:
        c.execute(f"DROP TABLE IF EXISTS public.{t}")
        c.execute(f"CREATE TABLE public.{t} (a int, b int)")
        c.execute(f"INSERT INTO public.{t} VALUES (1, 1), (1, 2)")
        try:
            yield c, t
        finally:
            c.execute(f"DROP TABLE IF EXISTS public.{t}")


@pytest.mark.db
def test_index_exists_match_wrong_order_wrong_table(scratch):
    c, t = scratch
    c.execute(f"CREATE INDEX ON public.{t} (a, b)")
    assert ev.index_exists(c, t, ["a"])[0]
    assert ev.index_exists(c, t, ["a", "b"])[0]
    assert not ev.index_exists(c, t, ["b", "a"])[0]
    assert not ev.index_exists(c, t, ["b"])[0]
    assert not ev.index_exists(c, "types", ["a"])[0]


@pytest.mark.db
def test_index_exists_ignores_an_invalid_index(scratch):
    c, t = scratch
    with pytest.raises(psycopg.Error):  # duplicate values: the build fails and leaves an INVALID index
        c.execute(f"CREATE UNIQUE INDEX CONCURRENTLY zz_eval_bad ON public.{t} (a)")
    invalid = c.execute("SELECT count(*) FROM pg_index WHERE indexrelid = 'public.zz_eval_bad'::regclass "
                        "AND NOT indisvalid").fetchone()[0]
    assert invalid == 1
    assert not ev.index_exists(c, t, ["a"])[0]


@pytest.mark.db
def test_reset_drops_extra_index_and_verify_catches_it():
    with conn() as c:
        base = ev.capture_baseline(c)
        c.execute("CREATE INDEX zz_eval_turns ON public.battles (turns)")
        try:
            with pytest.raises(ev.BaselineError, match="zz_eval_turns"):
                ev.verify_baseline(c, base)
            ev.reset_database(c, base)
            assert "zz_eval_turns" not in ev._public_indexes(c)  # the reset dropped it, not the cleanup
            ev.verify_baseline(c, base)
        finally:
            c.execute("DROP INDEX IF EXISTS public.zz_eval_turns")


@pytest.mark.db
def test_verify_catches_a_changed_row_count_and_teardown_restores_it():
    with conn() as c:
        base = ev.capture_baseline(c)
        ev.run_steps(c, ["INSERT INTO types (id, name) VALUES (99999, 'zz-eval')"])
        try:
            with pytest.raises(ev.BaselineError, match="row count of types"):
                ev.verify_baseline(c, base)
        finally:
            ev.reset_database(c, base, ["DELETE FROM types WHERE id = 99999"])
        ev.verify_baseline(c, base)


@pytest.mark.db
def test_capture_baseline_refuses_a_dirty_database():
    with conn() as c:
        c.execute("CREATE INDEX zz_eval_dirty ON public.types (id, name)")
        try:
            with pytest.raises(ev.BaselineError, match="zz_eval_dirty"):
                ev.capture_baseline(c)
        finally:
            c.execute("DROP INDEX IF EXISTS public.zz_eval_dirty")
