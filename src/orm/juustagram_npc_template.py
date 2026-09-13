from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import BigInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session


async def count_npc_templates() -> int:
    async with get_session() as session:
        result = await session.execute(text("SELECT COUNT(*)::bigint FROM juustagram_npc_templates"))
        return result.scalar() or 0


async def list_npc_templates(offset: int, limit: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, ship_group, message_persist, npc_reply_persist, time_persist "
                 "FROM juustagram_npc_templates ORDER BY id ASC OFFSET :off LIMIT :lim"),
            {"off": offset, "lim": limit},
        )
        return [dict(r) for r in result.mappings().all()]


async def get_npc_template(template_id: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, ship_group, message_persist, npc_reply_persist, time_persist "
                 "FROM juustagram_npc_templates WHERE id = :tid"),
            {"tid": template_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def create_npc_template(
    id: int, ship_group: int, message_persist: str,
    npc_reply_persist: str, time_persist: str,
) -> None:
    async with get_session() as session:
        await session.execute(
            text("INSERT INTO juustagram_npc_templates (id, ship_group, message_persist, npc_reply_persist, time_persist) "
                 "VALUES (:id, :sg, :mp, :nrp, :tp)"),
            {"id": id, "sg": ship_group, "mp": message_persist, "nrp": npc_reply_persist, "tp": time_persist},
        )
        await session.commit()


async def update_npc_template(
    id: int, ship_group: int, message_persist: str,
    npc_reply_persist: str, time_persist: str,
) -> None:
    async with get_session() as session:
        await session.execute(
            text("UPDATE juustagram_npc_templates SET ship_group=:sg, message_persist=:mp, "
                 "npc_reply_persist=:nrp, time_persist=:tp WHERE id=:id"),
            {"id": id, "sg": ship_group, "mp": message_persist, "nrp": npc_reply_persist, "tp": time_persist},
        )
        await session.commit()


async def delete_npc_template(template_id: int) -> bool:
    async with get_session() as session:
        result = await session.execute(
            text("DELETE FROM juustagram_npc_templates WHERE id = :tid"),
            {"tid": template_id},
        )
        await session.commit()
        return result.rowcount > 0


class JuustagramNpcTemplate(Base):
    __tablename__ = 'juustagram_npc_templates'
    __table_args__ = {}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ship_group: Mapped[int] = mapped_column(BigInteger, default=0)
    message_persist: Mapped[str] = mapped_column(String, default='')
    npc_reply_persist: Mapped[str] = mapped_column(String, default='')
    time_persist: Mapped[str] = mapped_column(String, default='')


# ── sync (store-based) access for game-packet handlers ────────────────────

from src.db.store import get_default_store

_NPC_TEMPLATE_COLUMNS = "id, ship_group, message_persist, npc_reply_persist, time_persist"


def get_npc_template_row_sync(npc_id: int) -> Optional[dict[str, Any]]:
    store = get_default_store()
    row = store.fetchrow(
        f"SELECT {_NPC_TEMPLATE_COLUMNS} FROM juustagram_npc_templates WHERE id = $1",
        npc_id,
    )
    return dict(row) if row is not None else None


def get_npc_template_rows_by_ids_sync(npc_ids: list) -> dict[int, dict[str, Any]]:
    store = get_default_store()
    rows = store.fetch(
        f"SELECT {_NPC_TEMPLATE_COLUMNS} FROM juustagram_npc_templates WHERE id = ANY($1)",
        [int(n) for n in npc_ids],
    )
    return {int(r["id"]): dict(r) for r in rows}


def list_npc_templates_by_message_persist_prefix_sync(prefix: str) -> list[dict[str, Any]]:
    store = get_default_store()
    rows = store.fetch(
        f"SELECT {_NPC_TEMPLATE_COLUMNS} FROM juustagram_npc_templates "
        "WHERE message_persist LIKE $1",
        prefix + "%",
    )
    return [dict(r) for r in rows]
