from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import BigInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session
from src.db.store import get_default_store

# Sync (store-based) access used by the game-packet handlers; the async
# session functions above serve the REST API.

_TEMPLATE_COLUMNS = (
    "id, group_id, ship_group, name, sculpture, picture_persist, message_persist, "
    "title, is_active, npc_discuss_persist, time, time_persist, oalist_pic_persist"
)


def get_template_row_sync(template_id: int) -> Optional[dict[str, Any]]:
    store = get_default_store()
    row = store.fetchrow(
        f"SELECT {_TEMPLATE_COLUMNS} FROM juustagram_templates WHERE id = $1",
        template_id,
    )
    return dict(row) if row is not None else None


def get_template_rows_by_ids_sync(template_ids: list) -> dict[int, dict[str, Any]]:
    store = get_default_store()
    rows = store.fetch(
        f"SELECT {_TEMPLATE_COLUMNS} FROM juustagram_templates WHERE id = ANY($1)",
        [int(t) for t in template_ids],
    )
    return {int(r["id"]): dict(r) for r in rows}


async def count_templates() -> int:
    async with get_session() as session:
        result = await session.execute(text("SELECT COUNT(*)::bigint FROM juustagram_templates"))
        return result.scalar() or 0


async def list_templates(offset: int, limit: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, group_id, ship_group, name, sculpture, picture_persist, message_persist, "
                 "is_active, npc_discuss_persist, time, time_persist, oalist_pic_persist "
                 "FROM juustagram_templates ORDER BY id ASC OFFSET :off LIMIT :lim"),
            {"off": offset, "lim": limit},
        )
        return [dict(r) for r in result.mappings().all()]


async def get_template(template_id: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, group_id, ship_group, name, sculpture, picture_persist, message_persist, "
                 "is_active, npc_discuss_persist, time, time_persist, oalist_pic_persist "
                 "FROM juustagram_templates WHERE id = :tid"),
            {"tid": template_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def create_template(
    id: int, group_id: int, ship_group: int, name: str, sculpture: str,
    picture_persist: str, message_persist: str, is_active: bool,
    npc_discuss_persist: str, time: str, time_persist: str, oalist_pic_persist: str = "",
) -> None:
    async with get_session() as session:
        await session.execute(
            text("INSERT INTO juustagram_templates (id, group_id, ship_group, name, sculpture, "
                 "picture_persist, message_persist, is_active, npc_discuss_persist, time, time_persist, "
                 "oalist_pic_persist) "
                 "VALUES (:id, :gid, :sg, :name, :sc, :pp, :mp, :ia, :ndp, :t, :tp, :oap)"),
            {"id": id, "gid": group_id, "sg": ship_group, "name": name, "sc": sculpture,
             "pp": picture_persist, "mp": message_persist, "ia": is_active,
             "ndp": npc_discuss_persist, "t": time, "tp": time_persist,
             "oap": oalist_pic_persist},
        )
        await session.commit()


async def update_template(
    id: int, group_id: int, ship_group: int, name: str, sculpture: str,
    picture_persist: str, message_persist: str, is_active: bool,
    npc_discuss_persist: str, time: str, time_persist: str, oalist_pic_persist: str = "",
) -> None:
    async with get_session() as session:
        await session.execute(
            text("UPDATE juustagram_templates SET group_id=:gid, ship_group=:sg, name=:name, "
                 "sculpture=:sc, picture_persist=:pp, message_persist=:mp, is_active=:ia, "
                 "npc_discuss_persist=:ndp, time=:t, time_persist=:tp, oalist_pic_persist=:oap WHERE id=:id"),
            {"id": id, "gid": group_id, "sg": ship_group, "name": name, "sc": sculpture,
             "pp": picture_persist, "mp": message_persist, "ia": is_active,
             "ndp": npc_discuss_persist, "t": time, "tp": time_persist,
             "oap": oalist_pic_persist},
        )
        await session.commit()


async def delete_template(template_id: int) -> bool:
    async with get_session() as session:
        result = await session.execute(
            text("DELETE FROM juustagram_templates WHERE id = :tid"),
            {"tid": template_id},
        )
        await session.commit()
        return result.rowcount > 0


class JuustagramTemplate(Base):
    __tablename__ = 'juustagram_templates'
    __table_args__ = {}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    group_id: Mapped[int] = mapped_column(BigInteger, default=0)
    ship_group: Mapped[int] = mapped_column(BigInteger, default=0)
    name: Mapped[str] = mapped_column(String, default='')
    sculpture: Mapped[str] = mapped_column(String, default='')
    picture_persist: Mapped[str] = mapped_column(String, default='')
    message_persist: Mapped[str] = mapped_column(String, default='')
    is_active: Mapped[int] = mapped_column(BigInteger, default=0)
    npc_discuss_persist: Mapped[str] = mapped_column(String, default='')
    time: Mapped[str] = mapped_column(String, default='')
    time_persist: Mapped[str] = mapped_column(String, default='')
    oalist_pic_persist: Mapped[str] = mapped_column(String, default='')
