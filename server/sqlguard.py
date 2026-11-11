"""SQL classification: guardrail layer 1 of 4 (see ARCHITECTURE.md, "Guardrails").

Owns: deciding what kind of statement a string is, and producing a clear,
actionable rejection message for the agent.

Does NOT own: execution or enforcement. A wrong "read" verdict here must still be
stopped by the later layers (single-statement protocol, READ ONLY transaction,
least-privilege role). Pure functions, no DB access, fully unit-testable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Kind = Literal["read", "create_index", "forbidden"]


@dataclass(frozen=True)
class Verdict:
    kind: Kind
    reason: str = ""            # shown to the agent when kind == "forbidden"
    table: str | None = None    # create_index: target table
    concurrently: bool = False  # create_index: CREATE INDEX CONCURRENTLY?


READ_STARTS = {"select", "with", "values", "table", "show"}

# Any of these as a bare keyword inside a read means it is not a read.
WRITE_KEYWORDS = {
    "insert", "update", "delete", "merge", "truncate", "drop", "alter", "create",
    "grant", "revoke", "copy", "vacuum", "reindex", "cluster", "refresh", "call", "lock",
}

# Functions with side effects outside the (rolled-back) transaction, or that
# change session state. Matched by name when followed by "(".
SIDE_EFFECT_FUNCTIONS = {
    "nextval", "setval", "set_config", "pg_terminate_backend", "pg_cancel_backend",
    "pg_reload_conf", "pg_rotate_logfile", "pg_switch_wal", "pg_create_restore_point",
    "pg_notify", "pg_promote", "pg_log_backend_memory_contexts",
}
SIDE_EFFECT_PREFIXES = ("pg_advisory", "pg_try_advisory", "lo_", "dblink")

_ONE_STATEMENT = "Only one statement per call is allowed. Send each statement separately."


class _ParseError(Exception):
    pass


@dataclass(frozen=True)
class _Tok:
    kind: str   # word | ident | string | num | param | punct
    text: str   # words lowercased; quoted identifiers keep their exact text


_DOLLAR_TAG = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)?\$")


def _is_ident_start(c: str) -> bool:
    return c.isalpha() or c == "_"


def _is_ident_char(c: str) -> bool:
    return c.isalnum() or c in "_$"


def _tokenize(sql: str, starts: list[int] | None = None) -> list[_Tok]:
    """Lex just enough SQL to find keywords and statement boundaries.
    Comments are dropped; string bodies are opaque. If `starts` is given, the
    start offset of each token in `sql` is appended to it."""
    toks: list[_Tok] = []
    i, n = 0, len(sql)
    while i < n:
        start = i
        c = sql[i]
        if c.isspace():
            i += 1
        elif sql.startswith("--", i):
            j = sql.find("\n", i)
            i = n if j < 0 else j + 1
        elif sql.startswith("/*", i):
            depth, i = 1, i + 2
            while depth:
                if i >= n:
                    raise _ParseError("unterminated /* comment")
                if sql.startswith("/*", i):
                    depth, i = depth + 1, i + 2
                elif sql.startswith("*/", i):
                    depth, i = depth - 1, i + 2
                else:
                    i += 1
        elif c == "'" or (c in "eE" and sql.startswith("'", i + 1)):
            backslash = c != "'"
            i += 1 if c == "'" else 2
            while True:
                if i >= n:
                    raise _ParseError("unterminated string literal")
                if backslash and sql[i] == "\\":
                    i += 2
                elif sql[i] == "'":
                    if sql.startswith("'", i + 1):
                        i += 2
                    else:
                        i += 1
                        break
                else:
                    i += 1
            toks.append(_Tok("string", ""))
        elif c == '"':
            j, parts = i + 1, []
            while True:
                k = sql.find('"', j)
                if k < 0:
                    raise _ParseError("unterminated quoted identifier")
                parts.append(sql[j:k])
                if sql.startswith('"', k + 1):
                    parts.append('"')
                    j = k + 2
                else:
                    i = k + 1
                    break
            toks.append(_Tok("ident", "".join(parts)))
        elif c == "$":
            if i + 1 < n and sql[i + 1].isdigit():
                j = i + 1
                while j < n and sql[j].isdigit():
                    j += 1
                toks.append(_Tok("param", sql[i:j]))
                i = j
            else:
                m = _DOLLAR_TAG.match(sql, i)
                if not m:
                    raise _ParseError("stray '$'")
                end = sql.find(m.group(0), m.end())
                if end < 0:
                    raise _ParseError("unterminated dollar-quoted string")
                toks.append(_Tok("string", ""))
                i = end + len(m.group(0))
        elif _is_ident_start(c):
            j = i + 1
            while j < n and _is_ident_char(sql[j]):
                j += 1
            toks.append(_Tok("word", sql[i:j].lower()))
            i = j
        elif c.isdigit():
            j = i + 1
            while j < n and (sql[j].isalnum() or sql[j] in "._"):
                j += 1
            toks.append(_Tok("num", sql[i:j]))
            i = j
        else:
            toks.append(_Tok("punct", c))
            i += 1
        if starts is not None and len(starts) < len(toks):
            starts.append(start)
    return toks


def _split_statements(toks: list[_Tok]) -> list[list[_Tok]]:
    stmts, cur = [], []
    for t in toks:
        if t == _Tok("punct", ";"):
            if cur:
                stmts.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        stmts.append(cur)
    return stmts


def _side_effect_call(toks: list[_Tok]) -> str | None:
    """Name of the first side-effecting function call, if any."""
    for t, nxt in zip(toks, toks[1:]):
        if t.kind in ("word", "ident") and nxt == _Tok("punct", "("):
            name = t.text if t.kind == "ident" else t.text.lower()
            if name in SIDE_EFFECT_FUNCTIONS or name.startswith(SIDE_EFFECT_PREFIXES):
                return name
    return None


def _forbidden(reason: str) -> Verdict:
    return Verdict("forbidden", reason)


def _classify_read(toks: list[_Tok]) -> Verdict:
    words = [t.text for t in toks if t.kind == "word"]
    for w in words:
        if w in WRITE_KEYWORDS:
            return _forbidden(
                f"This query contains {w.upper()}, which modifies the database. "
                "Only read-only queries are allowed here; the only permitted write is "
                "CREATE INDEX, through apply_index."
            )
    if "into" in words:
        return _forbidden("SELECT ... INTO creates a table and is not allowed. Remove the INTO clause.")
    for a, b in zip(words, words[1:]):
        if a == "for" and b in ("update", "share", "no", "key"):
            return _forbidden("Row-locking clauses (FOR UPDATE / FOR SHARE) are not allowed. Remove them.")
    fn = _side_effect_call(toks)
    if fn:
        return _forbidden(f"{fn}() has side effects outside a read-only query and is not allowed.")
    return Verdict("read")


_CREATE_INDEX_FORM = (
    "Expected: CREATE [UNIQUE] INDEX [CONCURRENTLY] [IF NOT EXISTS] [name] "
    "ON [ONLY] table [USING method] (columns) ..."
)


def _classify_create_index(toks: list[_Tok]) -> Verdict:
    i = 1  # past CREATE
    def word(k: int) -> str | None:
        return toks[k].text if k < len(toks) and toks[k].kind == "word" else None

    if word(i) == "unique":
        i += 1
    if word(i) != "index":
        return _forbidden(
            "Only CREATE INDEX is allowed (through apply_index). Other CREATE statements are forbidden."
        )
    i += 1
    concurrently = word(i) == "concurrently"
    if concurrently:
        i += 1
    if word(i) == "if" and word(i + 1) == "not" and word(i + 2) == "exists":
        i += 3
    if word(i) != "on" and i < len(toks) and toks[i].kind in ("word", "ident"):
        i += 1  # index name
    if word(i) != "on":
        return _forbidden("CREATE INDEX is missing ON <table>. " + _CREATE_INDEX_FORM)
    i += 1
    if word(i) == "only":
        i += 1
    parts = []
    while i < len(toks) and toks[i].kind in ("word", "ident"):
        parts.append(toks[i].text)
        i += 1
        if i < len(toks) and toks[i] == _Tok("punct", "."):
            i += 1
        else:
            break
    if not parts:
        return _forbidden("CREATE INDEX is missing the table name. " + _CREATE_INDEX_FORM)
    if word(i) == "using":
        i += 2
    if i >= len(toks) or toks[i] != _Tok("punct", "("):
        return _forbidden("CREATE INDEX is missing the column list. " + _CREATE_INDEX_FORM)
    fn = _side_effect_call(toks[i:])
    if fn:
        return _forbidden(f"{fn}() has side effects and cannot appear in an index definition.")
    return Verdict("create_index", table=".".join(parts), concurrently=concurrently)


def classify(sql: str) -> Verdict:
    """Classify exactly one SQL statement.

    Rules:
      * comments and string/identifier/dollar-quoted literals are ignored;
      * more than one statement -> forbidden;
      * SELECT / WITH / VALUES / TABLE / SHOW with no write keyword, no
        data-modifying CTE, no FOR UPDATE/SHARE, no SELECT INTO, and no
        side-effecting function -> read;
      * CREATE [UNIQUE] INDEX [CONCURRENTLY] ... ON <table> (...) -> create_index;
      * everything else -> forbidden.
    """
    try:
        toks = _tokenize(sql)
    except _ParseError as e:
        return _forbidden(f"Could not parse the SQL ({e}). Check quoting and comments.")
    stmts = _split_statements(toks)
    if not stmts:
        return _forbidden("The SQL is empty. Send one statement.")
    if len(stmts) > 1:
        return _forbidden(_ONE_STATEMENT)
    stmt = stmts[0]
    first = next((t for t in stmt if t != _Tok("punct", "(")), None)
    if first is None or first.kind != "word":
        return _forbidden("Could not recognise the statement. Send one SELECT, WITH, VALUES, TABLE or SHOW query.")
    head = first.text
    if head in READ_STARTS:
        return _classify_read(stmt)
    if head == "create":
        return _classify_create_index(stmt)
    if head == "explain":
        return _forbidden("Use the explain_query tool to get a query plan instead of running EXPLAIN directly.")
    if head == "drop" or head == "reindex" or head == "alter":
        return _forbidden(
            f"{head.upper()} is not allowed. The only permitted schema change is CREATE INDEX, through apply_index."
        )
    return _forbidden(
        f"{head.upper()} statements are not allowed. Only read-only queries "
        "(SELECT, WITH, VALUES, TABLE, SHOW) and CREATE INDEX are permitted."
    )


# --------------------------------------------------------------------------- helpers for callers

def leading_keyword(sql: str) -> str | None:
    """The statement's first keyword, lowercased (after comments and opening
    parentheses), e.g. 'select', 'with', 'show'. None if there is none or the SQL
    doesn't lex."""
    try:
        toks = _tokenize(sql)
    except _ParseError:
        return None
    first = next((t for t in toks if t != _Tok("punct", "(")), None)
    return first.text if first is not None and first.kind == "word" else None


def strip_terminator(sql: str) -> str:
    """`sql` up to its first top-level ';' (ignoring any inside quotes or comments),
    so that a single statement can be embedded in a larger one. Text after the ';'
    is dropped. Call only on SQL that classify() accepted as one statement."""
    starts: list[int] = []
    try:
        toks = _tokenize(sql, starts)
    except _ParseError:
        return sql
    for tok, pos in zip(toks, starts):
        if tok == _Tok("punct", ";"):
            return sql[:pos]
    return sql
