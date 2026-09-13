from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session


async def get_language(key: str) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT key, value FROM juustagram_languages WHERE key = :k"),
            {"k": key},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def list_languages(prefix: Optional[str] = None) -> list[dict[str, Any]]:
    async with get_session() as session:
        if prefix:
            result = await session.execute(
                text("SELECT key, value FROM juustagram_languages WHERE key LIKE :pref ORDER BY key ASC"),
                {"pref": f"{prefix}%"},
            )
        else:
            result = await session.execute(
                text("SELECT key, value FROM juustagram_languages ORDER BY key ASC"),
            )
        return [dict(r) for r in result.mappings().all()]


async def create_language(key: str, value: str) -> None:
    async with get_session() as session:
        await session.execute(
            text("INSERT INTO juustagram_languages (key, value) VALUES (:k, :v)"),
            {"k": key, "v": value},
        )
        await session.commit()


async def update_language(key: str, value: str) -> None:
    async with get_session() as session:
        await session.execute(
            text("UPDATE juustagram_languages SET value = :v WHERE key = :k"),
            {"v": value, "k": key},
        )
        await session.commit()


async def delete_language(key: str) -> bool:
    async with get_session() as session:
        result = await session.execute(
            text("DELETE FROM juustagram_languages WHERE key = :k"),
            {"k": key},
        )
        await session.commit()
        return result.rowcount > 0


class JuustagramLanguage(Base):
    __tablename__ = 'juustagram_languages'
    __table_args__ = {}
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, default='')


# ── sync (store-based) access for game-packet handlers ────────────────────

from src.db.store import get_default_store


def get_language_value_sync(key: str) -> Optional[str]:
    """None when the key does not exist (callers decide caching/raise)."""
    store = get_default_store()
    row = store.fetchrow("SELECT value FROM juustagram_languages WHERE key = $1", key)
    return row["value"] if row is not None else None


def get_language_values_by_keys_sync(keys: list) -> dict[str, str]:
    store = get_default_store()
    rows = store.fetch(
        "SELECT key, value FROM juustagram_languages WHERE key = ANY($1)",
        list(keys),
    )
    return {r["key"]: r["value"] for r in rows}


def list_language_rows_by_prefix_sync(prefix: str) -> list[dict[str, Any]]:
    store = get_default_store()
    rows = store.fetch(
        "SELECT key, value FROM juustagram_languages WHERE key LIKE $1",
        prefix + "%",
    )
    return [dict(r) for r in rows]
