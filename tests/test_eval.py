"""Tests for scripts/eval.py: stream parsing, grading, the temp folder, the command, and the
reset + verify cycle on the real database. No test starts a real `claude` session."""

from __future__ import annotations

import filecmp
import importlib.util
import json
import shutil
import sys
import types
from pathlib import Path

import psycopg
import pytest
import yaml

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
    i = cmd.index("--tools")
    assert cmd[i + 1:i + 3] == ["Skill", "Read"]
    i = cmd.index("--allowedTools")
    assert cmd[i + 1:i + 4] == ["mcp__pokedex-ops", "Skill", "Read(./.claude/skills/**)"]
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
                         "status": "graded", "task_error": False, "tool_call_count": 1, "turns": 2, "duration_s": 1.0,
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


# --------------------------------------------------------------------------- strict answer_matches

@pytest.mark.parametrize("text, exp", [
    ("206", 206), ("The count is -5.", -5), ("(206)", 206), ("It is 206.", 206),
    ("It is 206, I think.", 206), ("5,000,000 rows", 5000000), ("12.5% of them", 12.5), ("-5 degrees", -5),
])
def test_standalone_numbers_match(text, exp):
    assert ev.answer_matches(text, exp)[0]


@pytest.mark.parametrize("text", [
    "team-206", "on 2030-01-01", "at 12:30", "version v2", "release 1.2.3", "path a/206", "id_206", "206abc",
])
def test_embedded_numbers_do_not_match(text):
    for exp in (206, 2030, 2, 1, 12, 30, 3, 1.2):
        assert not ev.answer_matches(text, exp)[0], (text, exp)


def test_minus_sign_only_at_start_or_after_space_or_paren():
    assert ev.answer_matches("(-5)", -5)[0]
    assert not ev.answer_matches("a-5", 5)[0] and not ev.answer_matches("a-5", -5)[0]


def test_code_blocks_and_spans_are_ignored():
    text = "Query: `SELECT 206` and\n```sql\nSELECT 206;\n```\nThat is all."
    assert not ev.answer_matches(text, 206)[0]
    assert ev.answer_matches(text + " The answer is 206.", 206)[0]
    assert not ev.answer_matches("Run `encounters` now", "encounters")[0]


@pytest.mark.db
@pytest.mark.parametrize("query", [
    "SELECT 1 WHERE false", "SELECT 1 UNION ALL SELECT 2", "SELECT NULL::int", "SELECT ''",
])
def test_expected_query_must_return_exactly_one_value(query):
    parsed = types.SimpleNamespace(tool_calls={}, final_text="1 2")
    with conn() as c:
        checks = ev.grade(c, [{"answer_matches": {"query": query}}], parsed)
    assert checks[0]["status"] == "task_error" and not checks[0]["passed"]


@pytest.mark.db
def test_one_row_expected_query_is_graded():
    parsed = types.SimpleNamespace(tool_calls={}, final_text="It is 7.")
    with conn() as c:
        ok = ev.grade(c, [{"answer_matches": {"query": "SELECT 7"}}], parsed)
        bad = ev.grade(c, [{"answer_matches": {"query": "SELECT 8"}}], parsed)
    assert ok[0]["status"] == "ok" and ok[0]["passed"]
    assert bad[0]["status"] == "ok" and not bad[0]["passed"]


def test_task_error_trials_are_left_out_of_the_success_rate():
    def trial(status, success, task_error=False):
        return {"split": "dev", "task": "t", "status": status, "success": success, "task_error": task_error,
                "tokens": {"input": 1}, "tool_call_count": 1, "cost_usd_list_estimate": 0, "tool_errors": 0,
                "ended_with_question": False, "unrequested_writes": False, "timed_out": status == "timeout"}
    s = ev.summarize([trial("graded", True), trial("timeout", False), trial("graded", False, True),
                      trial("infra_error", False), trial("runner_error", False)])
    assert s["scored"] == 2 and s["success_rate"] == 0.5
    assert (s["task_errors"], s["infra_errors"], s["runner_errors"]) == (1, 1, 1)


# --------------------------------------------------------------------------- tool checks

def test_grade_tool_called_and_not_called():
    parsed = types.SimpleNamespace(tool_calls={"mcp__pokedex-ops__explain_query": 2}, final_text="")
    out = ev.grade(None, [{"tool_called": "explain_query"}, {"tool_called": "apply_index"},
                          {"tool_not_called": "apply_index"}, {"tool_not_called": "explain_query"}], parsed)
    assert [c["passed"] for c in out] == [True, False, True, False]


# --------------------------------------------------------------------------- strict index_exists

@pytest.mark.db
def test_partial_index_does_not_count_but_a_full_one_does(scratch):
    c, t = scratch
    c.execute(f"CREATE INDEX zz_eval_partial ON public.{t} (a) WHERE b > 1")
    assert not ev.index_exists(c, t, ["a"])[0]
    c.execute(f"CREATE INDEX zz_eval_full ON public.{t} (a)")
    assert ev.index_exists(c, t, ["a"])[0]


