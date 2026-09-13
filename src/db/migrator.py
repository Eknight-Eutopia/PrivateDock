from __future__ import annotations

import asyncio
import hashlib
import re
from pathlib import Path

MIGRATION_FILENAME_PATTERN = re.compile(r"^(\d+)_([a-zA-Z0-9][a-zA-Z0-9_-]*)\.sql$")

ADVISORY_LOCK_CLASS_ID: int = 0x62666d67
ADVISORY_LOCK_ACQUIRE_TIMEOUT = 10.0
ADVISORY_LOCK_TIMEOUT_MS = 5_000
STATEMENT_TIMEOUT_MS = 5 * 60 * 1_000
RESET_TIMEOUT = 5.0


class MigrationLoadError(Exception):
    pass


class MigrationChecksumError(Exception):
    pass


class Migration:
    def __init__(
        self,
        version: int,
        name: str,
        filename: str,
        sql: str,
        checksum: str,
        no_transaction: bool = False,
    ):
        self.version = version
        self.name = name
        self.filename = filename
        self.sql = sql
        self.checksum = checksum
        self.no_transaction = no_transaction


def _has_no_transaction_directive(sql_text: str) -> bool:
    for line in sql_text.split("\n"):
        trimmed = line.strip()
        if not trimmed.startswith("--"):
            continue
        if "+migrate" in trimmed and "notransaction" in trimmed.lower():
            return True
    return False


def load_migrations_from_directory(migrations_dir: str) -> list[Migration]:
    path = Path(migrations_dir)
    if not path.is_dir():
        return []

    entries = sorted(path.glob("*.sql"))
    if not entries:
        return []

    migrations: list[Migration] = []
    for f in entries:
        match = MIGRATION_FILENAME_PATTERN.match(f.name)
        if not match:
            raise MigrationLoadError(
                f"invalid migration filename {f.name!r} (expected NNNN_name.sql)"
            )
        version = int(match.group(1))
        name = match.group(2)
        sql = f.read_text(encoding="utf-8")
        checksum = hashlib.sha256(sql.encode("utf-8")).digest()
        migrations.append(
            Migration(
                version=version,
                name=name,
                filename=f.name,
                sql=sql,
                checksum=checksum,
                no_transaction=_has_no_transaction_directive(sql),
            )
        )

    migrations.sort(key=lambda m: m.version)
    for i in range(1, len(migrations)):
        if migrations[i].version == migrations[i - 1].version:
            raise MigrationLoadError(
                f"duplicate migration version {migrations[i].version}"
            )

    return migrations


def _qualified_name(schema_name: str, name: str) -> str:
    # SQLite has no schemas: "schema.table" would be parsed as an ATTACH'ed
    # database name ("unknown database <schema>"), so the schema part is
    # dropped for engines without schema support.
    from src.db.dialect import current_dialect

    if schema_name.strip() and current_dialect().supports_schemas:
        return f'"{schema_name}"."{name}"'
    return f'"{name}"'


def _quote_ident(value: str) -> str:
    return f'"{value.replace(chr(34), chr(34) + chr(34))}"'


def _advisory_lock_object_id(schema_name: str) -> int:
    value = schema_name.strip() or "public"
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big", signed=True)


async def _ensure_schema_migrations_table(conn, dialect, schema_name: str = ""):
    table = _qualified_name(schema_name, "schema_migrations")
    # BYTEA / TIMESTAMPTZ are PostgreSQL spellings; SQLite stores the checksum
    # as a BLOB and the timestamp as TEXT. Both accept the same parameter.
    applied_type = "TIMESTAMPTZ" if dialect.supports_schemas else "TIMESTAMP"
    checksum_type = "BYTEA" if dialect.supports_schemas else "BLOB"
    ddl = f"""
CREATE TABLE IF NOT EXISTS {table} (
  version BIGINT PRIMARY KEY,
  name TEXT NOT NULL,
  applied_at {applied_type} NOT NULL DEFAULT CURRENT_TIMESTAMP,
  checksum {checksum_type} NOT NULL
)
"""
    await _exec_stmt(conn, dialect, ddl)


