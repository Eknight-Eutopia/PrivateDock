from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, bindparam, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session


async def list_replies_by_chat_group(chat_group_record_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, chat_group_record_id, sequence, key, value "
                 "FROM juustagram_replies WHERE chat_group_record_id = :cgri ORDER BY sequence ASC"),
            {"cgri": chat_group_record_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def list_replies_by_chat_group_ids(chat_group_record_ids: list[int]) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, chat_group_record_id, sequence, key, value "
                 "FROM juustagram_replies WHERE chat_group_record_id IN :cgris "
                 "ORDER BY chat_group_record_id ASC, sequence ASC"
                 ).bindparams(bindparam("cgris", expanding=True)),
            {"cgris": chat_group_record_ids},
        )
        return [dict(r) for r in result.mappings().all()]


async def get_max_reply_sequence(chat_group_record_id: int) -> int:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT COALESCE(MAX(sequence), 0)::bigint FROM juustagram_replies WHERE chat_group_record_id = :cgri"),
            {"cgri": chat_group_record_id},
        )
        return result.scalar() or 0


async def create_reply(chat_group_record_id: int, sequence: int, key: int, value: int) -> int:
    async with get_session() as session:
        result = await session.execute(
            text("INSERT INTO juustagram_replies (chat_group_record_id, sequence, key, value) "
                 "VALUES (:cgri, :seq, :k, :v) RETURNING id"),
            {"cgri": chat_group_record_id, "seq": sequence, "k": key, "v": value},
        )
        await session.commit()
        return result.scalar_one()


async def delete_reply(commander_id: int, chat_group_id: int, sequence: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("DELETE FROM juustagram_replies r "
                 "USING juustagram_chat_groups cg "
                 "WHERE r.chat_group_record_id = cg.id AND cg.commander_id = :cid AND cg.chat_group_id = :cgi AND r.sequence = :seq"),
            {"cid": commander_id, "cgi": chat_group_id, "seq": sequence},
        )
        await session.commit()


class JuustagramReply(Base):
    __tablename__ = 'juustagram_replies'
    __table_args__ = {}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_group_record_id: Mapped[int] = mapped_column(BigInteger)
    sequence: Mapped[int] = mapped_column(BigInteger, default=0)
    key: Mapped[int] = mapped_column(BigInteger, default=0)
    value: Mapped[int] = mapped_column(BigInteger, default=0)
