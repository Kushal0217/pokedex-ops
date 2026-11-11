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
