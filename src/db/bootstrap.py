from __future__ import annotations

from sqlalchemy import text

from typing import TYPE_CHECKING

from src.db.dialect import current_dialect
from src.db.session import get_session
from src.db.store import Store, set_default_store
from src.db.migrator import run_migrations_from_directory

if TYPE_CHECKING:
    # Runtime import is lazy (inside the PostgreSQL branches below) so a
    # SQLite deployment never loads asyncpg.
    import asyncpg


async def open_postgres_sqldb(dsn: str) -> "asyncpg.Connection":
    if not dsn.strip():
        raise ValueError("postgres dsn is required")
    import asyncpg

    return await asyncpg.connect(dsn=dsn)


async def init_default_store(
    dsn: str,
    schema_name: str = "",
    migrations_dir: str = "",
) -> Store:
    dialect = current_dialect()

    if dialect.name == "postgresql":
        import asyncpg

        conn = await asyncpg.connect(dsn=dsn)
        try:
            if schema_name.strip():
                await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"')
            if migrations_dir:
                await run_migrations_from_directory(conn, migrations_dir, schema_name)
        finally:
            await conn.close()
    else:
        # SQLite: no schema creation needed; migrations run through the async engine.
        if migrations_dir:
            async with get_session() as session:
                conn = await session.connection()
                await run_migrations_from_directory(conn, migrations_dir, schema_name)
                await session.commit()

    store = Store()
    await store.init_pool(dsn, schema_name)
    set_default_store(store)
    return store


async def has_game_data(store: Store) -> bool:
    from src.db.session import get_session

    async with get_session() as session:
        row = await session.execute(text("SELECT EXISTS(SELECT 1 FROM items LIMIT 1)"))
        return bool(row.scalar())
