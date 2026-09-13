from __future__ import annotations
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, JSON, String, DateTime, select
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session
from src.orm.guild_membership import GuildMembership


def create_guild(name: str, leader_id: int) -> "Guild":
    with get_sync_session() as session:
        existing = session.execute(
            select(Guild).where(Guild.name == name)
        ).scalar_one_or_none()
        if existing is not None:
            raise ValueError("guild name already exists")
        guild = Guild(name=name, leader_id=leader_id)
        session.add(guild)
        session.commit()
        session.refresh(guild)
        return guild


def get_guild_for_commander(commander_id: int) -> Optional["Guild"]:
    with get_sync_session() as session:
        membership = session.execute(
            select(GuildMembership).where(
                GuildMembership.commander_id == commander_id,
            )
        ).scalar_one_or_none()
        if membership is None:
            return None
        return session.get(Guild, membership.guild_id)


def get_guild_by_id(guild_id: int) -> Optional["Guild"]:
    with get_sync_session() as session:
        return session.get(Guild, guild_id)


def get_commander_guild_membership(commander_id: int, guild_id: int) -> Optional[GuildMembership]:
    with get_sync_session() as session:
        return session.execute(
            select(GuildMembership).where(
                GuildMembership.commander_id == commander_id,
                GuildMembership.guild_id == guild_id,
            )
        ).scalar_one_or_none()


def list_guild_members(guild_id: int) -> list:
    with get_sync_session() as session:
        result = session.execute(
            select(GuildMembership).where(
                GuildMembership.guild_id == guild_id,
            )
        )
        return list(result.scalars().all())


def get_guild_set_uint(guild_id: int, key: str) -> int:
    with get_sync_session() as session:
        result = session.execute(
            select(Guild.config).where(Guild.id == guild_id)
        )
        config = result.scalar_one_or_none() or {}
        return config.get(key, 0) if isinstance(config, dict) else 0


def get_guild_leave_wait(commander_id: int) -> int:
    return get_commander_guild_wait_time(commander_id)


def get_commander_guild_wait_time(commander_id: int) -> int:
    with get_sync_session() as session:
        result = session.execute(
            select(GuildMembership.wait_time).where(
                GuildMembership.commander_id == commander_id,
            ).order_by(GuildMembership.wait_time.desc()).limit(1)
        )
        return result.scalar() or 0


class Guild(Base):
    __tablename__ = 'guilds'
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String, default='')
    leader_id: Mapped[int] = mapped_column(BigInteger)
    policy: Mapped[int] = mapped_column(BigInteger, default=0)
    faction: Mapped[int] = mapped_column(BigInteger, default=0)
    level: Mapped[int] = mapped_column(BigInteger, default=0)
    announce: Mapped[str] = mapped_column(String, default='')
    manifesto: Mapped[str] = mapped_column(String, default='')
    exp: Mapped[int] = mapped_column(BigInteger, default=0)
    member_count: Mapped[int] = mapped_column(BigInteger, default=0)
    change_faction_cd: Mapped[int] = mapped_column(BigInteger, default=0)
    kick_leader_cd: Mapped[int] = mapped_column(BigInteger, default=0)
    capital: Mapped[int] = mapped_column(BigInteger, default=0)
    tech_id: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    office_state: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    weekly_task_state: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
