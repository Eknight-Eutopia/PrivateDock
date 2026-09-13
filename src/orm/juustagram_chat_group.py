from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import bindparam, BigInteger, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session


async def list_chat_groups_by_commander(commander_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, commander_id, group_record_id, chat_group_id, op_time, read_flag "
                 "FROM juustagram_chat_groups WHERE commander_id = :cid ORDER BY chat_group_id ASC"),
            {"cid": commander_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def list_chat_groups_by_group_record(commander_id: int, group_record_ids: list[int]) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, commander_id, group_record_id, chat_group_id, op_time, read_flag "
                 "FROM juustagram_chat_groups WHERE commander_id = :cid AND group_record_id IN :gids "
                 "ORDER BY chat_group_id ASC").bindparams(bindparam("gids", expanding=True)),
            {"cid": commander_id, "gids": group_record_ids},
        )
        return [dict(r) for r in result.mappings().all()]


async def get_chat_group(commander_id: int, chat_group_id: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, commander_id, group_record_id, chat_group_id, op_time, read_flag "
                 "FROM juustagram_chat_groups WHERE commander_id = :cid AND chat_group_id = :cgid"),
            {"cid": commander_id, "cgid": chat_group_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def create_chat_group(commander_id: int, group_record_id: int, chat_group_id: int, op_time: int) -> int:
    async with get_session() as session:
        result = await session.execute(
            text("INSERT INTO juustagram_chat_groups (commander_id, group_record_id, chat_group_id, op_time, read_flag) "
                 "VALUES (:cid, :gri, :cgi, :ot, 1) RETURNING id"),
            {"cid": commander_id, "gri": group_record_id, "cgi": chat_group_id, "ot": op_time},
        )
        await session.commit()
        return result.scalar_one()


async def mark_chat_groups_read(commander_id: int, chat_group_ids: Optional[list[int]] = None) -> None:
    async with get_session() as session:
        if chat_group_ids:
            await session.execute(
                text("UPDATE juustagram_chat_groups SET read_flag = 1 "
                     "WHERE commander_id = :cid AND chat_group_id IN :cgids"
                     ).bindparams(bindparam("cgids", expanding=True)),
                {"cid": commander_id, "cgids": chat_group_ids},
            )
        else:
            await session.execute(
                text("UPDATE juustagram_chat_groups SET read_flag = 1 WHERE commander_id = :cid"),
                {"cid": commander_id},
            )
        await session.commit()


async def delete_chat_group(commander_id: int, chat_group_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("DELETE FROM juustagram_chat_groups WHERE commander_id = :cid AND chat_group_id = :cgid"),
            {"cid": commander_id, "cgid": chat_group_id},
        )
        await session.commit()


class JuustagramChatGroup(Base):
    __tablename__ = 'juustagram_chat_groups'
    __table_args__ = {}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    commander_id: Mapped[int] = mapped_column(BigInteger)
    group_record_id: Mapped[int] = mapped_column(BigInteger, default=0)
    chat_group_id: Mapped[int] = mapped_column(BigInteger, default=0)
    op_time: Mapped[int] = mapped_column(BigInteger, default=0)
    read_flag: Mapped[int] = mapped_column(BigInteger, default=0)


# ── sync (store-based) access for game-packet handlers ────────────────────

from src.db.store import get_default_store


def mark_chat_groups_read_sync(commander_id: int, chat_group_ids: list) -> None:
    store = get_default_store()
    if not chat_group_ids:
        store.execute(
            "UPDATE juustagram_chat_groups SET read_flag = 1 WHERE commander_id = $1",
            commander_id,
        )
    else:
        store.execute(
            "UPDATE juustagram_chat_groups SET read_flag = 1 "
            "WHERE commander_id = $1 AND chat_group_id = ANY($2)",
            commander_id, chat_group_ids,
        )