# --------------------------------------------------------------------------- stream guards

def init_event(status="connected") -> str:
    return json.dumps({"type": "system", "subtype": "init",
                       "mcp_servers": [{"name": "pokedex-ops", "status": status}]})


def result_event(text="done", is_error=False) -> str:
    return json.dumps({"type": "result", "is_error": is_error, "result": text, "num_turns": 1,
                       "usage": {}, "total_cost_usd": 0})


@pytest.mark.parametrize("out, code, expect", [
    (init_event(), 0, "no result event"),
    (init_event() + "\n" + result_event(is_error=True), 0, "is_error"),
    (init_event() + "\n" + result_event(), 1, "exited with code 1"),
    (init_event("failed") + "\n" + result_event(), 0, "not connected"),
    (result_event(), 0, "not connected"),
])
def test_infra_problem(out, code, expect):
    assert expect in ev.infra_problem(ev.parse_stream(out), code)


def test_healthy_session_has_no_infra_problem():
    assert ev.infra_problem(ev.parse_stream(init_event() + "\n" + result_event()), 0) is None


# --------------------------------------------------------------------------- whole runs on synthetic tasks

def write_task(root: Path, split: str, tid: str, row_id: int, name: str, query: str | None = None) -> None:
    (root / split).mkdir(parents=True, exist_ok=True)
    (root / split / f"{tid}.yaml").write_text(yaml.safe_dump({
        "id": tid, "prompt": "say the name",
        "setup": [{"sql": f"INSERT INTO types (id, name) VALUES ({row_id}, '{name}')"}],
        "teardown": [{"sql": f"DELETE FROM types WHERE id = {row_id}"}],
        "checks": [{"answer_matches": {"query": query or f"SELECT name FROM types WHERE id = {row_id}"}}],
    }), encoding="utf-8")


def type_rows() -> int:
    with conn() as c:
        return c.execute("SELECT count(*) FROM types WHERE id >= 99990").fetchone()[0]


@pytest.fixture
def synth(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "TASKS_DIR", tmp_path / "tasks")
    monkeypatch.setattr(ev, "RUNS_DIR", tmp_path / "runs")
    calls: list[int] = []
    box = {"out": init_event() + "\n" + result_event("zz-eval-dev"), "code": 0}

    def fake_run(cmd, cwd, timeout):
        calls.append(1)
        return box["out"], box["code"], False
    monkeypatch.setattr(ev, "run_claude", fake_run)
    return types.SimpleNamespace(tasks=tmp_path / "tasks", runs=tmp_path / "runs", calls=calls, box=box)


def only_run(runs: Path) -> Path:
    (d,) = list(runs.iterdir())
    return d


@pytest.mark.db
def test_a_grading_crash_still_runs_teardown_and_reset(synth):
    write_task(synth.tasks, "dev", "zz-crash", 99991, "zz-eval-dev", query="SELECT * FROM zz_no_such_table")
    with conn() as c:
        base = ev.capture_baseline(c)
        task = ev.load_tasks("dev", None, synth.tasks)[0]
        run_dir = synth.runs / "x"
        (run_dir / "transcripts").mkdir(parents=True)
        args = types.SimpleNamespace(toolset="v1", model="m", timeout=5, vacuum="dirty")
        rec = ev.run_trial(task, 1, args, c, base, run_dir)
        assert rec["status"] == "runner_error" and rec["error"] == "UndefinedTable"
        assert "zz_no_such_table" not in json.dumps(rec)  # the message and the SQL are never stored
        assert type_rows() == 0  # the setup row is gone: the teardown ran
        ev.verify_baseline(c, base)


@pytest.mark.db
@pytest.mark.parametrize("out, code", [
    (init_event(), 0),
    (init_event() + "\n" + result_event(is_error=True), 0),
    (init_event() + "\n" + result_event(), 1),
    (init_event("failed") + "\n" + result_event(), 0),
])
def test_infra_error_stops_the_run(synth, capsys, out, code):
    write_task(synth.tasks, "dev", "zz-infra", 99992, "zz-eval-dev")
    synth.box.update(out=out, code=code)
    assert ev.main(["--split", "dev", "--trials", "3", "--timeout", "5"]) == 3
    assert len(synth.calls) == 1  # the run stopped at the first infra error
    res = json.loads((only_run(synth.runs) / "results.json").read_text(encoding="utf-8"))
    assert [t["status"] for t in res["trials"]] == ["infra_error"]
    assert res["summary"]["dev_aggregate"]["scored"] == 0
    assert type_rows() == 0
    assert "STOPPED: infra error" in capsys.readouterr().err


@pytest.mark.db
def test_a_good_run_is_graded_and_cleaned(synth):
    write_task(synth.tasks, "dev", "zz-good", 99993, "zz-eval-dev")
    assert ev.main(["--split", "dev", "--trials", "2", "--timeout", "5"]) == 0
    res = json.loads((only_run(synth.runs) / "results.json").read_text(encoding="utf-8"))
    assert [(t["status"], t["success"]) for t in res["trials"]] == [("graded", True)] * 2
    assert type_rows() == 0


