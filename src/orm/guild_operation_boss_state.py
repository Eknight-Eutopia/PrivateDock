from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, select, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


class GuildOperationBossState(Base):
    __tablename__ = "guild_operation_boss_states"
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    operation_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    boss_id: Mapped[int] = mapped_column(BigInteger, default=0)
    damage: Mapped[int] = mapped_column(BigInteger, default=0)
    hp: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class GuildOperationBossRank(Base):
    __tablename__ = "guild_operation_boss_ranks"
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    operation_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    boss_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    damage: Mapped[int] = mapped_column(BigInteger, default=0)


def get_guild_operation_boss_state(guild_id: int, operation_id: int) -> Optional[dict]:
    with get_sync_session() as session:
        row = session.execute(
            select(GuildOperationBossState).where(
                GuildOperationBossState.guild_id == guild_id,
                GuildOperationBossState.operation_id == operation_id,
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return {
            "guild_id": row.guild_id,
            "operation_id": row.operation_id,
            "boss_id": row.boss_id,
            "damage": row.damage,
            "hp": row.hp,
        }


def upsert_guild_operation_boss_state(guild_id: int, operation_id: int, boss_id: int, damage: int, hp: int) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO guild_operation_boss_states (guild_id, operation_id, boss_id, damage, hp, updated_at)
                VALUES (:gid, :oid, :bid, :dmg, :hp, CURRENT_TIMESTAMP)
                ON CONFLICT (guild_id, operation_id)
                DO UPDATE SET boss_id = EXCLUDED.boss_id,
                    damage = EXCLUDED.damage,
                    hp = EXCLUDED.hp,
                    updated_at = CURRENT_TIMESTAMP
            """),
            {"gid": guild_id, "oid": operation_id, "bid": boss_id, "dmg": damage, "hp": hp},
        )
        session.commit()


def list_guild_operation_boss_ranks(guild_id: int, operation_id: int, boss_id: int) -> list[dict]:
    with get_sync_session() as session:
        rows = session.execute(
            text("""
                SELECT user_id, damage
                FROM guild_operation_boss_ranks
                WHERE guild_id = :gid AND operation_id = :oid AND boss_id = :bid
                ORDER BY damage DESC, user_id ASC
            """),
            {"gid": guild_id, "oid": operation_id, "bid": boss_id},
        ).fetchall()
        return [{"user_id": r[0], "damage": r[1]} for r in rows]


def replace_guild_operation_boss_ranks(guild_id: int, operation_id: int, boss_id: int, ranks: list[dict]) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                DELETE FROM guild_operation_boss_ranks
                WHERE guild_id = :gid AND operation_id = :oid AND boss_id = :bid
            """),
            {"gid": guild_id, "oid": operation_id, "bid": boss_id},
        )
        ordered = sorted(ranks, key=lambda x: (-x["damage"], x["user_id"]))
        for rank in ordered:
            session.execute(
                text("""
                    INSERT INTO guild_operation_boss_ranks (guild_id, operation_id, boss_id, user_id, damage)
                    VALUES (:gid, :oid, :bid, :uid, :dmg)
                """),
                {"gid": guild_id, "oid": operation_id, "bid": boss_id, "uid": rank["user_id"], "dmg": rank["damage"]},
            )
        session.commit()


get_guild_operation_boss_state_sync = get_guild_operation_boss_state
upsert_guild_operation_boss_state_sync = upsert_guild_operation_boss_state
list_guild_operation_boss_ranks_sync = list_guild_operation_boss_ranks
replace_guild_operation_boss_ranks_sync = replace_guild_operation_boss_ranks
