from __future__ import annotations
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, DateTime, select, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session, get_sync_session


# ── Async ORM query functions (for api/handlers) ──


async def list_commander_stories_rows(commander_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT story_id, created_at FROM commander_stories WHERE commander_id = :cid ORDER BY story_id"),
            {"cid": commander_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def upsert_commander_story(commander_id: int, story_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("INSERT INTO commander_stories (commander_id, story_id) VALUES (:cid, :sid) "
                 "ON CONFLICT DO NOTHING"),
            {"cid": commander_id, "sid": story_id},
        )
        await session.commit()


class CommanderSoundStory(Base):
    # Real table name (migration 0005 renamed the 0004 misnomer
    # "commander_soundstories" -> "commander_sound_stories"; the DO-block
    # rename is PG-specific and skipped on SQLite, where 0093 drops the
    # leftover). Pointing the model at the old name crashes reads on PG.
    __tablename__ = 'commander_sound_stories'
    __table_args__ = {}
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    story_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


def list_commander_stories(commander_id: int) -> list:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderStory).where(
                CommanderStory.commander_id == commander_id,
            )
        )
        return list(result.scalars().all())


def list_commander_sound_stories(commander_id: int) -> list:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderSoundStory).where(
                CommanderSoundStory.commander_id == commander_id,
            )
        )
        return list(result.scalars().all())


def is_sound_story_unlocked(commander_id: int, story_id: int) -> bool:
    with get_sync_session() as session:
        obj = session.execute(
            select(CommanderSoundStory).where(
                CommanderSoundStory.commander_id == commander_id,
                CommanderSoundStory.story_id == story_id,
            )
        ).scalar_one_or_none()
        return obj is not None


def list_commander_story_ids(commander_id: int) -> list[int]:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderStory.story_id).where(
                CommanderStory.commander_id == commander_id
            )
        )
        return [row[0] for row in result.fetchall()]


def list_commander_sound_story_ids(commander_id: int) -> list[int]:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderSoundStory.story_id).where(
                CommanderSoundStory.commander_id == commander_id
            )
        )
        return [row[0] for row in result.fetchall()]


def unlock_sound_story(commander_id: int, story_id: int):
    with get_sync_session() as session:
        existing = session.execute(
            select(CommanderSoundStory).where(
                CommanderSoundStory.commander_id == commander_id,
                CommanderSoundStory.story_id == story_id,
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(CommanderSoundStory(commander_id=commander_id, story_id=story_id))
            session.commit()


class CommanderStory(Base):
    __tablename__ = 'commander_stories'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    story_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
