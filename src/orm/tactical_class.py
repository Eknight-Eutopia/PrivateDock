from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, select, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


class ErrSkillClassConflict(Exception):
    pass


class ErrNoQuickFinishAllowance(Exception):
    pass


def list_commander_skill_classes(commander_id: int) -> list[CommanderSkillClass]:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderSkillClass)
            .where(CommanderSkillClass.commander_id == commander_id)
            .order_by(CommanderSkillClass.room_id)
        )
        return list(result.scalars().all())


def get_commander_skill_class(commander_id: int, room_id: int) -> Optional[CommanderSkillClass]:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderSkillClass).where(
                CommanderSkillClass.commander_id == commander_id,
                CommanderSkillClass.room_id == room_id,
            )
        )
        return result.scalar_one_or_none()


def upsert_commander_skill_class(entry: CommanderSkillClass) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO commander_skill_classes (commander_id, room_id, ship_id, skill_pos, skill_id, start_time, finish_time, exp)
                VALUES (:commander_id, :room_id, :ship_id, :skill_pos, :skill_id, :start_time, :finish_time, :exp)
                ON CONFLICT (commander_id, room_id)
                DO UPDATE SET
                    ship_id = EXCLUDED.ship_id,
                    skill_pos = EXCLUDED.skill_pos,
                    skill_id = EXCLUDED.skill_id,
                    start_time = EXCLUDED.start_time,
                    finish_time = EXCLUDED.finish_time,
                    exp = EXCLUDED.exp
            """),
            {
                "commander_id": entry.commander_id,
                "room_id": entry.room_id,
                "ship_id": entry.ship_id,
                "skill_pos": entry.skill_pos,
                "skill_id": entry.skill_id,
                "start_time": entry.start_time,
                "finish_time": entry.finish_time,
                "exp": entry.exp,
            },
        )
        session.commit()


def create_commander_skill_class(entry: CommanderSkillClass) -> None:
    with get_sync_session() as session:
        try:
            session.execute(
                text("""
                    INSERT INTO commander_skill_classes (commander_id, room_id, ship_id, skill_pos, skill_id, start_time, finish_time, exp)
                    VALUES (:commander_id, :room_id, :ship_id, :skill_pos, :skill_id, :start_time, :finish_time, :exp)
                """),
                {
                    "commander_id": entry.commander_id,
                    "room_id": entry.room_id,
                    "ship_id": entry.ship_id,
                    "skill_pos": entry.skill_pos,
                    "skill_id": entry.skill_id,
                    "start_time": entry.start_time,
                    "finish_time": entry.finish_time,
                    "exp": entry.exp,
                },
            )
            session.commit()
        except Exception as e:
            session.rollback()
            if "duplicate key" in str(e).lower() or "23505" in str(e):
                raise ErrSkillClassConflict() from e
            raise


def delete_commander_skill_class(commander_id: int, room_id: int) -> bool:
    with get_sync_session() as session:
        result = session.execute(
            text("""
                DELETE FROM commander_skill_classes
                WHERE commander_id = :commander_id AND room_id = :room_id
            """),
            {"commander_id": commander_id, "room_id": room_id},
        )
        session.commit()
        return result.rowcount > 0


def list_commander_ship_skills(commander_id: int) -> list[CommanderShipSkill]:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderShipSkill).where(CommanderShipSkill.commander_id == commander_id)
        )
        return list(result.scalars().all())


def get_commander_ship_skill(commander_id: int, ship_id: int, skill_pos: int) -> Optional[CommanderShipSkill]:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderShipSkill).where(
                CommanderShipSkill.commander_id == commander_id,
                CommanderShipSkill.ship_id == ship_id,
                CommanderShipSkill.skill_pos == skill_pos,
            )
        )
        return result.scalar_one_or_none()


def upsert_commander_ship_skill(entry: CommanderShipSkill) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO commander_ship_skills (commander_id, ship_id, skill_pos, skill_id, level, exp)
                VALUES (:commander_id, :ship_id, :skill_pos, :skill_id, :level, :exp)
                ON CONFLICT (commander_id, ship_id, skill_pos)
                DO UPDATE SET
                    skill_id = EXCLUDED.skill_id,
                    level = EXCLUDED.level,
                    exp = EXCLUDED.exp
            """),
            {
                "commander_id": entry.commander_id,
                "ship_id": entry.ship_id,
                "skill_pos": entry.skill_pos,
                "skill_id": entry.skill_id,
                "level": entry.level,
                "exp": entry.exp,
            },
        )
        session.commit()