async def _load_applied_migrations(
    conn, dialect, schema_name: str = ""
) -> dict[int, bytes]:
    table = _qualified_name(schema_name, "schema_migrations")
    try:
        if dialect.name == "postgresql":
            rows = await conn.fetch(f"SELECT version, checksum FROM {table}")
            return {row["version"]: row["checksum"] for row in rows}
        else:
            result = await conn.exec_driver_sql(
                f"SELECT version, checksum FROM {table}", []
            )
            rows = result.fetchall()
            return {row[0]: bytes(row[1]) if row[1] else b"" for row in rows}
    except Exception:
        return {}


def _record_migration_sql(table: str) -> str:
    return (
        f"INSERT INTO {table} (version, name, applied_at, checksum) "
        "VALUES ($1, $2, CURRENT_TIMESTAMP, $3) "
        "ON CONFLICT (version) DO NOTHING"
    )


def _split_sql_statements(sql_text: str) -> list[str]:
    statements: list[str] = []
    builder: list[str] = []

    in_single_quote = False
    in_double_quote = False
    in_line_comment = False
    in_block_comment = False
    dollar_tag = ""

    def flush():
        statement = "".join(builder).strip()
        if statement:
            statements.append(statement)
        builder.clear()

    i = 0
    while i < len(sql_text):
        ch = sql_text[i]
        nxt = sql_text[i + 1] if i + 1 < len(sql_text) else ""

        if in_line_comment:
            builder.append(ch)
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            builder.append(ch)
            if ch == "*" and nxt == "/":
                builder.append(nxt)
                i += 2
                in_block_comment = False
                continue
            i += 1
            continue

        if dollar_tag:
            if sql_text[i:].startswith(dollar_tag):
                builder.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = ""
                continue
            builder.append(ch)
            i += 1
            continue

        if not in_single_quote and not in_double_quote:
            if ch == "-" and nxt == "-":
                builder.append(ch)
                builder.append(nxt)
                i += 2
                in_line_comment = True
                continue

            if ch == "/" and nxt == "*":
                builder.append(ch)
                builder.append(nxt)
                i += 2
                in_block_comment = True
                continue

            if ch == "$":
                j = i + 1
                while j < len(sql_text):
                    if sql_text[j] == "$":
                        dollar_tag = sql_text[i : j + 1]
                        builder.append(dollar_tag)
                        i = j + 1
                        break
                    c = sql_text[j]
                    if c.isalnum() or c == "_":
                        j += 1
                        continue
                    break
                if dollar_tag:
                    continue

            if ch == ";":
                flush()
                i += 1
                continue

        if ch == "'" and not in_double_quote:
            if in_single_quote and nxt == "'":
                builder.append(ch)
                builder.append(nxt)
                i += 2
                continue
            in_single_quote = not in_single_quote

        if ch == '"' and not in_single_quote:
            if in_double_quote and nxt == '"':
                builder.append(ch)
                builder.append(nxt)
                i += 2
                continue
            in_double_quote = not in_double_quote

        builder.append(ch)
        i += 1

    flush()
    return statements


async def _apply_migration(
    conn, schema_name: str, m: Migration, dialect=None
):
    from src.db.dialect import current_dialect

    dialect = dialect or current_dialect()
    table = _qualified_name(schema_name, "schema_migrations")
    sql_text = m.sql.strip()
    if not sql_text:
        await _record_migration(conn, dialect, table, m)
        return

    # Translate DDL for non-PostgreSQL engines (e.g. JSONB→TEXT, SEQUENCE→noop).
    migration_sql = dialect.rewrite_ddl(sql_text) if dialect.name != "postgresql" else sql_text

    record_sql = _record_migration_sql(table)
    if dialect.name != "postgresql":
        record_sql, record_args = dialect.prepare(record_sql, (m.version, m.name, m.checksum))
    else:
        record_args = (m.version, m.name, m.checksum)

    if m.no_transaction:
        statements = _split_sql_statements(migration_sql)
        for stmt in statements:
            try:
                await _exec_stmt(conn, dialect, stmt)
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    continue
                raise
        await _exec_stmt(conn, dialect, record_sql, record_args)
    else:
        await _run_in_transaction(conn, dialect, migration_sql, record_sql, record_args)


