"""SQL dialect layer.

Every SQL statement in the codebase is written once, in a *canonical* form:
PostgreSQL-flavoured SQL with numbered ``$n`` parameters (this is what the
codebase already uses, so no existing statement has to change).

A :class:`Dialect` translates that canonical form into whatever the active
driver understands. ``PostgresDialect`` is a no-op translator, so switching the
layer on must not change PostgreSQL behaviour by a single byte. ``SqliteDialect``
rewrites the handful of PostgreSQL-only constructs listed in
:data:`SQLITE_UNSUPPORTED`.

Translation is cached on the SQL text, because the set of distinct statement
strings in the process is small and fixed (they are all literals) while the
call rate is high.

Rewrites performed for SQLite
-----------------------------
===================================  ==========================================
canonical (PostgreSQL)               SQLite
===================================  ==========================================
``$n`` (numbered, re-usable)         ``?`` (positional, repeated per use)
``x = ANY($3)``                      ``x IN (?, ?, ...)`` (list arg expanded)
``NOW()``                            ``CURRENT_TIMESTAMP``
``EXTRACT(EPOCH FROM c)``            ``unixepoch(c)``
``GREATEST(a, b)`` / ``LEAST(a, b)`` ``MAX(a, b)`` / ``MIN(a, b)``
``ILIKE``                            ``LIKE``
``expr::type``                       ``expr`` (casts are dropped)
``FOR UPDATE`` / ``FOR SHARE``       stripped (single-writer, no row locks)
===================================  ==========================================

``<> ANY(...)`` is deliberately *not* rewritten: it means "differs from at
least one element", which is not ``NOT IN`` ("differs from all"). Nothing in the
codebase uses it, so it stays untranslated and is reported by the audit script
instead of being silently mistranslated.

Already compatible, verified against SQLite 3.53: ``ON CONFLICT ... DO UPDATE
SET x = EXCLUDED.x``, ``RETURNING``, ``COALESCE``, ``TRUE``/``FALSE`` literals,
CTEs and window functions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

# Constructs that need a hand-written per-call-site port instead of a textual
# rewrite. The audit script (scripts/sql_dialect_audit.py) reports every hit;
# the translator leaves them untouched, which makes them fail loudly rather
# than silently return wrong rows.
SQLITE_UNSUPPORTED: tuple[str, ...] = (
    "unnest(",   # PostgreSQL array expansion -> expand in Python (executemany)
    "distinct on",  # -> ROW_NUMBER() OVER (PARTITION BY ...)
    "nextval(",  # PostgreSQL sequences -> sqlite_sequence / explicit id
    "setval(",
    "pg_get_serial_sequence(",
    "interval '",  # -> SQLite datetime() modifiers
    "advisory",
)

_RE_PARAM = re.compile(r"\$(\d+)")

# ``::jsonb``, ``::BIGINT[]``, ``::character varying``, ``::numeric(10,2)``.
#
# Multi-word type names must be an explicit whitelist tried *before* the
# single-word branch. A generic ``(?:\s+NAME)*`` tail looks reasonable but
# swallows the rest of the statement: ``::bigint AS u FROM commanders c``
# parses as the type ``bigint AS u FROM commanders c`` and the query loses
# everything up to the next punctuation mark.
_TYPE_NAMES = (
    r"timestamp\s+with\s+time\s+zone",
    r"timestamp\s+without\s+time\s+zone",
    r"time\s+with\s+time\s+zone",
    r"time\s+without\s+time\s+zone",
    r"character\s+varying",
    r"double\s+precision",
    r"bit\s+varying",
    r"[A-Za-z_][A-Za-z0-9_]*",
)
_RE_CAST = re.compile(
    r"::\s*(?:" + "|".join(_TYPE_NAMES) + r")"
    r"(?:\s*\([^)]*\))?"
    r"(?:\s*\[\s*\])?",
    re.IGNORECASE,
)

# ``x = ANY($3)`` -- the ``=`` is part of the match because ``x = IN (...)`` is
# not valid SQL. ``<> ANY`` is intentionally excluded: see the module docstring.
#
# ``:name`` (SQLAlchemy named parameter) is matched too, but only for the
# text-only translation used by the audit script: those statements are compiled
# by SQLAlchemy, which turns ``:name`` into a qmark *before* the statement
# reaches this layer. The qmark spelling is expanded at the driver boundary by
# ``src.db.sqlite_sa_dialect._expand_any_qmark``, which is the only place that
# can see the bound values.
_RE_ANY = re.compile(
    r"=\s*ANY\s*\(\s*"
    r"(?P<p>\$(?P<n>\d+)|:\w+)"
    r"\s*(?:::[^)]*)?"
    r"\)",
    re.IGNORECASE,
)

_RE_EXTRACT_EPOCH = re.compile(r"EXTRACT\s*\(\s*EPOCH\s+FROM\b", re.IGNORECASE)
_RE_NOW = re.compile(r"\bNOW\s*\(\s*\)", re.IGNORECASE)
_RE_ILIKE = re.compile(r"\bILIKE\b", re.IGNORECASE)
_RE_GREATEST = re.compile(r"\bGREATEST\s*\(", re.IGNORECASE)
_RE_LEAST = re.compile(r"\bLEAST\s*\(", re.IGNORECASE)
# Row locks are meaningless in SQLite (single writer, database-level locking in
# WAL mode), so the PostgreSQL lock clauses are stripped instead of failing.
_RE_FOR_UPDATE = re.compile(r"\bFOR\s+UPDATE\b(?:\s+(?:NOWAIT|SKIP\s+LOCKED))?", re.IGNORECASE)
_RE_FOR_SHARE = re.compile(r"\bFOR\s+SHARE\b(?:\s+(?:NOWAIT|SKIP\s+LOCKED))?", re.IGNORECASE)
# PostgreSQL accepts "OFFSET n LIMIT m" in either order; SQLite requires LIMIT
# first. Only placeholder/literal operands are matched -- a bare ``?`` is
# excluded because swapping the TEXT would silently swap the positional
# bindings (handled with a parameter swap in src.db.sqlite_sa_dialect instead).
_RE_OFFSET_LIMIT = re.compile(
    r"\bOFFSET\s+(?P<off>\$\d+|:\w+|\d+)\s+LIMIT\s+(?P<lim>\$\d+|:\w+|\d+)",
    re.IGNORECASE,
)
# Bare `index` column (guild_shop_goods / medal_shop_goods): usable unquoted
# in PostgreSQL (unreserved keyword) but reserved in SQLite, where
# "SELECT ... index ..." dies with 'near "index": syntax error'. Quoted in
# DML statements only; CREATE/DROP/REINDEX statements keep keyword semantics
# (rewrite_ddl quotes column definitions there, and CREATE/DROP INDEX are
# early-handled).
_RE_BARE_INDEX = re.compile(r'(?<![\w"])index(?![\w"])', re.IGNORECASE)
_RE_DDL_START = re.compile(r"\s*(CREATE|DROP|REINDEX)\b", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Scanner: split SQL into rewritable code and verbatim literal/comment spans
# --------------------------------------------------------------------------- #


@dataclass
class _Segment:
    text: str
    code: bool  # True -> SQL code, safe to rewrite. False -> verbatim.


def _scan(sql: str) -> list[_Segment]:
    """Split ``sql`` into code segments and verbatim segments.

    Verbatim segments are single-quoted strings (with ``''`` escapes),
    double-quoted identifiers, ``--`` line comments, ``/* */`` block comments
    and PostgreSQL ``$$...$$`` dollar-quoted bodies. Rewriting inside them would
    corrupt data such as ``'[]'::jsonb`` or a ``$1`` that happens to appear in a
    message body.
    """
    segments: list[_Segment] = []
    buf: list[str] = []
    i = 0
    n = len(sql)

    def flush(code: bool) -> None:
        if buf:
            segments.append(_Segment("".join(buf), code))
            buf.clear()

    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""

        # -- line comment
        if ch == "-" and nxt == "-":
            flush(True)
            j = sql.find("\n", i)
            j = n if j < 0 else j + 1
            segments.append(_Segment(sql[i:j], False))
            i = j
            continue

        # /* block comment */
        if ch == "/" and nxt == "*":
            flush(True)
            j = sql.find("*/", i + 2)
            j = n if j < 0 else j + 2
            segments.append(_Segment(sql[i:j], False))
            i = j
            continue

        # single-quoted string ('')
        if ch == "'":
            flush(True)
            j = i + 1
            while j < n:
                if sql[j] == "'":
                    if j + 1 < n and sql[j + 1] == "'":
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            segments.append(_Segment(sql[i:j], False))
            i = j
            continue

        # double-quoted identifier ("")
        if ch == '"':
            flush(True)
            j = i + 1
            while j < n:
                if sql[j] == '"':
                    if j + 1 < n and sql[j + 1] == '"':
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            segments.append(_Segment(sql[i:j], False))
            i = j
            continue

        # dollar-quoted body ($$tag$ ... $tag$)
        if ch == "$":
            m = re.match(r"\$([A-Za-z_][A-Za-z0-9_]*)?\$", sql[i:])
            if m:
                tag = m.group(0)
                end = sql.find(tag, i + len(tag))
                if end >= 0:
                    flush(True)
                    j = end + len(tag)
                    segments.append(_Segment(sql[i:j], False))
                    i = j
                    continue

        buf.append(ch)
        i += 1

    flush(True)
    return segments


def _find_matching_paren(text: str, open_idx: int) -> int:
    """Index of the ``)`` matching the ``(`` at ``open_idx``, or -1."""
    depth = 0
    in_str = False
    i = open_idx
    n = len(text)
    while i < n:
        ch = text[i]
        if in_str:
            if ch == "'":
                if i + 1 < n and text[i + 1] == "'":
                    i += 2
                    continue
                in_str = False
            i += 1
            continue
        if ch == "'":
            in_str = True
            i += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


# --------------------------------------------------------------------------- #
# Dialects
# --------------------------------------------------------------------------- #


@dataclass
class Dialect:
    """Translates canonical SQL into a driver-specific form."""

    name: str
    paramstyle: str  # "numeric" ($n) | "qmark" (?)
    supports_arrays: bool = False
    supports_jsonb: bool = False
    supports_schemas: bool = False
    supports_advisory_locks: bool = False
    supports_sequences: bool = False
    quote_char: str = '"'
    _cache: dict[Any, tuple[str, tuple[int, ...]]] = field(
        default_factory=dict, repr=False, compare=False
    )

    # -- public API --------------------------------------------------------- #

    def prepare(self, sql: str, args: Sequence[Any] = ()) -> tuple[str, list[Any]]:
        """Return ``(sql, args)`` ready for the driver.

        ``order`` holds 0-based indices into the concatenation of the caller's
        ``args`` followed by the dialect's generated ``extra`` values (an
        ``ANY()`` list expansion). Extra values depend on the *contents* of a
        list argument, so those statements are deliberately not cached.
        """
        key = self._cache_key(sql, args)
        hit = self._cache.get(key)
        if hit is not None:
            compiled, order = hit
            pool: tuple[Any, ...] = tuple(args)
        else:
            compiled, order, extra = self._compile(sql, args)
            pool = tuple(args) + tuple(extra)
            if not extra and len(self._cache) < 4096:
                self._cache[key] = (compiled, order)
        try:
            return compiled, [pool[i] for i in order]
        except IndexError:
            raise IndexError(
                f"dialect {self.name}: statement has more $n placeholders than "
                f"supplied arguments ({len(order)} placeholders vs {len(args)} args)"
            ) from None

    def translate(self, sql: str) -> str:
        """Rewrite SQL text only, leaving ``$n`` placeholders in place.

        For static analysis (``scripts/sql_dialect_audit.py``) and logging,
        where no parameter values are available. ``ANY($n)`` / ``ANY(:name)``
        collapses to ``IN ($n)`` / ``IN (:name)`` instead of being expanded.
        """
        return self._compile(sql, (), text_only=True)[0]

    def quote_ident(self, name: str) -> str:
        q = self.quote_char
        return f"{q}{name.replace(q, q + q)}{q}"

    def qualify(self, schema: str, name: str) -> str:
        if not schema or not self.supports_schemas:
            return self.quote_ident(name)
        return f"{self.quote_ident(schema)}.{self.quote_ident(name)}"

    def rewrite_ddl(self, sql: str) -> str:
        """Translate a migration script. Overridden per dialect."""
        return sql

    def supports(self, sql: str) -> Optional[str]:
        """Return the unsupported construct found in ``sql``, else ``None``."""
        low = sql.lower()
        for item in self._unsupported():
            if item in low:
                return item
        return None

    def resync_identity_sql(self, table: str, column: str = "id") -> str:
        """Statement re-syncing an auto-increment counter after explicit-id inserts.

        PostgreSQL sequences are not advanced by inserts that supply the id, so
        the counter has to be nudged back to ``MAX(id)``. SQLite derives the next
        rowid from ``MAX(rowid) + 1`` on every insert, so it needs nothing; an
        empty string means "skip this".
        """
        return ""

    # -- hooks -------------------------------------------------------------- #

    def _unsupported(self) -> tuple[str, ...]:
        return ()

    def _cache_key(self, sql: str, args: Sequence[Any]) -> Any:
        # ``ANY($n)`` expansion depends on the *length* of the list argument, so
        # the key has to include the shape of the arguments, not just the SQL.
        shape = tuple(len(a) for a in args if isinstance(a, (list, tuple, set, frozenset)))
        return (sql, shape)

    def _compile(
        self,
        sql: str,
        args: Sequence[Any],
        text_only: bool = False,
    ) -> tuple[str, tuple[int, ...], list[Any]]:
        """Return ``(compiled_sql, arg_order, extra_values)``.

        ``text_only`` keeps ``$n`` placeholders unexpanded; see :meth:`translate`.
        """
        raise NotImplementedError


class PostgresDialect(Dialect):
    """Identity translator -- canonical SQL *is* PostgreSQL SQL."""

    def __init__(self) -> None:
        super().__init__(
            name="postgresql",
            paramstyle="numeric",
            supports_arrays=True,
            supports_jsonb=True,
            supports_schemas=True,
            supports_advisory_locks=True,
            supports_sequences=True,
        )

    def _compile(
        self,
        sql: str,
        args: Sequence[Any],
        text_only: bool = False,
    ) -> tuple[str, tuple[int, ...], list[Any]]:
        # Nothing to rewrite: canonical SQL *is* PostgreSQL SQL, and asyncpg
        # accepts numbered parameters directly.
        return sql, tuple(range(len(args))), []

    def resync_identity_sql(self, table: str, column: str = "id") -> str:
        return (
            f"SELECT setval("
            f"pg_get_serial_sequence('{table}', '{column}'), "
            f"(SELECT MAX({column}) FROM {table}))"
        )

    def next_sequence_value_sql(self, sequence: str) -> str:
        return f"SELECT nextval('{sequence}') AS id"


class SqliteDialect(Dialect):
    """Rewrites canonical SQL for SQLite."""

    def __init__(self) -> None:
        super().__init__(
            name="sqlite",
            paramstyle="qmark",
            supports_arrays=False,
            supports_jsonb=False,
            supports_schemas=False,
            supports_advisory_locks=False,
            supports_sequences=False,
        )

    def _unsupported(self) -> tuple[str, ...]:
        return SQLITE_UNSUPPORTED

    def _compile(
        self,
        sql: str,
        args: Sequence[Any],
        text_only: bool = False,
    ) -> tuple[str, tuple[int, ...], list[Any]]:
        extra: list[Any] = []
        out: list[str] = []
        order: list[int] = []
        quote_index = not _RE_DDL_START.match(sql)

        for seg in _scan(sql):
            if not seg.code:
                out.append(seg.text)
                continue
            text = seg.text
            text = self._rewrite_extract_epoch(text)
            text = self._rewrite_greatest_least(text)
            text = self._rewrite_any(text, args, extra, text_only)
            text = _RE_NOW.sub("CURRENT_TIMESTAMP", text)
            text = _RE_ILIKE.sub("LIKE", text)
            text = _RE_FOR_UPDATE.sub("", text)
            text = _RE_FOR_SHARE.sub("", text)
            text = _RE_OFFSET_LIMIT.sub(r"LIMIT \g<lim> OFFSET \g<off>", text)
            text = _RE_CAST.sub("", text)
            if quote_index:
                text = _RE_BARE_INDEX.sub('"index"', text)
            out.append(text if text_only else self._substitute_params(text, order))

        return "".join(out), tuple(order), extra

    # -- individual rewrites ------------------------------------------------ #

    # strftime() format per EXTRACT field. SQLite has no EXTRACT(); its
    # equivalents are the strftime helpers (%s = unixepoch, %Y, %m, ...).
    _EXTRACT_STRFTIME = {
        "YEAR": "%Y",
        "MONTH": "%m",
        "DAY": "%d",
        "HOUR": "%H",
        "MINUTE": "%M",
        "SECOND": "%S",
    }

    def _rewrite_extract_epoch(self, text: str) -> str:
        """``EXTRACT(EPOCH FROM x)`` -> ``unixepoch(x)``; other date/time
        fields go through :meth:`_rewrite_extract_datetime`.

        The inner expression can itself contain parentheses, so the closing
        paren is found by matching rather than by regex.
        """
        while True:
            m = _RE_EXTRACT_EPOCH.search(text)
            if m is None:
                # Non-EPOCH fields (YEAR/MONTH/...) handled in a second pass.
                return self._rewrite_extract_datetime(text)
            open_idx = text.find("(", m.start())
            if open_idx < 0:
                return self._rewrite_extract_datetime(text)
            close_idx = _find_matching_paren(text, open_idx)
            if close_idx < 0:
                return self._rewrite_extract_datetime(text)
            inner = text[open_idx + 1 : close_idx]
            # 'EPOCH FROM ' prefix lives between the outer '(' and the expression
            inner = re.sub(r"^\s*EPOCH\s+FROM\b", "", inner, flags=re.IGNORECASE).lstrip()
            text = text[: m.start()] + f"unixepoch({inner})" + text[close_idx + 1 :]

    def _rewrite_extract_datetime(self, text: str) -> str:
        """``EXTRACT(<field> FROM x)`` -> ``strftime('<fmt>', x)``."""
        re_dt = re.compile(r"EXTRACT\s*\(\s*(?P<field>YEAR|MONTH|DAY|HOUR|MINUTE|SECOND)\s+FROM\b", re.IGNORECASE)
        while True:
            m = re_dt.search(text)
            if m is None:
                return text
            fmt = self._EXTRACT_STRFTIME[m.group("field").upper()]
            open_idx = text.find("(", m.start())
            if open_idx < 0:
                return text
            close_idx = _find_matching_paren(text, open_idx)
            if close_idx < 0:
                return text
            inner = text[open_idx + 1 : close_idx]
            field = m.group("field")
            inner = re.sub(rf"^\s*{field}\s+FROM\b", "", inner, flags=re.IGNORECASE).lstrip()
            text = text[: m.start()] + f"strftime('{fmt}', {inner})" + text[close_idx + 1 :]

    @staticmethod
    def _rewrite_greatest_least(text: str) -> str:
        text = _RE_GREATEST.sub("MAX(", text)
        text = _RE_LEAST.sub("MIN(", text)
        return text

    @staticmethod
    def _rewrite_any(
        text: str, args: Sequence[Any], extra: list[Any], text_only: bool = False
    ) -> str:
        """``x = ANY($3)`` -> ``x IN (?, ?, ...)``, expanding the list argument.

        Expanded elements are appended to ``extra`` and referenced by a virtual
        parameter number (``len(args) + len(extra)``, 1-based), so the later
        placeholder pass picks them up via the same numbering scheme.
        """

        def repl(m: re.Match) -> str:
            # The match consumes the '=' and any spacing of '= ANY($n)';
            # re-emit ' IN (...)' and let the strip below avoid double spaces
            # for the 'x = ANY(...)' spelling.
            if text_only:
                return f" IN ({m.group('p')})"
            n = m.group("n")
            if n is None:
                # A SQLAlchemy named parameter: the value is not addressable
                # here (it lives in the caller's dict), so leave the statement
                # alone -- src.db.sqlite_sa_dialect expands it after SA has
                # compiled ':name' down to a qmark.
                return m.group(0)
            n = int(n)
            if n < 1 or n > len(args):
                return m.group(0)
            value = args[n - 1]
            items = list(value) if isinstance(value, (list, tuple, set, frozenset)) else [value]
            if not items:
                # ``IN ()`` is a syntax error in SQLite. An empty PostgreSQL
                # array matches no row, and ``IN (NULL)`` evaluates to NULL,
                # which also matches no row -- while keeping the ``x IN (...)``
                # shape intact so the surrounding operator stays valid.
                return " IN (NULL)"
            refs = []
            for item in items:
                extra.append(item)
                refs.append(f"${len(args) + len(extra)}")
            return f" IN ({', '.join(refs)})"

        out = _RE_ANY.sub(repl, text)
        # Collapse the double space left when the source spelled 'x = ANY(...)'.
        return re.sub(r"(\S)  +IN \(", r"\1 IN (", out)

        return _RE_ANY.sub(repl, text)

    def rewrite_ddl(self, sql: str) -> str:
        """Translate PostgreSQL DDL into SQLite-compatible DDL.

        Covers the constructs present in ``sql/*.sql`` migration scripts:

        * Type mapping: ``JSONB``→``TEXT``, ``BYTEA``→``BLOB``,
          ``TIMESTAMPTZ``/``TIMESTAMP WITH TIME ZONE``→``TEXT``,
          ``BOOLEAN``→``INTEGER``, ``SERIAL``/``BIGSERIAL``→``INTEGER``.
        * Default rewrites: ``'[]'::jsonb``→``'[]'``, ``'{}'::jsonb``→``'{}'``,
          ``TRUE``/``FALSE`` literals stay (SQLite accepts them).
        * ``CREATE SEQUENCE`` / ``setval`` / ``nextval`` statements are
          turned into no-op comment lines (SQLite has no sequences; the
          ``_next_account_id`` helper derives ids from ``MAX()+1`` instead).
        * ``CREATE SCHEMA`` is skipped (SQLite has no schemas).
        * ``DO $$ ... $$;`` anonymous blocks are dropped: they only carry
          PostgreSQL identity/sequence maintenance (unneeded on SQLite,
          where ``INTEGER PRIMARY KEY`` auto-increments) and legacy table
          renames guarded by ``to_regclass`` (irrelevant on a fresh file).
        * ``ALTER TABLE t ADD COLUMN IF NOT EXISTS a, ADD COLUMN ... b`` is
          split into one ``ALTER TABLE t ADD COLUMN`` statement per column:
          SQLite has neither ``ADD COLUMN IF NOT EXISTS`` nor multi-column
          ADD. Idempotence is preserved by the migrator's version bookkeeping
          (each migration runs exactly once per database).
        """
        # Pre-pass: expand multi-column ALTER TABLE ... ADD COLUMN before the
        # line-oriented translation below sees the pieces.
        sql = self._expand_alter_add_columns(sql)
        out: list[str] = []
        i = 0
        lines = sql.split("\n")
        n = len(lines)
        skipping_stmt = False
        while i < n:
            line = lines[i]
            if skipping_stmt:
                # Swallow the remainder of a multi-line statement that was
                # already neutralized (e.g. SELECT setval(...)) up to the
                # line whose trailing punctuation closes the statement.
                if line.rstrip().endswith(";") or line.rstrip().endswith(")"):
                    # A ")" alone can close setval(...); the ";" may live on
                    # the same or the next line -- keep swallowing until ";",
                    # or the ")" that balances the opened call.
                    if line.rstrip().endswith(";"):
                        skipping_stmt = False
                i += 1
                continue
            low = line.strip().lower()
            if ("setval(" in low or "nextval(" in low) and not low.startswith("--"):
                out.append(f"-- [sqlite] sequence call skipped: {line.strip()}")
                # find the statement end: a line ending with ';' possibly
                # followed by ')' before it -- simplest: until a line whose
                # stripped form ends with ';'
                j = i
                depth_open = line.count("(") - line.count(")")
                while j < n:
                    if depth_open <= 0 and lines[j].rstrip().endswith(";"):
                        break
                    depth_open += lines[j].count("(") - lines[j].count(")")
                    if lines[j].rstrip().endswith(";") and depth_open <= 0:
                        break
                    j += 1
                i = j + 1
                continue
            if self._is_do_block_start(line):
                # Skip through the closing $$ (same line or a later one).
                stripped = line.strip()
                # "DO $$ ... $$;" -- opening AND closing tag on one line.
                if stripped.count("$$") >= 2:
                    i += 1
                    out.append("-- [sqlite] DO $$ block skipped")
                    continue
                i += 1
                while i < n and "$$" not in lines[i]:
                    i += 1
                i += 1  # consume the closing $$ line
                out.append("-- [sqlite] DO $$ block skipped")
                continue
            translated = self._rewrite_ddl_line(line)
            if translated is not None:
                out.append(translated)
            i += 1
        return "\n".join(out)

    @staticmethod
    def _is_do_block_start(line: str) -> bool:
        low = line.strip().lower()
        return low.startswith("do $") or low == "do"

    _RE_ALTER_ADD = re.compile(
        r"ALTER\s+TABLE\s+(?P<table>\S+)\s+ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+(?P<body>[^;]+);",
        re.IGNORECASE,
    )

    @classmethod
    def _expand_alter_add_columns(cls, sql: str) -> str:
        """Split ``ALTER TABLE t ADD COLUMN a, ADD COLUMN b;`` into one
        statement per column, dropping ``IF NOT EXISTS`` (SQLite's ADD COLUMN
        has neither the guard nor the comma form)."""

        def repl(m: re.Match) -> str:
            table = m.group("table")
            body = m.group("body")
            parts = re.split(r",\s*(?=ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+)", body, flags=re.IGNORECASE)
            stmts = []
            for part in parts:
                part = part.strip()
                part = re.sub(r"^ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+", "", part, flags=re.IGNORECASE)
                part = cls._rewrite_ddl_line(part) or part
                stmts.append(f"ALTER TABLE {table} ADD COLUMN {part};")
            return "\n".join(stmts)

        return cls._RE_ALTER_ADD.sub(repl, sql)

    @staticmethod
    def _rewrite_ddl_line(line: str) -> Optional[str]:
        """Translate one line of DDL. Return ``None`` to drop the line."""
        low = line.strip().lower()

        # Skip PostgreSQL schema creation entirely.
        if low.startswith("create schema") or low.startswith("drop schema"):
            return None

        # CREATE INDEX CONCURRENTLY -> plain CREATE INDEX (SQLite builds its
        # index in one shot anyway; there are no concurrent writers to lock).
        result = line
        if low.startswith("create index") or low.startswith("create unique index"):
            result = re.sub(r"\bCONCURRENTLY\b", "", result, flags=re.IGNORECASE)

        # CREATE SEQUENCE / setval / nextval -- no SQLite equivalent.
        if low.startswith("create sequence") or low.startswith("drop sequence"):
            return f"-- [sqlite] sequence skipped: {line.strip()}"
        if "setval(" in low or "nextval(" in low:
            return f"-- [sqlite] sequence call skipped: {line.strip()}"
        if low.startswith("-- [sqlite] sequence"):
            return line

        # DEFAULT now() / DEFAULT NOW() -> CURRENT_TIMESTAMP (the SQLite
        # spelling of "transaction start time" usable inside DEFAULT).
        result = re.sub(r"\bnow\s*\(\s*\)", "CURRENT_TIMESTAMP", result, flags=re.IGNORECASE)

        # `id bigint PRIMARY KEY` -> `id INTEGER PRIMARY KEY`: PostgreSQL marks
        # these as IDENTITY (e.g. sql/0024_builds.sql, sql/0058_owned_ships.sql) so inserts without an id generate
        # one; on SQLite "INTEGER PRIMARY KEY" is the rowid alias and does the
        # same. Explicit-id inserts keep working on both spellings.
        result = re.sub(
            r"\bid\s+bigint\s+PRIMARY\s+KEY\b",
            "id INTEGER PRIMARY KEY",
            result,
            flags=re.IGNORECASE,
        )

        # EXTRACT(EPOCH/YEAR/MONTH/... FROM x) -> unixepoch(x)/strftime(...):
        # data-backfill statements inside migrations carry them too.
        dialect = SqliteDialect()
        result = dialect._rewrite_extract_epoch(result)

        # Type rewrites. Order matters: multi-word types before single-word.
        # TIMESTAMPTZ -> DATETIME (NOT TEXT): sqlite_types registers a
        # "datetime" converter so reads return aware datetime objects, matching
        # what asyncpg/psycopg2 deliver for timestamptz on PostgreSQL.
        result = re.sub(
            r"\btimestamptz\b", "DATETIME", result, flags=re.IGNORECASE
        )
        result = re.sub(
            r"\btimestamp\s+with\s+time\s+zone\b", "DATETIME", result, flags=re.IGNORECASE
        )
        # TIMESTAMP WITHOUT TIME ZONE -> DATETIME as well (same converter).
        result = re.sub(
            r"\btimestamp\s+without\s+time\s+zone\b", "DATETIME", result, flags=re.IGNORECASE
        )
        # JSONB -> TEXT
        # JSONB -> JSON (NOT TEXT): with PARSE_DECLTYPES, sqlite_types'
        # "json" converter parses the stored text so reads return dict/list,
        # matching SQLAlchemy's JSONB behaviour on PostgreSQL.
        result = re.sub(r"\bjsonb\b", "JSON", result, flags=re.IGNORECASE)
        # BYTEA -> BLOB
        result = re.sub(r"\bbytea\b", "BLOB", result, flags=re.IGNORECASE)
        # SERIAL / BIGSERIAL -> INTEGER (SQLite AUTOINCREMENT is handled by
        # the PRIMARY KEY clause; "INTEGER PRIMARY KEY" auto-increments).
        result = re.sub(r"\bbigserial\b", "INTEGER", result, flags=re.IGNORECASE)
        result = re.sub(r"\bserial\b", "INTEGER", result, flags=re.IGNORECASE)

        # Cast rewrites: '[]'::jsonb -> '[]', '{}'::jsonb -> '{}', etc.
        # The generic ::cast rewriter from _RE_CAST handles runtime queries,
        # but in DDL the cast is part of a DEFAULT clause and must survive
        # as a plain literal.
        result = re.sub(
            r"('(?:\[\]|\{\}|[^']*)')::\s*(?:jsonb|json)\b",
            r"\1",
            result,
            flags=re.IGNORECASE,
        )
        # Strip remaining ::type casts (e.g. ::bigint, ::text).
        result = _RE_CAST.sub("", result)

        # Quote the column name `index`: allowed unquoted in PostgreSQL DDL,
        # but a reserved keyword in SQLite. DML statements get the same
        # quoting in SqliteDialect._compile; here it makes the created table
        # match that spelling.
        result = re.sub(
            r'(?<![\w"])index(?![\w"])', '"index"', result
        )
        return result

    @staticmethod
    def _substitute_params(text: str, order: list[int]) -> str:
        """``$n`` -> ``?``, repeating/reordering parameters by appearance."""

        def repl(m: re.Match) -> str:
            order.append(int(m.group(1)) - 1)
            return "?"

        return _RE_PARAM.sub(repl, text)


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #

_DIALECTS: dict[str, Dialect] = {
    "postgresql": PostgresDialect(),
    "postgres": PostgresDialect(),
    "sqlite": SqliteDialect(),
    "sqlite3": SqliteDialect(),
}


def get_dialect(name: str) -> Dialect:
    try:
        return _DIALECTS[(name or "postgresql").strip().lower()]
    except KeyError:
        raise ValueError(
            f"unknown database dialect {name!r} "
            f"(supported: {', '.join(sorted(set(_DIALECTS)))})"
        ) from None


_current: Optional[Dialect] = None


def current_dialect() -> Dialect:
    """The process-wide dialect, derived from ``[database] dsn`` in configurations/server.json.

    Falls back to PostgreSQL so that anything importing this before the config
    is loaded keeps today's behaviour.
    """
    global _current
    if _current is None:
        try:
            from src.config.config import current

            cfg = current().database
            if cfg.driver.strip():
                _current = get_dialect(cfg.driver)
            else:
                _current = detect_dialect(cfg.dsn)
        except Exception:  # pragma: no cover - config not loaded yet
            _current = get_dialect("postgresql")
    return _current


def set_dialect(dialect: Dialect) -> None:
    """Pin the process-wide dialect (used by startup and by tests)."""
    global _current
    _current = dialect


def reset_dialect() -> None:
    """Drop the cached dialect so the next call re-reads the config."""
    global _current
    _current = None


def detect_dialect(dsn: str) -> Dialect:
    """Pick the dialect from a DSN.

    ``sqlite:///path/to.db`` (or ``file:...``, or a bare ``*.db`` path) selects
    SQLite; anything else is treated as PostgreSQL, which keeps every existing
    configuration working unchanged.
    """
    raw = (dsn or "").strip()
    low = raw.lower()
    if low.startswith("sqlite:") or low.startswith("file:"):
        return get_dialect("sqlite")
    if low.endswith(".db") or low.endswith(".sqlite") or low.endswith(".sqlite3"):
        return get_dialect("sqlite")
    if "://" not in raw:
        # A bare filesystem path with no scheme -> SQLite.
        return get_dialect("sqlite")
    return get_dialect("postgresql")