def get_commander_tactics_quick_finish(commander_id: int, now: datetime) -> int:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderTacticsQuickFinish).where(
                CommanderTacticsQuickFinish.commander_id == commander_id
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return 0

        today = _utc_day_key(now)
        if row.reset_day != today:
            return 0
        return row.used_count


def upsert_commander_tactics_quick_finish(entry: CommanderTacticsQuickFinish) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO commander_tactics_quick_finishes (commander_id, used_count, reset_day)
                VALUES (:commander_id, :used_count, :reset_day)
                ON CONFLICT (commander_id)
                DO UPDATE SET
                    used_count = EXCLUDED.used_count,
                    reset_day = EXCLUDED.reset_day
            """),
            {
                "commander_id": entry.commander_id,
                "used_count": entry.used_count,
                "reset_day": entry.reset_day,
            },
        )
        session.commit()


def consume_commander_quick_finish(commander_id: int, allowance: int, now: datetime) -> int:
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO commander_tactics_quick_finishes (commander_id, used_count, reset_day)
                VALUES (:commander_id, 0, 0)
                ON CONFLICT (commander_id) DO NOTHING
            """),
            {"commander_id": commander_id},
        )
        session.commit()

        result = session.execute(
            select(CommanderTacticsQuickFinish).where(
                CommanderTacticsQuickFinish.commander_id == commander_id
            )
        )
        row = result.scalar_one()

        today = _utc_day_key(now)
        if row.reset_day != today:
            row.used_count = 0
            row.reset_day = today

        if row.used_count >= allowance:
            raise ErrNoQuickFinishAllowance()

        row.used_count += 1
        session.commit()
        return row.used_count


def get_or_create_commander_ship_skill(commander_id: int, ship_id: int, skill_pos: int, skill_id: int) -> CommanderShipSkill:
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO commander_ship_skills (commander_id, ship_id, skill_pos, skill_id, level, exp)
                VALUES (:commander_id, :ship_id, :skill_pos, :skill_id, 1, 0)
                ON CONFLICT (commander_id, ship_id, skill_pos) DO NOTHING
            """),
            {
                "commander_id": commander_id,
                "ship_id": ship_id,
                "skill_pos": skill_pos,
                "skill_id": skill_id,
            },
        )
        session.commit()

        result = session.execute(
            select(CommanderShipSkill).where(
                CommanderShipSkill.commander_id == commander_id,
                CommanderShipSkill.ship_id == ship_id,
                CommanderShipSkill.skill_pos == skill_pos,
            )
        )
        entry = result.scalar_one()
        if entry.skill_id == 0:
            entry.skill_id = skill_id
            session.commit()
        return entry


def save_commander_ship_skill(entry: CommanderShipSkill) -> None:
    with get_sync_session() as session:
        result = session.execute(
            text("""
                UPDATE commander_ship_skills
                SET skill_id = :skill_id, level = :level, exp = :exp
                WHERE commander_id = :commander_id AND ship_id = :ship_id AND skill_pos = :skill_pos
            """),
            {
                "commander_id": entry.commander_id,
                "ship_id": entry.ship_id,
                "skill_pos": entry.skill_pos,
                "skill_id": entry.skill_id,
                "level": entry.level,
                "exp": entry.exp,
            },
        )
        session.commit()
        if result.rowcount == 0:
            from src.db.store import ErrNotFound
            raise ErrNotFound


def _utc_day_key(now: datetime) -> int:
    return now.year * 10000 + now.month * 100 + now.day


class CommanderSkillClass(Base):
    __tablename__ = "commander_skill_classes"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    room_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ship_id: Mapped[int] = mapped_column(BigInteger, default=0)
    skill_pos: Mapped[int] = mapped_column(BigInteger, default=0)
    skill_id: Mapped[int] = mapped_column(BigInteger, default=0)
    start_time: Mapped[int] = mapped_column(BigInteger, default=0)
    finish_time: Mapped[int] = mapped_column(BigInteger, default=0)
    exp: Mapped[int] = mapped_column(BigInteger, default=0)


class CommanderShipSkill(Base):
    __tablename__ = "commander_ship_skills"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ship_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    skill_pos: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    skill_id: Mapped[int] = mapped_column(BigInteger, default=0)
    level: Mapped[int] = mapped_column(BigInteger, default=0)
    exp: Mapped[int] = mapped_column(BigInteger, default=0)


from src.orm.commander_tactics_quick_finish import CommanderTacticsQuickFinish
