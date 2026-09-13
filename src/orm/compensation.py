from __future__ import annotations
from typing import Any

from sqlalchemy import text

from src.db.session import get_session


async def list_compensations(commander_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, commander_id, title, text, send_time, expires_at, attach_flag, created_at "
                 "FROM compensations WHERE commander_id = :cid ORDER BY created_at DESC"),
            {"cid": commander_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def list_compensation_attachments(compensation_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT type, item_id, quantity FROM compensation_attachments WHERE compensation_id = :cid"),
            {"cid": compensation_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def create_compensation(commander_id: int, title: str, text_body: str, send_time: str, expires_at: str) -> int:
    async with get_session() as session:
        result = await session.execute(
            text("INSERT INTO compensations (commander_id, title, text, send_time, expires_at, created_at) "
                 "VALUES (:cid, :t, :b, :st, :ea, NOW()) RETURNING id"),
            {"cid": commander_id, "t": title, "b": text_body, "st": send_time, "ea": expires_at},
        )
        await session.commit()
        return result.scalar_one()


async def create_compensation_attachment(compensation_id: int, att_type: int, item_id: int, quantity: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("INSERT INTO compensation_attachments (compensation_id, type, item_id, quantity) "
                 "VALUES (:cid, :t, :iid, :q)"),
            {"cid": compensation_id, "t": att_type, "iid": item_id, "q": quantity},
        )
        await session.commit()
