from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import BigInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session


async def count_ship_group_templates() -> int:
    async with get_session() as session:
        result = await session.execute(text("SELECT COUNT(*)::bigint FROM juustagram_ship_group_templates"))
        return result.scalar() or 0


async def list_ship_group_templates(offset: int, limit: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT ship_group, name, background, sculpture, sculpture_ii, nationality, type "
                 "FROM juustagram_ship_group_templates ORDER BY ship_group ASC OFFSET :off LIMIT :lim"),
            {"off": offset, "lim": limit},
        )
        return [dict(r) for r in result.mappings().all()]


async def get_ship_group_template(ship_group: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT ship_group, name, background, sculpture, sculpture_ii, nationality, type "
                 "FROM juustagram_ship_group_templates WHERE ship_group = :sg"),
            {"sg": ship_group},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def create_ship_group_template(
    ship_group: int, name: str, background: str, sculpture: str,
    sculpture_ii: str, nationality: int, type_: int,
) -> None:
    async with get_session() as session:
        await session.execute(
            text("INSERT INTO juustagram_ship_group_templates (ship_group, name, background, sculpture, "
                 "sculpture_ii, nationality, type) VALUES (:sg, :name, :bg, :sc, :sc2, :nat, :typ)"),
            {"sg": ship_group, "name": name, "bg": background, "sc": sculpture,
             "sc2": sculpture_ii, "nat": nationality, "typ": type_},
        )
        await session.commit()


async def update_ship_group_template(
    ship_group: int, name: str, background: str, sculpture: str,
    sculpture_ii: str, nationality: int, type_: int,
) -> None:
    async with get_session() as session:
        await session.execute(
            text("UPDATE juustagram_ship_group_templates SET name=:name, background=:bg, sculpture=:sc, "
                 "sculpture_ii=:sc2, nationality=:nat, type=:typ WHERE ship_group=:sg"),
            {"sg": ship_group, "name": name, "bg": background, "sc": sculpture,
             "sc2": sculpture_ii, "nat": nationality, "typ": type_},
        )
        await session.commit()


async def delete_ship_group_template(ship_group: int) -> bool:
    async with get_session() as session:
        result = await session.execute(
            text("DELETE FROM juustagram_ship_group_templates WHERE ship_group = :sg"),
            {"sg": ship_group},
        )
        await session.commit()
        return result.rowcount > 0


class JuustagramShipGroupTemplate(Base):
    __tablename__ = 'juustagram_ship_group_templates'
    __table_args__ = {}
    ship_group: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String, default='')
    background: Mapped[str] = mapped_column(String, default='')
    sculpture: Mapped[str] = mapped_column(String, default='')
    sculpture_ii: Mapped[str] = mapped_column(String, default='')
    nationality: Mapped[int] = mapped_column(BigInteger, default=0)
    type: Mapped[int] = mapped_column(BigInteger, default=0)
