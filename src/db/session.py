from __future__ import annotations

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine, Engine, event
from sqlalchemy.orm import Session as SASession

from src.config.config import current as _get_config


class _Base:
    pass


Base = declarative_base(cls=_Base)


def apply_schema_name(schema_name: str) -> None:
    """Qualify every ORM table with the PostgreSQL schema from configurations/server.json.

    The value is driven by config (``schema_name``), so the schema is no longer
    hardcoded in any model. ``search_path`` already points at this schema on both
    the sync and async engines; this makes the qualification explicit in the SQL.

    A no-op on SQLite: it has no PostgreSQL-style schemas, so qualifying the
    tables would emit ``schema.table`` and fail.
    """
    from src.db.dialect import current_dialect

    if not current_dialect().supports_schemas:
        return
    target = schema_name or None
    for _table in Base.metadata.tables.values():
        _table.schema = target

_sync_engine: Engine | None = None
_SyncSession = None
_async_engine = None
_AsyncSession = None


def _install_bool_as_int_codec(async_engine) -> None:
    """Decode PostgreSQL BOOLEAN as int (0/1) on the asyncpg driver.

    The generated protobuf runtime (upb, google.protobuf >= 5) strictly rejects
    bool for int proto fields ("Expected an int, got a boolean") and handlers
    assign DB values straight into proto fields. Applied at connect time via
    asyncpg's set_type_codec so every ORM-model read through this engine is
    covered. Python truthiness and `1 == True` keep boolean logic working."""

    @event.listens_for(async_engine.sync_engine, "connect")
    def _connect(dbapi_conn, _rec):
        try:
            raw = getattr(dbapi_conn, "driver_connection", None)
            if raw is None:
                raw = getattr(dbapi_conn, "_connection", None)
            if raw is None:
                return
            dbapi_conn.await_(raw.set_type_codec(
                "bool",
                schema="pg_catalog",
                encoder=lambda v: "t" if v else "f",
                decoder=lambda v: 1 if str(v).strip().lower() in ("t", "true", "yes", "1") else 0,
                format="text",
            ))
        except Exception as e:
            from src.logger.logger import log_event, LOG_LEVEL_WARN
            log_event("DB", "bool-codec", f"asyncpg bool->int codec not applied: {e}", LOG_LEVEL_WARN)


from src.db.sqlite_sa_dialect import register_translating_dialects

register_translating_dialects()


def _sqlite_dsn(path: str, async_: bool) -> str:
    """SQLAlchemy URL for a SQLite file.

    The DSN arrives as ``sqlite:///C:/x/app.db`` or a bare path. SQLAlchemy's
    URL parser treats everything after ``sqlite://`` as a *relative* path, so a
    host-style prefix would silently produce ``C:/x/app.db`` relative to cwd.
    Building the URL with :func:`sqlalchemy.engine.URL.create` avoids the
    slash-counting pitfalls entirely and handles Windows drive letters.
    """
    from sqlalchemy.engine import URL

    raw = path.strip()
    for prefix in ("sqlite+aiosqlite:///", "sqlite+aiosqlite://", "sqlite:///", "sqlite://", "sqlite:"):
        if raw.lower().startswith(prefix):
            raw = raw[len(prefix):]
            break
    else:
        if raw.lower().startswith("file:"):
            raw = raw[5:]
    scheme = "sqlite+taiosqlite" if async_ else "sqlite+tpysqlite"
    return URL.create(scheme, database=raw)


