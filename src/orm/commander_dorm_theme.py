from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, JSON, String, select
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


def list_commander_dorm_themes(commander_id: int):
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderDormTheme).where(CommanderDormTheme.commander_id == commander_id)
        )
        return list(result.scalars().all())


def upsert_commander_dorm_theme(commander_id: int, theme_slot_id: int, data: dict):
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderDormTheme).where(
                CommanderDormTheme.commander_id == commander_id,
                CommanderDormTheme.theme_slot_id == theme_slot_id,
            )
        )
        obj = result.scalar_one_or_none()
        name = data.get("name", "") if isinstance(data, dict) else ""
        furniture_put_list = data.get("furniture_put_list", {}) if isinstance(data, dict) else data
        if obj is None:
            obj = CommanderDormTheme(
                commander_id=commander_id,
                theme_slot_id=theme_slot_id,
                name=name,
                furniture_put_list=furniture_put_list,
            )
            session.add(obj)
        else:
            obj.name = name
            obj.furniture_put_list = furniture_put_list
        session.commit()


def delete_commander_dorm_theme(commander_id: int, theme_slot_id: int):
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderDormTheme).where(
                CommanderDormTheme.commander_id == commander_id,
                CommanderDormTheme.theme_slot_id == theme_slot_id,
            )
        )
        obj = result.scalar_one_or_none()
        if obj is not None:
            session.delete(obj)
            session.commit()


class CommanderDormTheme(Base):
    __tablename__ = 'commander_dorm_themes'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    theme_slot_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String, default='')
    furniture_put_list: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
