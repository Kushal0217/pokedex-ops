"""Tests for the eval runner's session handling, isolation check, answers, resumable runs,
usage guard and task validation. A fake runner returns canned stream-json; the real `claude`
is never started."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

import psycopg
import pytest

from server import config

ROOT = Path(__file__).resolve().parent.parent
PROBE = ROOT / "tests" / "fixtures" / "claude_stream_probe.jsonl"

_spec = importlib.util.spec_from_file_location("eval_runner", ROOT / "scripts" / "eval.py")
ev = sys.modules.get("eval_runner") or importlib.util.module_from_spec(_spec)
if "eval_runner" not in sys.modules:
    sys.modules["eval_runner"] = ev
    _spec.loader.exec_module(ev)


def probe_init() -> dict:
    for line in PROBE.read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        if e.get("type") == "system" and e.get("subtype") == "init":
            return e
    raise AssertionError("no init in the probe fixture")


@pytest.fixture(autouse=True)
def no_personal_skills(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    return home


def stream(text: str = "done", *, init: dict | None = None, session: str = "s1", turns: int = 2,
           cost: float = 0.5, tokens: int = 10, tool_uses: list[dict] | None = None,
           rate: dict | None = None, with_init: bool = True) -> str:
    lines = []
    if with_init:
        lines.append(init or probe_init())
    if rate:
        lines.append({"type": "rate_limit_event", "rate_limit_info": rate})
    for i, tu in enumerate(tool_uses or []):
        lines.append({"type": "assistant", "message": {"content": [dict(tu, type="tool_use", id=f"t{i}")]}})
    lines.append({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}})
    lines.append({"type": "result", "session_id": session, "num_turns": turns, "total_cost_usd": cost,
                  "result": text, "usage": {"input_tokens": tokens, "output_tokens": tokens,
                                            "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}})
    return "\n".join(json.dumps(x) for x in lines) + "\n"


class FakeRunner:
    def __init__(self, outs: list[str]):
        self.outs, self.cmds = list(outs), []

    def __call__(self, cmd, cwd, timeout):
        self.cmds.append(cmd)
        return self.outs.pop(0), 0, False


def make_args(**kw) -> argparse.Namespace:
    d = dict(toolset="v1", model="m", effort="medium", timeout=5, trials=1, max_trials=None,
             stop_at_5h=0.90, stop_at_7d=0.80, split="dev", vacuum="dirty")
    d.update(kw)
    return argparse.Namespace(**d)


def make_task(**kw) -> "ev.Task":
    d = dict(id="t", prompt="p", split="dev")
    d.update(kw)
    return ev.Task(**d)


def session(task, outs, tmp_path, **argkw):
    r = FakeRunner(outs)
    return ev.run_session(task, make_args(**argkw), tmp_path, tmp_path / "mcp.json", r), r


# --------------------------------------------------------------------------- G1 / G2

def test_command_has_effort_and_only_the_v1_skill():
    cmd = ev.build_command("x", "m", Path("c.json"), effort="high")
    assert cmd[cmd.index("--effort") + 1] == "high"
    i = cmd.index("--allowedTools")
    assert cmd[i + 1:i + 3] == ["mcp__pokedex-ops", "Skill(pokedex-ops)"]
    assert cmd[cmd.index("--tools") + 1] == "Skill"
    assert ev.build_command("x", "m", Path("c.json"))[ev.build_command("x", "m", Path("c.json")).index("--effort") + 1] == "medium"


def test_persistence_flag_follows_answers_and_resume_argv():
    assert "--no-session-persistence" in ev.build_command("x", "m", Path("c"))
    cmd = ev.build_command("hi", "m", Path("c"), resume="sid", persist=True)
    assert "--no-session-persistence" not in cmd
    assert cmd[cmd.index("--resume") + 1] == "sid" and cmd[cmd.index("-p") + 1] == "hi"


def test_defaults_trials_and_effort_on_the_command_line(capsys):
    assert ev.main(["--tasks", "slow-winner-history", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "trials=1" in out and out.count("slow-winner-history t") == 1
    assert "--effort medium" in out and "Skill(pokedex-ops)" in out


# --------------------------------------------------------------------------- G3

def test_isolation_passes_on_the_probe_init():
    assert ev.isolation_problems(probe_init(), "v1") == []


def test_isolation_fails_on_extra_tool():
    init = probe_init()
    init["tools"] = init["tools"] + ["Bash"]
    assert "Bash" in ev.isolation_problems(init, "v1")[0]


def test_isolation_fails_on_missing_mcp_tool():
    init = probe_init()
    init["tools"] = [t for t in init["tools"] if not t.endswith("apply_index")]
    assert "apply_index" in ev.isolation_problems(init, "v1")[0]


def test_isolation_fails_on_disconnected_server():
    init = probe_init()
    init["mcp_servers"] = [{"name": "pokedex-ops", "status": "failed"}]
    assert any("not connected" in p for p in ev.isolation_problems(init, "v1"))


def test_isolation_fails_when_the_skill_is_missing():
    init = probe_init()
    init["skills"] = [s for s in init["skills"] if s != "pokedex-ops"]
    assert any("not loaded" in p for p in ev.isolation_problems(init, "v1"))


def test_isolation_fails_on_a_leaked_personal_skill(no_personal_skills):
    (no_personal_skills / ".claude" / "skills" / "deep-research").mkdir(parents=True)  # also a built-in name
    problems = ev.isolation_problems(probe_init(), "v1")
    assert any("deep-research" in p for p in problems)


def test_session_status_isolation_failed_and_claude_error(tmp_path):
    bad = probe_init()
    bad["tools"] = bad["tools"] + ["Bash"]
    s, _ = session(make_task(), [stream(init=bad)], tmp_path)
    assert s.status == "isolation_failed" and s.problems
    s, _ = session(make_task(), [stream(with_init=False)], tmp_path)
    assert s.status == "claude_error"
    s, _ = session(make_task(), [stream()], tmp_path)
    assert s.status == "ok"


def test_isolation_failed_trials_are_counted_apart_in_the_summary():
    ok = {"success": True, "status": "ok", "tokens": {"i": 1}, "tool_call_count": 1, "skill_loaded": True,
          "cost_usd_list_estimate": 0, "tool_errors": 0, "ended_with_question": False,
          "unrequested_writes": False, "timed_out": False}
    bad = dict(ok, status="isolation_failed", success=False, skill_loaded=False)
    s = ev.summarize([ok, bad])
    assert s["trials"] == 2 and s["scored_trials"] == 1 and s["isolation_failed"] == 1
    assert s["success_rate"] == 1.0 and s["skill_loaded"] == 1.0


# --------------------------------------------------------------------------- G4

@pytest.mark.parametrize("inp,expected", [
    ({"skill": "pokedex-ops"}, True), ({"command": "pokedex-ops:v1"}, True),
    ({"skill": "deep-research"}, False), ({}, False)])
def test_skill_loaded(inp, expected, tmp_path):
    s, _ = session(make_task(), [stream(tool_uses=[{"name": "Skill", "input": inp}])], tmp_path)
    assert ev.skill_was_loaded(s.parsed.skill_inputs) is expected


def test_skill_loaded_false_in_the_probe_run():
    assert not ev.skill_was_loaded(ev.parse_stream(PROBE.read_text(encoding="utf-8")).skill_inputs)


# --------------------------------------------------------------------------- G5

ANSWERS = [{"when_all": ["Which", "Table"], "reply": "the teams table"},
           {"when_all": ["sure"], "reply": "yes go ahead"}]


def test_reply_matches_case_insensitively_and_resumes_the_session(tmp_path):
    outs = [stream("WHICH table do you mean?", session="abc"), stream("All done")]
    s, r = session(make_task(answers=ANSWERS), outs, tmp_path)
    assert s.replies == ["the teams table"] and s.parsed.final_text == "All done"
    assert len(r.cmds) == 2
    first, second = r.cmds
    assert "--resume" not in first and "--no-session-persistence" not in first
    assert second[second.index("--resume") + 1] == "abc" and second[second.index("-p") + 1] == "the teams table"
    assert "--no-session-persistence" not in second and "--allowedTools" in second
    assert not s.unanswered_question


def test_no_match_ends_the_trial_and_flags_the_question(tmp_path):
    s, r = session(make_task(answers=ANSWERS), [stream("Which colour?")], tmp_path)
    assert s.replies == [] and len(r.cmds) == 1 and s.unanswered_question


def test_a_question_without_answers_is_unanswered_and_keeps_no_persistence(tmp_path):
    s, r = session(make_task(), [stream("Which one?")], tmp_path)
    assert s.unanswered_question and "--no-session-persistence" in r.cmds[0]


def test_at_most_three_replies(tmp_path):
    outs = [stream("sure?", session="x") for _ in range(6)]
    s, r = session(make_task(answers=ANSWERS), outs, tmp_path)
    assert len(s.replies) == 3 and len(r.cmds) == 4


def test_merged_usage_turns_cost_calls_and_transcript(tmp_path):
    use = [{"name": "mcp__pokedex-ops__check_health", "input": {}}]
    outs = [stream("sure?", turns=2, cost=0.25, tokens=10, tool_uses=use),
            stream("fine", turns=3, cost=0.5, tokens=5, tool_uses=use)]
    s, _ = session(make_task(answers=ANSWERS), outs, tmp_path)
    p = s.parsed
    assert p.result["num_turns"] == 5 and p.result["total_cost_usd"] == pytest.approx(0.75)
    assert p.usage["input"] == 15 and p.usage["output"] == 15
    assert p.tool_calls == {"mcp__pokedex-ops__check_health": 2}
    assert p.final_text == "fine"
    assert s.transcript.count('"subtype": "init"') == 2 and s.transcript.index("sure?") < s.transcript.index("fine")


# --------------------------------------------------------------------------- G6

def test_thousand_and_million_words():
    assert ev.answer_matches("about 12.5 million rows", 12_500_000)[0]
    assert ev.answer_matches("roughly 5 Thousand", 5000)[0]
    assert ev.answer_matches("3 MILLION", 3_000_000)[0]
    assert not ev.answer_matches("3 million", 3000)[0]
    assert not ev.answer_matches("3 millions", 3_000_000)[0]


def test_text_answer_must_be_a_whole_token():
    assert ev.answer_matches("the teams table", "teams")[0]
    assert ev.answer_matches("Teams.", "teams")[0]
    assert not ev.answer_matches("the teamsters table", "teams")[0]
    assert not ev.answer_matches("index teams_pkey", "teams")[0]
    assert ev.answer_matches("see (a.b) now", "a.b")[0]


@pytest.mark.db
def test_ground_truth_is_computed_before_the_agent_runs(tmp_path):
    with psycopg.connect(config.ADMIN_DSN, autocommit=True) as c:
        base = ev.capture_baseline(c)
        task = make_task(
            setup=["INSERT INTO types (id, name) VALUES (99998, 'zz-truth')"],
            teardown=["DELETE FROM types WHERE id = 99998"],
            checks=[{"answer_matches": {"query": "SELECT count(*) FROM types WHERE name = 'zz-truth'"}}])

        def agent(cmd, cwd, timeout):  # a fake agent that changes the data under the grader
            c.execute("DELETE FROM types WHERE id = 99998")
            return stream("There is 1 row."), 0, False

        (tmp_path / "transcripts").mkdir()
        try:
            try:
                r = ev.run_trial(task, 1, make_args(), c, base, tmp_path, runner=agent)
            except ev.BaselineError:
                pytest.fail("the fake agent's DELETE left the baseline broken")
            assert r["success"] and r["checks"][0]["passed"]
        finally:
            c.execute("DELETE FROM types WHERE id = 99998")
        ev.verify_baseline(c, base)


# --------------------------------------------------------------------------- G7 / G8 / G9

def fake_trial(task, n, rate=None):
    return {"task": task.id, "split": task.split, "trial": n, "status": "ok", "success": True, "checks": [],
            "tool_call_count": 0, "turns": 1, "duration_s": 0.0, "tokens": {"input": 1},
            "cost_usd_list_estimate": 0, "tool_errors": 0, "ended_with_question": False,
            "unrequested_writes": False, "timed_out": False, "rate_limit": rate}


def loop(tmp_path, tasks, calls, name="r", rate_by_call=None, **argkw):
    def fn(task, n):
        calls.append((task.id, n))
        return fake_trial(task, n, (rate_by_call or {}).get(len(calls)))
    return ev.run_loop(tasks, make_args(**argkw), tmp_path / name, fn)


def test_resume_skips_finished_trials_and_rebuilds_results(tmp_path, capsys):
    tasks = [make_task(id="a"), make_task(id="b")]
    calls: list = []
    loop(tmp_path, tasks, calls, trials=2, max_trials=3)
    assert calls == [("a", 1), ("a", 2), ("b", 1)]
    run = tmp_path / "r"
    assert sorted(p.name for p in (run / "trials").iterdir()) == ["a-t1.json", "a-t2.json", "b-t1.json"]
    assert not list(run.rglob("*.tmp"))
    calls.clear()
    loop(tmp_path, tasks, calls, trials=2)
    out = capsys.readouterr().out
    assert calls == [("b", 2)] and "skipping 3 already finished" in out
    res = json.loads((run / "results.json").read_text())
    assert [(t["task"], t["trial"]) for t in res["trials"]] == [("a", 1), ("a", 2), ("b", 1), ("b", 2)]
    assert res["summary"]["overall"]["trials"] == 4


def test_trial_files_are_written_atomically(tmp_path, monkeypatch):
    replaced = []
    real = ev.os.replace
    monkeypatch.setattr(ev.os, "replace", lambda a, b: (replaced.append((Path(a).name, Path(b).name)), real(a, b)))
    loop(tmp_path, [make_task(id="a")], [])
    assert ("a-t1.json.tmp", "a-t1.json") in replaced


def test_max_trials_counts_only_new_trials(tmp_path):
    tasks = [make_task(id="a"), make_task(id="b"), make_task(id="c")]
    calls: list = []
    loop(tmp_path, tasks, calls, max_trials=1)
    loop(tmp_path, tasks, calls, max_trials=1)
    assert calls == [("a", 1), ("b", 1)]  # the second call skipped a and ran one new trial


def rate(status="allowed", five=0.1, seven=0.1):
    return {"status": status, "unifiedWindows": {
        "five_hour": {"utilization": five, "resetsAt": 1794633600, "status": status},
        "seven_day": {"utilization": seven, "resetsAt": 1794758400, "status": "allowed"}}}


@pytest.mark.parametrize("info,fragment", [
    (rate(five=0.90), "five_hour window at 90%"),
    (rate(seven=0.85), "seven_day window at 85%"),
    (rate(status="rejected"), "status is 'rejected'")])
def test_usage_guard_stops_cleanly(tmp_path, capsys, info, fragment):
    tasks = [make_task(id="a"), make_task(id="b")]
    calls: list = []
    assert loop(tmp_path, tasks, calls, name="NAME", rate_by_call={1: info}) == 0
    out = capsys.readouterr().out
    assert calls == [("a", 1)] and fragment in out and "--run NAME" in out
    assert "resets 20" in out
    saved = json.loads((tmp_path / "NAME" / "trials" / "a-t1.json").read_text())
    assert saved["rate_limit"] == info


def test_usage_guard_lets_a_low_usage_run_continue_and_honors_flags(tmp_path):
    tasks = [make_task(id="a"), make_task(id="b")]
    calls: list = []
    loop(tmp_path, tasks, calls, rate_by_call={1: rate(five=0.5, seven=0.5)})
    assert len(calls) == 2
    calls.clear()
    loop(tmp_path, tasks, calls, name="r2", rate_by_call={1: rate(five=0.5)}, stop_at_5h=0.4)
    assert len(calls) == 1


def test_usage_reset_time_is_local(tmp_path):
    msg = ev.usage_stop_reason(rate(five=0.95), 0.9, 0.8, "N")
    assert datetime.fromtimestamp(1794633600).strftime("%Y-%m-%d %H:%M") in msg


def test_reset_time_uses_the_local_timezone(monkeypatch):
    import time
    monkeypatch.setenv("TZ", "Asia/Tokyo")
    time.tzset()
    try:
        assert "JST" in ev.usage_stop_reason(rate(five=0.95), 0.9, 0.8, "N")
    finally:
        monkeypatch.undo()
        time.tzset()


@pytest.mark.db
def test_trial_file_carries_the_latest_rate_limit(tmp_path):
    with psycopg.connect(config.ADMIN_DSN, autocommit=True) as c:
        base = ev.capture_baseline(c)
        (tmp_path / "transcripts").mkdir()
        out = stream("ok", rate=rate(five=0.42))
        r = ev.run_trial(make_task(), 1, make_args(), c, base, tmp_path, runner=lambda *a: (out, 0, False))
        assert r["rate_limit"]["unifiedWindows"]["five_hour"]["utilization"] == 0.42


def test_rate_limit_is_parsed_from_the_probe_run():
    info = ev.parse_stream(PROBE.read_text(encoding="utf-8")).rate_limit
    assert info["unifiedWindows"]["five_hour"]["utilization"] == 0.81


# --------------------------------------------------------------------------- G11

GOOD = "id: {id}\nprompt: hello\n"


def write_task(tmp_path, split, name, body):
    d = tmp_path / split
    d.mkdir(exist_ok=True)
    (d / f"{name}.yaml").write_text(body, encoding="utf-8")


def load(tmp_path, split="dev"):
    return ev.load_tasks(split, tasks_dir=tmp_path)


def test_valid_task_loads_with_answers(tmp_path):
    write_task(tmp_path, "dev", "ok", GOOD.format(id="ok") + "answers:\n  - when_all: [a, b]\n    reply: c\n"
               "setup:\n  - sql: CREATE INDEX i ON t (a)\nchecks:\n  - tool_called: x\n")
    (t,) = load(tmp_path)
    assert t.answers == [{"when_all": ["a", "b"], "reply": "c"}]


@pytest.mark.parametrize("body,reason", [
    (GOOD.format(id="bad") + "bogus: 1\n", "unknown top-level"),
    (GOOD.format(id="bad") + "checks:\n  - nope: 1\n", "unknown check kind"),
    (GOOD.format(id="bad") + "checks:\n  - {tool_called: a, tool_not_called: b}\n", "exactly one key"),
    (GOOD.format(id="bad") + "checks:\n  - tool_called\n", "exactly one key"),
    (GOOD.format(id="other"), "does not match the file name"),
    (GOOD.format(id="bad") + "answers:\n  - when_all: []\n    reply: x\n", "malformed answers"),
    (GOOD.format(id="bad") + "answers:\n  - when_all: [a]\n", "malformed answers"),
    (GOOD.format(id="bad") + "answers:\n  - when_all: [a]\n    reply: 5\n", "malformed answers"),
    (GOOD.format(id="bad") + "answers:\n  - when_all: [1]\n    reply: x\n", "malformed answers"),
    (GOOD.format(id="bad") + "answers:\n  - when_all: [a]\n    reply: x\n    extra: 1\n", "malformed answers"),
    (GOOD.format(id="bad") + "setup:\n  - sql: DELETE FROM teams\n", "needs a teardown"),
])
def test_task_validation_errors_name_the_file_and_reason(tmp_path, body, reason):
    write_task(tmp_path, "dev", "bad", body)
    with pytest.raises(SystemExit, match="bad.yaml") as e:
        load(tmp_path)
    assert reason in str(e.value)


def test_heldout_errors_never_quote_prompt_or_sql(tmp_path):
    secret = "SELECT secret_column FROM hidden"
    write_task(tmp_path, "heldout", "h1", f"id: h1\nprompt: topsecretprompt\nsetup:\n  - sql: {secret}\n")
    with pytest.raises(SystemExit) as e:
        load(tmp_path, "heldout")
    assert "h1.yaml" in str(e.value) and "secret" not in str(e.value)
    write_task(tmp_path, "heldout", "h2", "id: h2\nprompt: topsecretprompt\nchecks:\n  - secretkind: 1\n")
    with pytest.raises(SystemExit) as e:
        ev.parse_task(tmp_path / "heldout" / "h2.yaml", "heldout")
    assert "secret" not in str(e.value) and "h2.yaml" in str(e.value)


def test_dry_run_validates(monkeypatch, tmp_path):
    write_task(tmp_path, "dev", "bad", GOOD.format(id="bad") + "bogus: 1\n")
    real = ev.load_tasks
    monkeypatch.setattr(ev, "load_tasks", lambda split, only=None: real(split, only, tasks_dir=tmp_path))
    with pytest.raises(SystemExit, match="bad.yaml"):
        ev.main(["--dry-run"])
