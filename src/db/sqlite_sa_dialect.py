"""SQLAlchemy SQLite dialect that translates canonical (PostgreSQL-flavoured)
SQL at the driver boundary.

Statements that go through ``src.db.store`` are translated by
``src.db.dialect.Dialect.prepare``. ORM ``text()`` statements bypass that
path but still speak the canonical dialect (``NOW()``, ``::casts``,
``FOR UPDATE``), so the SQLAlchemy sqlite dialects below run the same
``SqliteDialect.translate`` inside ``do_execute``/``exec_driver_sql``.
"""
from __future__ import annotations

import datetime as _dt
import re
import sqlite3 as _sqlite3

from sqlalchemy import types as _satypes
from sqlalchemy.dialects.sqlite.aiosqlite import SQLiteDialect_aiosqlite
from sqlalchemy.dialects.sqlite.base import DATETIME as _SqliteDATETIME
from sqlalchemy.dialects.sqlite.pysqlite import SQLiteDialect_pysqlite

from src.db.dialect import SqliteDialect

_TRANSLATOR = SqliteDialect()

# After SA compilation the ORM text() statements carry qmark placeholders, so
# "OFFSET ? LIMIT ?" (PostgreSQL-legal order) cannot be fixed by a text swap
# alone: the two bound values would swap meaning with the clause. Rewrite the
# clause and swap the corresponding parameter values together.
_RE_QMARK_OFFSET_LIMIT = re.compile(r"\bOFFSET\s+\?\s+LIMIT\s+\?", re.IGNORECASE)

# Same story for ``x = ANY(?)``: the canonical ``ANY($n)`` reaches do_execute
# as ``ANY(?)``, so SqliteDialect.translate (which sees text only, no values)
# leaves it alone and SQLite dies with 'no such function: ANY'. The bound value
# is still the caller's list, so it can be spliced in at the driver boundary.
_RE_QMARK_ANY = re.compile(
    r"=\s*ANY\s*\(\s*\?\s*(?:::[^)]*)?\s*\)",
    re.IGNORECASE,
)

# Single-quoted SQL literals ('...' with '' escapes): a '?' inside one is data,
# not a placeholder, so it must not be counted when locating a binding.
_RE_SQL_LITERAL = re.compile(r"'(?:[^']|'')*'")


def _expand_any_qmark(statement: str, parameters):
    """``x = ANY(?)`` -> ``x IN (?, ?, ...)``, splicing the bound list in place.

    The value bound to that ``?`` is the Python list the caller would have
    passed to PostgreSQL as an array. Replacing it with its elements keeps
    every other binding aligned, because the expansion happens at exactly the
    position the placeholder occupied.
    """
    if parameters is None or "ANY" not in statement.upper():
        return statement, parameters
    try:
        params = list(parameters)
    except TypeError:  # pragma: no cover - dict-style bindings have no order
        return statement, parameters

    out = statement
    while True:
        m = _RE_QMARK_ANY.search(out)
        if m is None:
            break
        idx = _RE_SQL_LITERAL.sub("''", out[: m.start()]).count("?")
        if idx >= len(params):
            # The placeholder cannot be mapped to a value: leave the statement
            # untouched so the failure is the driver's, not a silent wrong-row
            # result from a mis-aligned parameter list.
            break
        value = params[idx]
        items = list(value) if isinstance(value, (list, tuple, set, frozenset)) else [value]
        if items:
            # The match starts at '=', so the prefix still carries the space
            # that separated the column from the operator.
            replacement = "IN (" + ", ".join(["?"] * len(items)) + ")"
            params[idx : idx + 1] = items
        else:
            # ``IN ()`` is a syntax error in SQLite. An empty array matches no
            # row, and ``IN (NULL)`` evaluates to NULL -- which also matches no
            # row -- while keeping the statement shape valid.
            replacement = "IN (NULL)"
            params[idx : idx + 1] = []
        out = out[: m.start()].rstrip() + " " + replacement + out[m.end() :]
    return out, params


def _reorder_offset_limit(statement: str, parameters):
    m = _RE_QMARK_OFFSET_LIMIT.search(statement)
    if m is None:
        return statement, parameters
    # The two placeholders bound to OFFSET/LIMIT sit right before the clause;
    # count the '?' preceding it, ignoring quoted literals.
    head = re.sub(r"'(?:[^']|'')*'", "''", statement[: m.start()])
    off_idx = head.count("?")
    params = list(parameters)
    if off_idx + 1 >= len(params):
        return statement, parameters
    params[off_idx], params[off_idx + 1] = params[off_idx + 1], params[off_idx]
    new_sql = statement[: m.start()] + "LIMIT ? OFFSET ?" + statement[m.end():]
    return new_sql, params


class _UTCAwareDateTime(_SqliteDATETIME):
    """SQLite DATETIME that hands back **timezone-aware** UTC datetimes.

    Parity with the PostgreSQL drivers: asyncpg/psycopg2 return aware
    datetimes for timestamptz, while SQLAlchemy's stock sqlite processor
    returns naive ones (it parses the stored TEXT and drops tzinfo even for
    ``DateTime(timezone=True)`` columns). Every timestamp this server stores
    in SQLite is UTC text (see ``src.db.sqlite_types``), so naive values make
    ``.timestamp()`` apply the *local* UTC offset -- silently shifting real
    dates and raising ``OSError: [Errno 22]`` on Windows for pre-epoch
    defaults like ``1970-01-01``.

    The engines run with ``detect_types=PARSE_DECLTYPES`` so that *raw*
    ``text()`` SELECTs (which carry no SQLAlchemy type information and would
    otherwise hand the caller the stored TEXT) get the same aware datetime.
    That means this processor can receive an already-converted ``datetime``,
    which the stock processor rejects ("fromisoformat: argument must be str"),
    so it is passed through.
    """

    def result_processor(self, dialect, coltype):
        inner = super().result_processor(dialect, coltype)
        _utc = _dt.timezone.utc

        def process(value):
            if value is None:
                return None
            if isinstance(value, _dt.datetime):
                parsed = value  # already converted by the driver
            else:
                parsed = inner(value)
            if parsed is not None and parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=_utc)
            return parsed

        return process


