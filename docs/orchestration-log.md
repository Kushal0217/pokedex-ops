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
