from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import BigInteger, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session


async def list_player_discusses(commander_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, commander_id, message_id, discuss_id, option_index, npc_reply_id, comment_time "
                 "FROM juustagram_player_discusses WHERE commander_id = :cid ORDER BY message_id"),
            {"cid": commander_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def get_player_discuss(commander_id: int, discuss_id: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, commander_id, message_id, discuss_id, option_index, npc_reply_id, comment_time "
                 "FROM juustagram_player_discusses WHERE commander_id = :cid AND discuss_id = :did"),
            {"cid": commander_id, "did": discuss_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def upsert_player_discuss(commander_id: int, message_id: int, discuss_id: int, option_index: int, npc_reply_id: int, comment_time: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("INSERT INTO juustagram_player_discusses (commander_id, message_id, discuss_id, option_index, npc_reply_id, comment_time) "
                 "VALUES (:cid, :mid, :did, :oi, :nri, :ct) "
                 "ON CONFLICT (commander_id, message_id, discuss_id) DO UPDATE SET "
                 "option_index = EXCLUDED.option_index, npc_reply_id = EXCLUDED.npc_reply_id, "
                 "comment_time = EXCLUDED.comment_time"),
            {"cid": commander_id, "mid": message_id, "did": discuss_id, "oi": option_index, "nri": npc_reply_id, "ct": comment_time},
        )
        await session.commit()


async def update_player_discuss(commander_id: int, discuss_id: int, option_index: int, npc_reply_id: int, comment_time: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("UPDATE juustagram_player_discusses SET option_index = :oi, npc_reply_id = :nri, comment_time = :ct "
                 "WHERE commander_id = :cid AND discuss_id = :did"),
            {"cid": commander_id, "did": discuss_id, "oi": option_index, "nri": npc_reply_id, "ct": comment_time},
        )
        await session.commit()


async def create_player_discuss(commander_id: int, message_id: int, discuss_id: int, option_index: int, npc_reply_id: int, comment_time: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("INSERT INTO juustagram_player_discusses (commander_id, message_id, discuss_id, option_index, npc_reply_id, comment_time) "
                 "VALUES (:cid, :mid, :did, :oi, :nri, :ct)"),
            {"cid": commander_id, "mid": message_id, "did": discuss_id, "oi": option_index, "nri": npc_reply_id, "ct": comment_time},
        )
        await session.commit()


class JuustagramPlayerDiscuss(Base):
    __tablename__ = 'juustagram_player_discusses'
    __table_args__ = {}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    commander_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int] = mapped_column(BigInteger, default=0)
    discuss_id: Mapped[int] = mapped_column(BigInteger, default=0)
    option_index: Mapped[int] = mapped_column(BigInteger, default=0)
    npc_reply_id: Mapped[int] = mapped_column(BigInteger, default=0)
    comment_time: Mapped[int] = mapped_column(BigInteger, default=0)


# ── sync (store-based) access for game-packet handlers ────────────────────

from src.db.store import get_default_store

_PLAYER_DISCUSS_COLUMNS = "id, commander_id, message_id, discuss_id, option_index, npc_reply_id, comment_time"


def get_player_discuss_sync(commander_id: int, message_id: int, discuss_id: int) -> Optional[dict[str, Any]]:
    store = get_default_store()
    row = store.fetchrow(
        f"SELECT {_PLAYER_DISCUSS_COLUMNS} FROM juustagram_player_discusses "
        "WHERE commander_id = $1 AND message_id = $2 AND discuss_id = $3",
        commander_id, message_id, discuss_id,
    )
    return dict(row) if row is not None else None


def list_player_discusses_sync(commander_id: int, message_id: int) -> list[dict[str, Any]]:
    store = get_default_store()
    rows = store.fetch(
        f"SELECT {_PLAYER_DISCUSS_COLUMNS} FROM juustagram_player_discusses "
        "WHERE commander_id = $1 AND message_id = $2 ORDER BY id",
        commander_id, message_id,
    )
    return [dict(r) for r in rows]


def list_player_discusses_for_ids_sync(commander_id: int, message_ids: list) -> dict[int, list[dict[str, Any]]]:
    store = get_default_store()
    rows = store.fetch(
        f"SELECT {_PLAYER_DISCUSS_COLUMNS} FROM juustagram_player_discusses "
        "WHERE commander_id = $1 AND message_id = ANY($2) ORDER BY id",
        commander_id, [int(m) for m in message_ids],
    )
    grouped: dict[int, list[dict[str, Any]]] = {}
    for r in rows:
        grouped.setdefault(int(r["message_id"]), []).append(dict(r))
    return grouped


def upsert_player_discuss_sync(entry: dict) -> None:
    store = get_default_store()
    store.execute(
        "INSERT INTO juustagram_player_discusses "
        "(commander_id, message_id, discuss_id, option_index, npc_reply_id, comment_time) "
        "VALUES ($1, $2, $3, $4, $5, $6) "
        "ON CONFLICT (commander_id, message_id, discuss_id) DO UPDATE SET "
        "option_index = EXCLUDED.option_index, npc_reply_id = EXCLUDED.npc_reply_id, "
        "comment_time = EXCLUDED.comment_time",
        entry["commander_id"], entry["message_id"], entry["discuss_id"],
        entry["option_index"], entry["npc_reply_id"], entry["comment_time"],
    )
