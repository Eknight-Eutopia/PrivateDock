from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import BigInteger, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session


async def get_message_state(commander_id: int, message_id: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, commander_id, message_id, is_read, is_good, good_count, updated_at "
                 "FROM juustagram_message_states WHERE commander_id = :cid AND message_id = :mid"),
            {"cid": commander_id, "mid": message_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def upsert_message_state(commander_id: int, message_id: int, is_read: int, is_good: int, good_count: int, updated_at: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("INSERT INTO juustagram_message_states (commander_id, message_id, is_read, is_good, good_count, updated_at) "
                 "VALUES (:cid, :mid, :ir, :ig, :gc, :ua) "
                 "ON CONFLICT (commander_id, message_id) DO UPDATE SET "
                 "is_read = EXCLUDED.is_read, is_good = EXCLUDED.is_good, good_count = EXCLUDED.good_count, updated_at = EXCLUDED.updated_at"),
            {"cid": commander_id, "mid": message_id, "ir": is_read, "ig": is_good, "gc": good_count, "ua": updated_at},
        )
        await session.commit()


async def list_message_states_by_commander(commander_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, commander_id, message_id, is_read, is_good, good_count, updated_at "
                 "FROM juustagram_message_states WHERE commander_id = :cid ORDER BY message_id"),
            {"cid": commander_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def delete_message_state(commander_id: int, message_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("DELETE FROM juustagram_message_states WHERE commander_id = :cid AND message_id = :mid"),
            {"cid": commander_id, "mid": message_id},
        )
        await session.commit()


class JuustagramMessageState(Base):
    __tablename__ = 'juustagram_message_states'
    __table_args__ = {}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    commander_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int] = mapped_column(BigInteger, default=0)
    is_read: Mapped[int] = mapped_column(BigInteger, default=0)
    is_good: Mapped[int] = mapped_column(BigInteger, default=0)
    good_count: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=0)


# ── sync (store-based) access for game-packet handlers ────────────────────

from src.db.store import get_default_store

_MESSAGE_STATE_COLUMNS = "id, commander_id, message_id, is_read, is_good, good_count, updated_at"


def get_message_states_sync(commander_id: int, message_ids: list) -> dict[int, dict[str, Any]]:
    store = get_default_store()
    rows = store.fetch(
        f"SELECT {_MESSAGE_STATE_COLUMNS} FROM juustagram_message_states "
        "WHERE commander_id = $1 AND message_id = ANY($2)",
        commander_id, [int(m) for m in message_ids],
    )
    return {int(r["message_id"]): dict(r) for r in rows}


def insert_message_states_sync(rows: list) -> None:
    """rows: iterable of (commander_id, message_id, updated_at)."""
    store = get_default_store()
    store.executemany(
        "INSERT INTO juustagram_message_states "
        "(commander_id, message_id, is_read, is_good, good_count, updated_at) "
        "VALUES ($1, $2, 0, 0, 0, $3)",
        rows,
    )


def update_message_state_sync(state: dict) -> None:
    store = get_default_store()
    store.execute(
        "UPDATE juustagram_message_states SET is_read = $1, is_good = $2, good_count = $3, "
        "updated_at = $4 WHERE commander_id = $5 AND message_id = $6",
        state["is_read"], state["is_good"], state["good_count"], state["updated_at"],
        state["commander_id"], state["message_id"],
    )