@pytest.mark.db
def test_stats_are_reset_after_the_setup(synth, monkeypatch):
    write_task(synth.tasks, "dev", "zz-stats", 99994, "zz-eval-dev")
    seen: list[int] = []

    def fake_run(cmd, cwd, timeout):
        with conn() as c:
            seen.append(c.execute("SELECT count(*) FROM pg_stat_statements WHERE query ILIKE '%INSERT INTO types%'"
                                  ).fetchone()[0])
        return synth.box["out"], 0, False
    monkeypatch.setattr(ev, "run_claude", fake_run)
    assert ev.main(["--split", "dev", "--trials", "1", "--timeout", "5"]) == 0
    assert seen == [0]  # the setup INSERT is not visible to the agent


@pytest.mark.db
def test_preclean_removes_a_leftover_row_and_index_before_the_baseline(synth):
    write_task(synth.tasks, "dev", "zz-pre", 99995, "zz-eval-dev")
    task = ev.load_tasks("dev", None, synth.tasks)[0]
    with conn() as c:
        before = ev.capture_baseline(c)
        c.execute("INSERT INTO types (id, name) VALUES (99995, 'zz-eval-dev')")
        c.execute("CREATE INDEX zz_eval_stray ON public.types (name, id)")
        try:
            with pytest.raises(ev.BaselineError):
                ev.capture_baseline(c)  # the refusal still exists
            ev.preclean(c, [task])
            assert type_rows() == 0
            assert "zz_eval_stray" not in ev._public_indexes(c)
            assert ev.capture_baseline(c).counts == before.counts
        finally:
            c.execute("DELETE FROM types WHERE id = 99995")
            c.execute("DROP INDEX IF EXISTS public.zz_eval_stray")


@pytest.mark.db
def test_stop_agent_sessions_ends_the_agent_connection():
    agent = psycopg.connect(config.AGENT_DSN, autocommit=True)
    try:
        agent.execute("SELECT 1")
        with conn() as c:
            ev.stop_agent_sessions(c)
        with pytest.raises(psycopg.Error):
            agent.execute("SELECT 1")
    finally:
        agent.close()


@pytest.mark.db
def test_heldout_detail_goes_only_to_the_heldout_files(synth, capsys):
    write_task(synth.tasks, "dev", "zz-dev-visible", 99996, "zz-eval-dev")
    write_task(synth.tasks, "heldout", "zz-held-secret-id", 99997, "zz-held-secret-answer")
    synth.box["out"] = init_event() + "\n" + result_event("zz-eval-dev zz-held-secret-answer")
    assert ev.main(["--split", "all", "--trials", "1", "--timeout", "5"]) == 0
    run = only_run(synth.runs)
    main_json = (run / "results.json").read_text(encoding="utf-8")
    assert "zz-dev-visible" in main_json
    assert "zz-held-secret" not in main_json  # no id, reason or answer
    assert "overall" not in json.loads(main_json)["summary"]
    assert json.loads(main_json)["summary"]["heldout_aggregate"]["trials"] == 1
    held = (run / "results-heldout.json").read_text(encoding="utf-8")
    assert "zz-held-secret-id" in held and "zz-held-secret-answer" in held
    transcripts = list((run / "transcripts-heldout").glob("*.jsonl"))
    assert [p.name for p in transcripts] == ["zz-held-secret-id-t1.jsonl"]
    assert not any("zz-held" in p.name for p in (run / "transcripts").iterdir())
    assert "zz-held-secret" not in capsys.readouterr().out


@pytest.mark.db
def test_leftover_agent_sessions_are_ended_after_each_trial(synth, monkeypatch):
    write_task(synth.tasks, "dev", "zz-leftover", 99989, "zz-eval-dev")
    leaked: list[psycopg.Connection] = []

    def fake_run(cmd, cwd, timeout):
        leaked.append(psycopg.connect(config.AGENT_DSN, autocommit=True))  # a session the agent left running
        return synth.box["out"], None, True
    monkeypatch.setattr(ev, "run_claude", fake_run)
    try:
        assert ev.main(["--split", "dev", "--trials", "1", "--timeout", "5"]) == 0
        with pytest.raises(psycopg.Error):
            leaked[0].execute("SELECT 1")
    finally:
        leaked[0].close()


@pytest.mark.db
def test_task_error_is_flagged_on_the_trial_and_a_timeout_is_a_failure(synth):
    task = ev.Task(id="t", prompt="p", split="dev", checks=[{"answer_matches": {"query": "SELECT 1 WHERE false"}}])
    with conn() as c:
        rec = ev.score_session(c, task, init_event() + "\n" + result_event("1"), 0, False, 1.0)
        assert (rec["status"], rec["task_error"], rec["success"]) == ("graded", True, False)
        ok_task = ev.Task(id="t", prompt="p", split="dev", checks=[{"answer_matches": {"query": "SELECT 1"}}])
        rec = ev.score_session(c, ok_task, "", None, True, 1.0)
        assert (rec["status"], rec["success"]) == ("timeout", False)
