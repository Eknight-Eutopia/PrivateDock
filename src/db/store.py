from __future__ import annotations

import json
import re
import sqlite3
import threading
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Coroutine, Iterator, Optional, Sequence, TypeVar

from typing import TYPE_CHECKING
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_session, aclose_engines, _SQLITE_PRAGMAS
from src.db.postgres import bool_as_int_init
from src.db.dialect import Dialect, current_dialect

if TYPE_CHECKING:
    # Runtime import is lazy via _ensure_asyncpg() (PostgreSQL branches only),
    # so a SQLite deployment never loads asyncpg.
    import asyncpg

_NUMERIC_PARAM_RE = re.compile(r'\$(\d+)')


def _bool_to_int(value, cur):
    """psycopg2 BOOL adapter: decode boolean columns as int (0/1), not bool.

    The generated protobuf runtime (upb) rejects bool for int proto fields and
    handlers assign DB values straight into proto fields, so every BOOLEAN
    column is decoded as int. Registered globally below; also covers the
    SQLAlchemy sync engine (same psycopg2 driver)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    s = str(value).strip().lower()
    if s in ("t", "true", "yes", "1"):
        return 1
    if s in ("f", "false", "no", "0"):
        return 0
    return None


_psycopg2: Any = None
_psycopg2_extensions: Any = None
_psycopg2_pool: Any = None
_asyncpg: Any = None


def _ensure_asyncpg():
    """Import asyncpg only when PostgreSQL is actually used.

    SQLite deployments (``configurations/server.json [database] dsn = "sqlite:///..."``) never
    reach the async PostgreSQL pool, so the package is not required at import
    time. Note that type annotations above reference ``asyncpg`` freely: they
    are strings (``from __future__ import annotations``) and are never
    evaluated. Returns the lazily-imported module.
    """
    global _asyncpg
    if _asyncpg is None:
        import asyncpg

        _asyncpg = asyncpg
    return _asyncpg


def _ensure_psycopg2():
    """Import psycopg2 only when PostgreSQL is actually used.

    SQLite deployments (``configurations/server.json [database] dsn = "sqlite:///..."``) never
    reach the sync PostgreSQL pool, so the package is not required at import
    time. On first call this also registers the global BOOLEAN->int codec
    (psycopg2 ``register_type`` only applies to connections opened afterwards),
    so callers must invoke it before any psycopg2 connection is created -- the
    store pool does this itself, and ``session._ensure_engines`` does it for the
    SQLAlchemy sync engine. Returns ``(psycopg2, extensions, pool)``.
    """
    global _psycopg2, _psycopg2_extensions, _psycopg2_pool
    if _psycopg2 is None:
        import psycopg2
        import psycopg2.extensions
        import psycopg2.pool

        _BOOL_AS_INT = psycopg2.extensions.new_type((16,), "BOOL_AS_INT", _bool_to_int)
        psycopg2.extensions.register_type(_BOOL_AS_INT)
        _psycopg2 = psycopg2
        _psycopg2_extensions = psycopg2.extensions
        _psycopg2_pool = psycopg2.pool
    return _psycopg2, _psycopg2_extensions, _psycopg2_pool


def _norm_bool_values(values: list) -> list:
    """Scalar bool -> int for rows read through SQLAlchemy async sessions."""
    return [int(v) if isinstance(v, bool) else v for v in values]


# Per-table declared column types from sqlite_master, used to restore the
# asyncpg-equivalent Python types on the raw async read path (the SA sqlite
# engines run WITHOUT detect_types so typed ORM columns are not double-
# processed; raw store.afetch* rows therefore come back as TEXT and are
# converted here, mirroring what asyncpg does for timestamptz on PG).
_SQLITE_TS_COLS: dict[str, frozenset] = {}


def _sqlite_file_path() -> str:
    """Best-effort sqlite file path from the loaded config (empty if unknown)."""
    try:
        from src.config.config import current as _cfg

        cfg = _cfg()
        raw = (cfg.database.dsn or "").strip()
        for prefix in ("sqlite:///", "sqlite://", "sqlite:"):
            if raw.lower().startswith(prefix):
                return raw[len(prefix):]
        return cfg.database.path or ""
    except Exception:
        return ""


def _sqlite_datetime_column_names() -> frozenset:
    """Column names declared DATETIME/TIMESTAMP in the current sqlite file.

    Cached per database path. Reading sqlite_master needs a connection: the
    raw async read path has no thread-local sync connection, so open a
    one-off read-only handle on first use (a stale cache is harmless -- the
    converter only fires when the text actually parses as a timestamp).
    """
    path = _sqlite_file_path()
    cached = _SQLITE_TS_COLS.get(path)
    if cached is not None:
        return cached
    found = set()
    if path:
        try:
            conn = sqlite3.connect(path)
            try:
                for (decl,) in conn.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table'"
                ).fetchall():
                    for m in re.finditer(
                        r'["`]?(\w+)["`]?\s+(?:DATETIME|TIMESTAMP)\b', decl or "", re.I
                    ):
                        found.add(m.group(1))
            finally:
                conn.close()
        except sqlite3.Error:
            pass
    cols = frozenset(found)
    _SQLITE_TS_COLS[path] = cols
    return cols


def _maybe_restore_types(sql: str, cols: list, values: list) -> list:
    """On SQLite, parse DATETIME/TIMESTAMP-declared columns that the driver
    returned as TEXT (asyncpg would return datetime on PostgreSQL)."""
    ts_cols = [c for c, v in zip(cols, values) if isinstance(v, str)]
    if not ts_cols:
        return values
    from src.db import sqlite_types

    out = list(values)
    # column name -> table alias is unknown for generic SQL; simplest reliable
    # source is the declared schema across every table that owns such a column
    # name. The converter only fires when the text actually parses as a
    # timestamp, so false positives on same-named text columns are harmless.
    names = _sqlite_datetime_column_names()
    for i, (c, v) in enumerate(zip(cols, out)):
        if isinstance(v, str) and c in names:
            parsed = sqlite_types._convert_timestamp(v)
            if parsed is not None:
                out[i] = parsed
    return out


def _numeric_to_pyformat(query: str, args: tuple) -> tuple[str, tuple]:
    """Convert $N placeholders to %s and reorder args to match appearance order.

    psycopg2 speaks ``%s``; the canonical SQL in this codebase speaks ``$n``.
    """
    matches = list(_NUMERIC_PARAM_RE.finditer(query))
    result = _NUMERIC_PARAM_RE.sub('%s', query)
    reordered = tuple(args[int(m.group(1)) - 1] for m in matches if int(m.group(1)) <= len(args))
    return result, reordered


T = TypeVar("T")


class SyncRow:
    def __init__(self, cols, values):
        self._cols = cols
        self._values = values
        self._mapping = dict(zip(cols, values))

    def __getitem__(self, key):
        if isinstance(key, (int,)):
            return self._values[key]
        return self._mapping[key]

    def __iter__(self):
        return iter(self._mapping.items())

    def items(self):
        return self._mapping.items()

    def __len__(self):
        return len(self._values)

    def __setitem__(self, key, value):
        if isinstance(key, (int,)):
            self._values[key] = value
        else:
            self._mapping[key] = value

    def get(self, key, default=None):
        if isinstance(key, (int,)):
            if 0 <= key < len(self._values):
                return self._values[key]
            return default
        return self._mapping.get(key, default)


class NotFoundError(Exception):
    pass


def decode_json_value(raw):
    """Decode a value read from a JSON/JSONB column.

    Delivery is driver-dependent: psycopg2 (sync PG) parses jsonb into
    Python objects, while asyncpg and the SQLite paths hand back JSON TEXT.
    Readers of config_entries / jsonb columns must normalize both — a
    bytes-only check lets strings through and crashes callers with
    ``'str' object has no attribute 'get'``. Returns the parsed object, the
    input unchanged when it is already a Python object, or None when
    TEXT/bytes fails to parse.
    """
    if isinstance(raw, memoryview):
        raw = bytes(raw)
    if isinstance(raw, (bytes, bytearray, str)):
        try:
            return json.loads(raw)
        except Exception:
            return None
    return raw


def map_not_found(err: Optional[Exception]) -> Optional[Exception]:
    if err is None:
        return None
    if isinstance(err, NotFoundError):
        return err
    return err


def is_not_found(err: Exception) -> bool:
    return isinstance(err, NotFoundError)


# --------------------------------------------------------------------------- #
# SQLite sync connections
# --------------------------------------------------------------------------- #

# SQLite has a single writer, and this server issues blocking writes from
# ``asyncio.to_thread`` workers while the event-loop thread reads. One
# connection per thread (as with the psycopg2 pool) plus WAL lets readers and
# the writer proceed without "database is locked".
_SQLITE_LOCAL = threading.local()


class _NullCM:
    """Context manager for objects that are not context managers
    (plain ``sqlite3.Cursor``)."""

    def __init__(self, obj):
        self._obj = obj

    def __enter__(self):
        return self._obj

    def __exit__(self, *exc):
        try:
            self._obj.close()
        except Exception:
            pass
        return False


def sqlite_path_from_dsn(dsn: str) -> str:
    """Filesystem path for a SQLite DSN.

    Accepts ``sqlite:///C:/x/app.db``, ``sqlite:////abs/app.db``,
    ``file:app.db`` and a bare path.
    """
    raw = (dsn or "").strip()
    for prefix in ("sqlite:///", "sqlite://", "sqlite:", "file:"):
        if raw.lower().startswith(prefix):
            raw = raw[len(prefix):]
            break
    return raw or "privatedock.sqlite"


class _SyncTx:
    """Statements pinned to one connection, for use inside a transaction."""

    def __init__(self, store: "Store", conn):
        self._store = store
        self._conn = conn

    def execute(self, query: str, *args) -> int:
        sql, prepared = self._store._prepare_sync(query, args)
        with self._store._sync_cursor(self._conn) as cur:
            cur.execute(sql, prepared)
            return cur.rowcount


class _AsyncTx:
    """Statements on one async session, for use inside a transaction."""

    def __init__(self, store: "Store", session):
        self._store = store
        self._session = session

    async def execute(self, query: str, *args) -> str:
        sql, prepared = self._store._dialect.prepare(query, args)
        conn = await self._session.connection()
        result = await conn.exec_driver_sql(sql, tuple(prepared))
        return str(result.rowcount)


class Store:
    def __init__(self, dialect: Optional[Dialect] = None):
        self._pool: Optional[asyncpg.Pool] = None
        self._sync_pool: Any = None
        self._dialect: Dialect = dialect or current_dialect()
        self._sqlite_path: str = ""

    # -- dialect ------------------------------------------------------------ #

    @property
    def dialect(self) -> Dialect:
        return self._dialect

    @property
    def is_sqlite(self) -> bool:
        return self._dialect.name == "sqlite"

    @staticmethod
    def _server_config() -> dict:
        cfg_path = Path(__file__).resolve().parent.parent.parent / "configurations" / "server.json"
        return json.loads(cfg_path.read_text(encoding="utf-8"))

    # -- async pool --------------------------------------------------------- #

    async def init_pool(self, dsn: str, schema_name: str = ""):
        """Bring up the async side. SQLite needs no pool -- the SQLAlchemy
        async engine owns the connection, so this only records the path."""
        if self.is_sqlite:
            self._sqlite_path = sqlite_path_from_dsn(dsn)
            Path(self._sqlite_path).parent.mkdir(parents=True, exist_ok=True)
            return
        server_settings = {}
        if schema_name:
            server_settings["search_path"] = schema_name
        _asyncpg = _ensure_asyncpg()
        self._pool = await _asyncpg.create_pool(
            dsn=dsn,
            server_settings=server_settings,
            min_size=5,
            max_size=20,
            init=bool_as_int_init,
        )

    @property
    def pool(self) -> Optional[asyncpg.Pool]:
        return self._pool

    # -- sync connections --------------------------------------------------- #

    def _get_sync_pool(self):
        """Thread-safe psycopg2 connection pool for the blocking sync helpers.

        A single shared psycopg2 connection is NOT thread-safe: the game server
        issues blocking writes via ``asyncio.to_thread(store.execute, ...)`` (a
        worker thread) and then reads the same rows back on the event-loop
        thread through ``store.fetch``/``store.fetchrow``. Reusing one connection
        object across threads made the read-after-write inconsistent (the read
        returned stale/empty results while a fresh connection saw the committed
        rows). A ``ThreadedConnectionPool`` hands each thread its own connection,
        so writes and subsequent reads are always consistent."""
        if self._sync_pool is None:
            cfg = self._server_config()
            dsn = cfg.get("database", {}).get("dsn", "")
            schema_name = cfg.get("database", {}).get("schema_name", "")
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(dsn)
            conn_kwargs = {
                "host": parsed.hostname,
                "port": parsed.port,
                "user": parsed.username,
                "password": parsed.password,
                "dbname": parsed.path.lstrip("/"),
            }
            qs = parse_qs(parsed.query)
            if "sslmode" in qs:
                sslmode = qs["sslmode"][0]
                if sslmode == "disable":
                    conn_kwargs["sslmode"] = "disable"
            if schema_name:
                conn_kwargs["options"] = f"-c search_path={schema_name}"
            _psycopg2_pool = _ensure_psycopg2()[2]
            self._sync_pool = _psycopg2_pool.ThreadedConnectionPool(
                1, 20, **conn_kwargs
            )
        return self._sync_pool

    def _get_sqlite_conn(self) -> sqlite3.Connection:
        """One SQLite connection per thread, autocommit, WAL."""
        conn = getattr(_SQLITE_LOCAL, "conn", None)
        if conn is not None:
            return conn
        if not self._sqlite_path:
            db = self._server_config().get("database", {})
            # `path` is the file form of the sqlite config (folded into dsn by
            # config.load too); accept either spelling here.
            raw_dsn = db.get("dsn", "") or ("sqlite:///" + db.get("path", "") if db.get("path", "") else "")
            self._sqlite_path = sqlite_path_from_dsn(raw_dsn)
        Path(self._sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        from src.db import sqlite_types  # registers adapters/converters

        sqlite_types.register()
        conn = sqlite3.connect(
            self._sqlite_path,
            timeout=30.0,
            isolation_level=None,  # autocommit, matching the psycopg2 path
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        for pragma in _SQLITE_PRAGMAS:
            conn.execute(pragma)
        _SQLITE_LOCAL.conn = conn
        return conn

    def _sync_conn(self):
        if self.is_sqlite:
            return self._get_sqlite_conn()
        conn = self._get_sync_pool().getconn()
        conn.autocommit = True
        return conn

    def _put_sync_conn(self, conn):
        if self.is_sqlite:
            return  # thread-local, kept open for the life of the thread
        self._get_sync_pool().putconn(conn)

    def _prepare_sync(self, query: str, args: tuple) -> tuple[str, tuple]:
        """Dialect translation + driver paramstyle for the sync path."""
        sql, prepared = self._dialect.prepare(query, args)
        if self.is_sqlite:
            return sql, tuple(prepared)
        return _numeric_to_pyformat(sql, tuple(prepared))

    # -- lifecycle ---------------------------------------------------------- #

    async def close(self):
        if self._pool is not None:
            await self._pool.close()
        if self._sync_pool is not None:
            self._sync_pool.closeall()
        if self.is_sqlite:
            conn = getattr(_SQLITE_LOCAL, "conn", None)
            if conn is not None:
                conn.close()
                _SQLITE_LOCAL.conn = None
        await aclose_engines()

    # -- async API ---------------------------------------------------------- #

    @staticmethod
    def _is_read_only(sql: str) -> bool:
        """True for statements that cannot modify data.

        ``afetch*`` helpers must COMMIT after DML: several call sites use
        ``INSERT/UPDATE ... RETURNING`` through them (guild chat sends, build
        creation, auth challenges/sessions, secondary passwords). Without
        the commit the SQLAlchemy session rolls the write back on close, and
        the returned row is the only trace of a change that never landed.
        """
        head = sql.lstrip().split(None, 1)
        if not head:
            return True
        first = head[0].upper().lstrip("(")
        return first in ("SELECT", "WITH", "SHOW", "EXPLAIN", "VALUES")

    async def afetch(self, query: str, *args) -> list:
        sql, prepared = self._dialect.prepare(query, args)
        async with get_session() as session:
            conn = await session.connection()
            result = await conn.exec_driver_sql(sql, tuple(prepared))
            rows = result.fetchall()
            if not self._is_read_only(sql):
                await session.commit()
            if not rows:
                return []
            cols = list(rows[0]._mapping.keys())
            rows_out = []
            for r in rows:
                vals = _norm_bool_values(list(r._mapping.values()))
                if self.is_sqlite:
                    vals = _maybe_restore_types(sql, cols, vals)
                rows_out.append(SyncRow(cols, vals))
            return rows_out

    async def afetchrow(self, query: str, *args):
        sql, prepared = self._dialect.prepare(query, args)
        async with get_session() as session:
            conn = await session.connection()
            result = await conn.exec_driver_sql(sql, tuple(prepared))
            row = result.fetchone()
            if not self._is_read_only(sql):
                await session.commit()
            if row is None:
                return None
            cols = list(row._mapping.keys())
            vals = _norm_bool_values(list(row._mapping.values()))
            if self.is_sqlite:
                vals = _maybe_restore_types(sql, cols, vals)
            return SyncRow(cols, vals)

    async def afetchval(self, query: str, *args):
        """First column of the first row, or ``None`` (asyncpg ``fetchval``).

        Commits when the statement is DML -- see :meth:`_is_read_only`."""
        sql, prepared = self._dialect.prepare(query, args)
        async with get_session() as session:
            conn = await session.connection()
            result = await conn.exec_driver_sql(sql, tuple(prepared))
            row = result.fetchone()
            if not self._is_read_only(sql):
                await session.commit()
            return None if row is None else row[0]

    async def aexecute(self, query: str, *args: object) -> str:
        sql, prepared = self._dialect.prepare(query, args)
        async with get_session() as session:
            conn = await session.connection()
            result = await conn.exec_driver_sql(sql, tuple(prepared))
            await session.commit()
            return str(result.rowcount)

    async def aexecutemany(self, query: str, seq_of_args: Sequence[Sequence[Any]]) -> None:
        """Run one statement over many parameter rows.

        Each row is translated independently: an ``ANY()`` list argument can
        expand to a different number of placeholders per row.
        """
        async with get_session() as session:
            conn = await session.connection()
            for row in seq_of_args:
                sql, prepared = self._dialect.prepare(query, tuple(row))
                await conn.exec_driver_sql(sql, tuple(prepared))
            await session.commit()

    # -- sync API ----------------------------------------------------------- #

    def _sync_cursor(self, conn):
        """``with``-able cursor: psycopg2 cursors are context managers,
        plain sqlite3 cursors are not."""
        if self.is_sqlite:
            return _NullCM(conn.cursor())
        return conn.cursor()

    def fetch(self, query: str, *args) -> list:
        sql, prepared = self._prepare_sync(query, args)
        conn = self._sync_conn()
        try:
            with self._sync_cursor(conn) as cur:
                cur.execute(sql, prepared)
                if cur.description is None:
                    return []
                cols = [desc[0] for desc in cur.description]
                return [SyncRow(cols, list(row)) for row in cur.fetchall()]
        finally:
            self._put_sync_conn(conn)

    def fetchrow(self, query: str, *args):
        sql, prepared = self._prepare_sync(query, args)
        conn = self._sync_conn()
        try:
            with self._sync_cursor(conn) as cur:
                cur.execute(sql, prepared)
                row = cur.fetchone()
                if row is None:
                    return None
                cols = [desc[0] for desc in cur.description]
                return SyncRow(cols, list(row))
        finally:
            self._put_sync_conn(conn)

    def fetchval(self, query: str, *args):
        row = self.fetchrow(query, *args)
        return None if row is None else row[0]

    def execute(self, query: str, *args) -> int:
        sql, prepared = self._prepare_sync(query, args)
        conn = self._sync_conn()
        try:
            with self._sync_cursor(conn) as cur:
                cur.execute(sql, prepared)
                return cur.rowcount
        finally:
            self._put_sync_conn(conn)

    def executemany(self, query: str, seq_of_args: Sequence[Sequence[Any]]) -> int:
        """Run one statement over many parameter rows on the sync path.

        Replaces the PostgreSQL ``unnest($n::bigint[])`` idiom, which SQLite has
        no equivalent for. Note that rows are translated one by one, because an
        ``ANY()`` argument can expand to a different placeholder count per row.
        """
        conn = self._sync_conn()
        try:
            with self._sync_cursor(conn) as cur:
                total = 0
                for row in seq_of_args:
                    sql, prepared = self._prepare_sync(query, tuple(row))
                    cur.execute(sql, prepared)
                    total += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
                return total
        finally:
            self._put_sync_conn(conn)

    # -- transactions ------------------------------------------------------- #

    @contextmanager
    def sync_transaction(self) -> Iterator[_SyncTx]:
        """Run a block of statements on one connection, atomically.

        ``execute`` returns its connection to the pool after every statement, so
        plain ``BEGIN``/``COMMIT`` statements would not survive across calls on
        PostgreSQL. This pins a single connection for the whole block instead.
        On SQLite the write lock is taken up front (``BEGIN IMMEDIATE``); on
        PostgreSQL the transaction serializes on row locks. Statements go
        through ``tx.execute`` (identical SQL preparation to ``Store.execute``)
        and are committed atomically; any exception rolls the block back.
        """
        conn = self._sync_conn()
        try:
            begin = "BEGIN IMMEDIATE" if self.is_sqlite else "BEGIN"
            with self._sync_cursor(conn) as cur:
                cur.execute(begin)
            tx = _SyncTx(self, conn)
            yield tx
            with self._sync_cursor(conn) as cur:
                cur.execute("COMMIT")
        except BaseException:
            try:
                with self._sync_cursor(conn) as cur:
                    cur.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            self._put_sync_conn(conn)

    @asynccontextmanager
    async def atransaction(self) -> AsyncIterator[_AsyncTx]:
        """Async counterpart of :meth:`sync_transaction`.

        ``aexecute`` commits after every statement, so a delete + inserts
        rebuild would not be atomic across calls. This pins one async session
        in a single transaction for the whole block (``session.begin()``); an
        exception rolls the block back, otherwise it commits on exit.
        """
        async with get_session() as session:
            async with session.begin():
                yield _AsyncTx(self, session)

    async def with_tx(
        self,
        fn: Callable[[AsyncSession], Coroutine[Any, Any, T]],
    ) -> T:
        async with get_session() as session:
            async with session.begin():
                return await fn(session)

    async def with_pgx_tx(
        self,
        fn: Callable[[AsyncSession], Coroutine[Any, Any, T]],
    ) -> T:
        return await self.with_tx(fn)


_default_store: Optional[Store] = None


def get_default_store() -> Optional[Store]:
    return _default_store


def set_default_store(store: Store):
    global _default_store
    _default_store = store