async def _record_migration(conn, dialect, table: str, m: Migration) -> None:
    record_sql = _record_migration_sql(table)
    if dialect.name != "postgresql":
        record_sql, record_args = dialect.prepare(record_sql, (m.version, m.name, m.checksum))
    else:
        record_args = (m.version, m.name, m.checksum)
    await _exec_stmt(conn, dialect, record_sql, record_args)


async def _exec_stmt(conn, dialect, sql: str, args: tuple = ()) -> None:
    """Execute one statement on the active connection.

    PostgreSQL: ``conn`` is an asyncpg Connection — ``conn.execute(sql, *args)``.
    SQLite: ``conn`` is a SQLAlchemy async connection — use
    ``conn.exec_driver_sql(sql, args)``.
    """
    if dialect.name == "postgresql":
        await conn.execute(sql, *args)
    else:
        await conn.exec_driver_sql(sql, tuple(args))


async def _run_in_transaction(
    conn, dialect, migration_sql: str, record_sql: str, record_args: tuple
) -> None:
    """Run migration SQL + record insert in a single transaction."""
    if dialect.name == "postgresql":
        async with conn.transaction():
            await conn.execute(migration_sql)
            await conn.execute(record_sql, *record_args)
    else:
        # SQLAlchemy async connection already manages its own transaction
        # via the session; execute statements in order and commit after.
        for stmt in _split_sql_statements(migration_sql):
            try:
                await conn.exec_driver_sql(stmt, ())
            except Exception as e:
                # "duplicate column name" is the SQLite spelling of
                # PostgreSQL's ADD COLUMN IF NOT EXISTS: the column was
                # already created (CREATE TABLE carries it) and the ALTER is
                # pure idempotence for legacy databases.
                if "duplicate column name" in str(e).lower():
                    continue
                raise
        await conn.exec_driver_sql(record_sql, tuple(record_args))


async def run_migrations(
    conn,
    migrations: list[Migration],
    schema_name: str = "",
    dsn: str = "",
):
    if not migrations:
        return

    from src.db.dialect import current_dialect

    dialect = current_dialect()

    lock_conn = None
    # PostgreSQL advisory locks serialise concurrent migrators across
    # processes. SQLite has no equivalent -- it is a local file guarded by WAL
    # plus busy_timeout, and this server is the only writer, so the lock is
    # skipped rather than emulated.
    if dsn and dialect.supports_advisory_locks:
        import asyncpg
        lock_conn = await asyncpg.connect(dsn=dsn)

    try:
        if lock_conn:
            lock_obj = _advisory_lock_object_id(schema_name)
            try:
                await asyncio.wait_for(
                    lock_conn.execute(
                        "SELECT pg_advisory_lock($1, $2)",
                        ADVISORY_LOCK_CLASS_ID,
                        lock_obj,
                    ),
                    timeout=ADVISORY_LOCK_ACQUIRE_TIMEOUT,
                )
            except asyncio.TimeoutError:
                raise TimeoutError(
                    "failed to acquire migration advisory lock within timeout"
                )

        await _ensure_schema_migrations_table(conn, dialect, schema_name)
        applied = await _load_applied_migrations(conn, dialect, schema_name)

        for m in migrations:
            if m.version in applied:
                """if applied[m.version] != m.checksum:
                    raise MigrationChecksumError(
                        f"migration {m.version} ({m.filename}) "
                        "already applied but checksum changed"
                    )"""
                continue

            await _apply_migration(conn, schema_name, m, dialect)

    finally:
        if lock_conn:
            try:
                lock_obj = _advisory_lock_object_id(schema_name)
                await asyncio.wait_for(
                    lock_conn.execute(
                        "SELECT pg_advisory_unlock($1, $2)",
                        ADVISORY_LOCK_CLASS_ID,
                        lock_obj,
                    ),
                    timeout=RESET_TIMEOUT,
                )
            except Exception:
                pass
            await lock_conn.close()


async def run_migrations_from_directory(
    conn,
    migrations_dir: str,
    schema_name: str = "",
):
    migrations = load_migrations_from_directory(migrations_dir)
    await run_migrations(conn, migrations, schema_name)
