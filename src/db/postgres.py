from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    # Runtime import is lazy (inside open_pool) so a SQLite deployment never
    # loads asyncpg.
    import asyncpg


async def bool_as_int_init(conn) -> None:
    """Decode PostgreSQL BOOLEAN columns as int (0/1) instead of Python bool.

    The generated protobuf runtime (upb, google.protobuf >= 5) strictly rejects
    bool for int32/int64 proto fields ("Expected an int, got a boolean"), and
    handlers assign DB values straight into proto fields. Decoding bools as
    ints at the driver boundary fixes every such site at once; Python truthiness
    and `1 == True` keep existing boolean logic working.
    """
    await conn.set_type_codec(
        "bool",
        schema="pg_catalog",
        encoder=lambda v: "t" if v else "f",
        decoder=lambda v: 1 if str(v).strip().lower() in ("t", "true", "yes", "1") else 0,
        format="text",
    )


@runtime_checkable
class PostgresPool(Protocol):
    async def execute(self, query: str, *args: Any) -> str: ...
    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]: ...
    async def fetchrow(self, query: str, *args: Any) -> asyncpg.Record | None: ...
    async def fetchval(self, query: str, *args: Any) -> Any: ...


async def open_pool(
    dsn: str,
    schema_name: str = "",
    min_size: int = 2,
    max_size: int = 10,
) -> asyncpg.Pool:
    if not dsn.strip():
        raise ValueError("postgres dsn is required")

    import asyncpg

    pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=min_size,
        max_size=max_size,
        server_settings={"search_path": schema_name} if schema_name.strip() else {},
        init=bool_as_int_init,
    )
    return pool
