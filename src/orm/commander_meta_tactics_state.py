from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, select, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


DEFAULT_META_TACTICS_SWITCH_COUNT = 3


def get_or_create_commander_meta_tactics_state(commander_id: int, ship_id: int) -> CommanderMetaTacticsState:
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO commander_meta_tactics_states (commander_id, ship_id, current_skill_id, daily_exp, double_exp, switch_cnt)
                VALUES (:commander_id, :ship_id, 0, 0, 0, :switch_cnt)
                ON CONFLICT (commander_id, ship_id) DO NOTHING
            """),
            {"commander_id": commander_id, "ship_id": ship_id, "switch_cnt": DEFAULT_META_TACTICS_SWITCH_COUNT},
        )
        session.commit()

        result = session.execute(
            select(CommanderMetaTacticsState).where(
                CommanderMetaTacticsState.commander_id == commander_id,
                CommanderMetaTacticsState.ship_id == ship_id,
            )
        )
        return result.scalar_one()


def get_commander_meta_tactics_state(commander_id: int, ship_id: int) -> Optional[CommanderMetaTacticsState]:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderMetaTacticsState).where(
                CommanderMetaTacticsState.commander_id == commander_id,
                CommanderMetaTacticsState.ship_id == ship_id,
            )
        )
        return result.scalar_one_or_none()


def save_commander_meta_tactics_state(state: CommanderMetaTacticsState) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                UPDATE commander_meta_tactics_states
                SET current_skill_id = :current_skill_id,
                    daily_exp = :daily_exp,
                    double_exp = :double_exp,
                    switch_cnt = :switch_cnt,
                    updated_at = CURRENT_TIMESTAMP
                WHERE commander_id = :commander_id AND ship_id = :ship_id
            """),
            {
                "commander_id": state.commander_id,
                "ship_id": state.ship_id,
                "current_skill_id": state.current_skill_id,
                "daily_exp": state.daily_exp,
                "double_exp": state.double_exp,
                "switch_cnt": state.switch_cnt,
            },
        )
        session.commit()


def delete_commander_meta_tactics_state(commander_id: int, ship_id: int) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                DELETE FROM commander_meta_tactics_states
                WHERE commander_id = :commander_id AND ship_id = :ship_id
            """),
            {"commander_id": commander_id, "ship_id": ship_id},
        )
        session.commit()


def get_or_create_commander_meta_tactics_skill_state(commander_id: int, ship_id: int, skill_id: int, skill_pos: int) -> CommanderMetaTacticsSkillState:
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO commander_meta_tactics_skill_states (commander_id, ship_id, skill_id, skill_pos, level, exp)
                VALUES (:commander_id, :ship_id, :skill_id, :skill_pos, 0, 0)
                ON CONFLICT (commander_id, ship_id, skill_id) DO NOTHING
            """),
            {"commander_id": commander_id, "ship_id": ship_id, "skill_id": skill_id, "skill_pos": skill_pos},
        )
        session.commit()

        result = session.execute(
            select(CommanderMetaTacticsSkillState).where(
                CommanderMetaTacticsSkillState.commander_id == commander_id,
                CommanderMetaTacticsSkillState.ship_id == ship_id,
                CommanderMetaTacticsSkillState.skill_id == skill_id,
            )
        )
        return result.scalar_one()


def save_commander_meta_tactics_skill_state(state: CommanderMetaTacticsSkillState) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO commander_meta_tactics_skill_states (commander_id, ship_id, skill_id, skill_pos, level, exp, updated_at)
                VALUES (:commander_id, :ship_id, :skill_id, :skill_pos, :level, :exp, CURRENT_TIMESTAMP)
                ON CONFLICT (commander_id, ship_id, skill_id)
                DO UPDATE SET
                    skill_pos = EXCLUDED.skill_pos,
                    level = EXCLUDED.level,
                    exp = EXCLUDED.exp,
                    updated_at = CURRENT_TIMESTAMP
            """),
            {
                "commander_id": state.commander_id,
                "ship_id": state.ship_id,
                "skill_id": state.skill_id,
                "skill_pos": state.skill_pos,
                "level": state.level,
                "exp": state.exp,
            },
        )
        session.commit()


def list_commander_meta_tactics_skill_states(commander_id: int, ship_id: int) -> list[CommanderMetaTacticsSkillState]:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderMetaTacticsSkillState)
            .where(
                CommanderMetaTacticsSkillState.commander_id == commander_id,
                CommanderMetaTacticsSkillState.ship_id == ship_id,
            )
            .order_by(CommanderMetaTacticsSkillState.skill_pos, CommanderMetaTacticsSkillState.skill_id)
        )
        return list(result.scalars().all())


def upsert_commander_meta_tactics_task_progress(entry: CommanderMetaTacticsTaskProgress) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO commander_meta_tactics_task_progress (commander_id, ship_id, skill_id, task_id, finish_cnt, updated_at)
                VALUES (:commander_id, :ship_id, :skill_id, :task_id, :finish_cnt, CURRENT_TIMESTAMP)
                ON CONFLICT (commander_id, ship_id, skill_id, task_id)
                DO UPDATE SET
                    finish_cnt = EXCLUDED.finish_cnt,
                    updated_at = CURRENT_TIMESTAMP
            """),
            {
                "commander_id": entry.commander_id,
                "ship_id": entry.ship_id,
                "skill_id": entry.skill_id,
                "task_id": entry.task_id,
                "finish_cnt": entry.finish_cnt,
            },
        )
        session.commit()


def list_commander_meta_tactics_task_progress(commander_id: int, ship_id: int) -> list[CommanderMetaTacticsTaskProgress]:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderMetaTacticsTaskProgress)
            .where(
                CommanderMetaTacticsTaskProgress.commander_id == commander_id,
                CommanderMetaTacticsTaskProgress.ship_id == ship_id,
            )
        )
        entries = list(result.scalars().all())
        entries.sort(key=lambda e: (e.skill_id, e.task_id))
        return entries


class CommanderMetaTacticsState(Base):
    __tablename__ = "commander_meta_tactics_states"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ship_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    current_skill_id: Mapped[int] = mapped_column(BigInteger, default=0)
    daily_exp: Mapped[int] = mapped_column(BigInteger, default=0)
    double_exp: Mapped[int] = mapped_column(BigInteger, default=0)
    switch_cnt: Mapped[int] = mapped_column(BigInteger, default=DEFAULT_META_TACTICS_SWITCH_COUNT)


class CommanderMetaTacticsSkillState(Base):
    __tablename__ = "commander_meta_tactics_skill_states"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ship_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    skill_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    skill_pos: Mapped[int] = mapped_column(BigInteger, default=0)
    level: Mapped[int] = mapped_column(BigInteger, default=0)
    exp: Mapped[int] = mapped_column(BigInteger, default=0)


class CommanderMetaTacticsTaskProgress(Base):
    __tablename__ = "commander_meta_tactics_task_progresses"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ship_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    skill_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    task_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    finish_cnt: Mapped[int] = mapped_column(BigInteger, default=0)