def _ensure_engines():
    global _sync_engine, _SyncSession, _async_engine, _AsyncSession
    if _sync_engine is not None:
        return
    _cfg = _get_config()
    _raw_dsn = _cfg.database.dsn

    from src.db.dialect import current_dialect
    from src.db import sqlite_types

    if current_dialect().name == "sqlite":
        sqlite_types.register()
        # SQLite is a local file: WAL lets the event-loop readers proceed while
        # a to_thread writer holds the write lock, and busy_timeout makes the
        # writer wait instead of raising "database is locked".
        # detect_types=PARSE_DECLTYPES is supplied by the translating dialect
        # itself (src.db.sqlite_sa_dialect._TranslatingMixin), not here: SQLA-
        # lchemy only runs its own result processors on *typed* ORM columns, so
        # without it a raw ``session.execute(text("SELECT create_time ..."))``
        # hands back the stored TEXT while PostgreSQL/psycopg2 returns an aware
        # datetime -- and handlers call ``.timestamp()`` on those values. See
        # src.db.sqlite_types for the converters and
        # src.db.sqlite_sa_dialect._UTCAwareDateTime for the typed-column
        # passthrough that stops SA double-processing them.
        connect_args = {"check_same_thread": False, "timeout": 30.0}
        # The imported game data stores jsonb `""` (an empty JSON string) in
        # ~8500 equipment columns; the PG drivers deliver that as a plain ''
        # Python string, so ORM code treats it as falsy. SQLite's JSON result
        # processor would call json.loads('') and crash, so the deserializer
        # maps '' (and other empties) to None for symmetric behaviour.
        def _lenient_json_deserializer(value):
            import json

            if isinstance(value, str) and not value.strip():
                return None
            return json.loads(value)

        _sync_engine = create_engine(
            _sqlite_dsn(_raw_dsn, async_=False),
            pool_pre_ping=True,
            connect_args=connect_args,
            json_deserializer=_lenient_json_deserializer,
        )
        _async_engine = create_async_engine(
            _sqlite_dsn(_raw_dsn, async_=True),
            pool_pre_ping=True,
            connect_args=connect_args,
            json_deserializer=_lenient_json_deserializer,
        )
        _install_sqlite_pragmas(_sync_engine)
        _install_sqlite_pragmas(_async_engine)
        _SyncSession = sessionmaker(bind=_sync_engine, expire_on_commit=False)
        _AsyncSession = async_sessionmaker(bind=_async_engine, class_=AsyncSession, expire_on_commit=False)
        return

    _DB_DSN = _raw_dsn.replace("postgres://", "postgresql://", 1)
    _ASYNC_DSN = _DB_DSN.replace("postgresql://", "postgresql+asyncpg://", 1)
    if "sslmode=" in _ASYNC_DSN:
        from urllib.parse import urlparse, urlencode, parse_qs
        parsed = urlparse(_ASYNC_DSN)
        qs = parse_qs(parsed.query, keep_blank_values=True)
        qs.pop("sslmode", None)
        new_query = urlencode(qs, doseq=True)
        _ASYNC_DSN = parsed._replace(query=new_query).geturl()
    search_path = _cfg.database.schema_name
    # The sync engine below drives psycopg2. Register its global BOOLEAN->int
    # codec before the first connection is opened so raw text() reads hand back
    # int, not bool (protobuf int fields reject bool). psycopg2 is imported
    # lazily by store._ensure_psycopg2, so SQLite never needs the package.
    from src.db.store import _ensure_psycopg2

    _ensure_psycopg2()
    _sync_engine = create_engine(_DB_DSN, pool_pre_ping=True, connect_args={"options": "-c search_path=" + search_path})
    _SyncSession = sessionmaker(bind=_sync_engine, expire_on_commit=False)
    _async_engine = create_async_engine(_ASYNC_DSN, pool_pre_ping=True, connect_args={"server_settings": {"search_path": search_path}})
    _install_bool_as_int_codec(_async_engine)
    _AsyncSession = async_sessionmaker(bind=_async_engine, class_=AsyncSession, expire_on_commit=False)


_SQLITE_PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA busy_timeout=30000",
    "PRAGMA foreign_keys=ON",
    "PRAGMA synchronous=NORMAL",
)


def _install_sqlite_pragmas(engine) -> None:
    """Apply the connection pragmas and UDF shims to every pooled connection."""
    from sqlalchemy import event as _event
    from sqlalchemy.ext.asyncio import AsyncEngine

    target = engine.sync_engine if isinstance(engine, AsyncEngine) else engine

    @_event.listens_for(target, "connect")
    def _pragma_on_connect(dbapi_conn, _rec):  # pragma: no cover - driver hook
        cursor = dbapi_conn.cursor()
        try:
            for pragma in _SQLITE_PRAGMAS:
                cursor.execute(pragma)
        finally:
            cursor.close()
        # PostgreSQL function shims: ORM text() statements bypass the store's
        # dialect translation, so provide now() natively. The value is TEXT in
        # CURRENT_TIMESTAMP's exact format ("YYYY-MM-DD HH:MM:SS", UTC), so
        # comparisons against stored timestamps stay lexicographically valid.
        import datetime as _dt

        def _now():
            return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        dbapi_conn.create_function("now", 0, _now)


def get_engine() -> Engine:
    _ensure_engines()
    return _sync_engine


def get_session() -> AsyncSession:
    _ensure_engines()
    return _AsyncSession()


def get_sync_session() -> SASession:
    _ensure_engines()
    return _SyncSession()


def close_engine():
    _ensure_engines()


async def aclose_engines():
    """Dispose both engines. store.close() awaits this; the sync engine's
    dispose is synchronous, the async engine's must be awaited."""
    _ensure_engines()
    _sync_engine.dispose()
    if _async_engine is not None:
        await _async_engine.dispose()