class _TranslatingMixin:
    """do_execute hook: rewrite the statement text just before execution."""

    def create_connect_args(self, url):
        """Default ``detect_types`` to ``PARSE_DECLTYPES``.

        SQLAlchemy only runs its own result processors on *typed* ORM columns,
        so a raw ``session.execute(text("SELECT create_time FROM ..."))`` would
        otherwise hand back the stored TEXT -- while psycopg2/asyncpg return an
        aware datetime. Handlers call ``.timestamp()`` on those values, so a
        string turns a working handler into a ``ValueError``. The converters
        come from ``src.db.sqlite_types`` (declared DATETIME/TIMESTAMP
        columns only; there is deliberately no JSON converter, because SA's
        ``json_deserializer`` has to see the TEXT).

        ``setdefault`` keeps an explicit ``connect_args={"detect_types": ...}``
        on :func:`create_engine` winning -- SA unions ``connect_args`` over
        whatever this method returns.
        """
        args, opts = super().create_connect_args(url)
        opts.setdefault("detect_types", _sqlite3.PARSE_DECLTYPES)
        return args, opts

    def do_execute(self, cursor, statement, parameters, context=None):
        translated = _TRANSLATOR.translate(statement)
        translated, parameters = _expand_any_qmark(translated, parameters)
        translated, parameters = _reorder_offset_limit(translated, parameters)
        return super().do_execute(cursor, translated, parameters, context)

    def do_executemany(self, cursor, statement, parameters, context=None):
        # executemany() gets one parameter group per row, so each group has to
        # be spliced separately -- a per-group list length is legal here, and
        # the driver then reports the mismatch (SQLite still needs one row per
        # placeholder count it was compiled for).
        base = _TRANSLATOR.translate(statement)
        groups = list(parameters or ())
        if not groups or "ANY" not in base.upper():
            return super().do_executemany(cursor, base, groups, context)
        # The un-expanded text is needed once per group, so keep ``base``.
        sql, first = _expand_any_qmark(base, groups[0])
        expanded = [first] + [_expand_any_qmark(base, g)[1] for g in groups[1:]]
        return super().do_executemany(cursor, sql, expanded, context)
    # NOTE: SQLAlchemy checks supports_statement_cache via
    # ``type(dialect).__dict__`` — the CONCRETE class only, not the MRO — so
    # the flag must be set on TranslatingSQLiteDialect_pysqlite/_aiosqlite
    # themselves. The translation happens inside do_execute, i.e. AFTER
    # statement compilation, so SA's compiled-statement cache is safe to
    # enable and the "will not make use of SQL compilation caching" warning
    # is bogus for this dialect.

    # Parity with the PostgreSQL engines, where the global BOOL_AS_INT
    # typecaster (psycopg2) / set_type_codec (asyncpg) decode BOOLEAN as
    # int 0/1: handlers assign DB values straight into protobuf int fields
    # and the upb runtime rejects bool ("Expected an int, got a boolean").
    # With native boolean support SA skips its int->bool result processor and
    # the driver's 0/1 reaches the handler; binds still go through the
    # sqlite3 bool->int adapter from src.db.sqlite_types.
    supports_native_boolean = True
    colspecs = {
        **SQLiteDialect_pysqlite.colspecs,
        _satypes.DateTime: _UTCAwareDateTime,
    }


class TranslatingSQLiteDialect_pysqlite(_TranslatingMixin, SQLiteDialect_pysqlite):
    """`sqlite+tpysqlite://` -- sync engine."""

    # must live on the concrete class: SA inspects type(dialect).__dict__
    supports_statement_cache = True

    @classmethod
    def import_dbapi(cls):
        import sqlite3

        return sqlite3

    # SQLAlchemy 2.x renamed the DBAPI hook to import_dbapi(); the old
    # dbapi() classmethod name triggers a SADeprecationWarning per engine.
    dbapi = import_dbapi


class TranslatingSQLiteDialect_aiosqlite(_TranslatingMixin, SQLiteDialect_aiosqlite):
    """`sqlite+taiosqlite://` -- async engine."""

    # must live on the concrete class: SA inspects type(dialect).__dict__
    supports_statement_cache = True


def register_translating_dialects() -> None:
    """Make the translating dialects loadable from URL schemes.

    Registers `sqlite+tpysqlite` (sync) and `sqlite+taiosqlite` (async) in
    SQLAlchemy's plugin registry; idempotent.
    """
    from sqlalchemy.dialects import registry

    registry.register(
        "sqlite.tpysqlite",
        "src.db.sqlite_sa_dialect",
        "TranslatingSQLiteDialect_pysqlite",
    )
    registry.register(
        "sqlite.taiosqlite",
        "src.db.sqlite_sa_dialect",
        "TranslatingSQLiteDialect_aiosqlite",
    )
