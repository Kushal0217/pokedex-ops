# Orchestration log

One row per subagent delegation. The goal is to learn when delegation pays off,
so record the cost and the result honestly, including failures.

- **Tokens / time:** from the Agent result's usage line.
- **Rework:** fixes the orchestrator needed after the report (0 = used as is).
- **Review:** reviewer findings (confirmed / plausible), or "n/a".
- **Verdict:** worth it? One line on why.

| Date | Task | Agent | Effort | Tokens | Time | Tool uses | Rework | Review | Verdict |
|------|------|-------|--------|--------|------|-----------|--------|--------|---------|
| 2026-11-11 | Look up subagent frontmatter fields in the Claude Code docs | claude-code-guide (built-in) | default | 27.8k | 42 s | 3 | 0 | n/a | Yes: exact field list, and it found two risks (inherited MCP tools, inherited CLAUDE.md) that changed the design. |
| 2026-11-11 | Implement `explain_query` from a contract (2 files, E1-E4) | implementer | medium | 30.7k | 57 s | 9 | 3: a cancel from another session was treated as the timeout; 2 tests could not fail | see next row | Yes: correct code, contract followed, 12 tests. Weak spot: tests were never shown to fail. One wrong claim in its report (said the v1 description was stale; it is still TODO). |
| 2026-11-11 | Review the `explain_query` diff | reviewer | high | 35.1k | 78 s | 7 | 0 | 1 bug + 1 test gap confirmed, 1 test gap plausible, 3 minor | Yes: it reproduced a real bug (cancel at 0.5 s reported as "after 20 s") that the tests missed. Worth its cost. |
| 2026-11-11 | Research: can the eval run on a Claude subscription instead of an API key? | claude-code-guide (built-in) | default | 140.2k | 112 s | 20 | 0 | n/a | Yes: quoted the terms, limits and flags with sources. Its open question (are tool results in the stream?) took one 11 s probe to answer. |
| 2026-11-11 | Implement `apply_index` from a contract (4 files, A1) | implementer | medium | 48.6k | 150 s | 16 | 3: crash on a leading `;`; wrong "nothing built" for an unfindable table; crash on a concurrent build | see next row | Yes: correct core, and every test shown to fail (D21 worked: no test that could not fail this time). It flagged the race itself. |
| 2026-11-11 | Review the `apply_index` diff | reviewer | high | 34.2k | 73 s | 6 | 0 | 2 bugs confirmed, 1 race plausible, 4 test gaps | Yes: both bugs reproduced against the database; the orchestrator fixed all three in a few minutes. |
| 2026-11-11 | Write 12 dev + 12 heldout eval tasks | task-author | high | 62.9k | 295 s | 21 | open: see the tasks PR | n/a | Partly: 24 tasks validated with psql and hypopg. But its report named one heldout task, and a rolled-back setup check left a dead row that broke a test. The orchestrator's own `git status` then listed the heldout file names. |
| 2026-11-11 | Implement `check_health` from a contract (2 files, H1) | implementer | medium | 56.2k | 540 s | 18 | 3: timestamps to seconds; lock-free sizes; stop when the database is down | see next row | Yes: correct SQL for all nine sections, 9 failure checks, and it found and fixed a 20 s hang behind a lock on its own. Slow (9 min): the lock and sleep tests take real time. Its size limit in the contract (3,000 chars) was mine and wrong. |
| 2026-11-11 | Review the `check_health` diff | reviewer | high | 35.3k | 175 s | 7 | 0 | 2 bugs + 1 test gap confirmed, 2 tests plausible, 1 minor | Yes: both bugs (a lock wiped out `tables`; 50 s with the database down) are about the situations the tool exists for, and the tests missed them. |
