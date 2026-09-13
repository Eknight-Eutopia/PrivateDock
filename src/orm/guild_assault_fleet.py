from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, JSON, select, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session

GUILD_ASSAULT_RECOMMENDATION_LIMIT = 9


class GuildAssaultFleetSlot(Base):
    __tablename__ = "guild_assault_fleet_slots"
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pos: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ship_id: Mapped[int] = mapped_column(BigInteger, default=0)
    last_time: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class GuildAssaultRecommendation(Base):
    __tablename__ = "guild_assault_recommendations"
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ship_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)


class GuildBossMissionFleet(Base):
    __tablename__ = "guild_boss_mission_fleets"
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    operation_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    fleet_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ships: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    commanders: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


def list_guild_assault_fleet_slots_by_commander(guild_id: int, commander_id: int) -> list[dict]:
    with get_sync_session() as session:
        rows = session.execute(
            select(GuildAssaultFleetSlot).where(
                GuildAssaultFleetSlot.guild_id == guild_id,
                GuildAssaultFleetSlot.commander_id == commander_id,
            ).order_by(GuildAssaultFleetSlot.pos.asc())
        ).scalars().all()
        return [
            {
                "guild_id": r.guild_id,
                "commander_id": r.commander_id,
                "pos": r.pos,
                "ship_id": r.ship_id,
                "last_time": r.last_time,
            }
            for r in rows
        ]


def list_guild_assault_fleet_slots_by_guild(guild_id: int) -> list[dict]:
    with get_sync_session() as session:
        rows = session.execute(
            select(GuildAssaultFleetSlot).where(
                GuildAssaultFleetSlot.guild_id == guild_id,
            ).order_by(GuildAssaultFleetSlot.commander_id.asc(), GuildAssaultFleetSlot.pos.asc())
        ).scalars().all()
        return [
            {
                "guild_id": r.guild_id,
                "commander_id": r.commander_id,
                "pos": r.pos,
                "ship_id": r.ship_id,
                "last_time": r.last_time,
            }
            for r in rows
        ]


def upsert_guild_assault_fleet_slots(guild_id: int, commander_id: int, slots: list[dict], now: int) -> None:
    with get_sync_session() as session:
        for slot in slots:
            session.execute(
                text("""
                    INSERT INTO guild_assault_fleet_slots (guild_id, commander_id, pos, ship_id, last_time, updated_at)
                    VALUES (:guild_id, :commander_id, :pos, :ship_id, :last_time, CURRENT_TIMESTAMP)
                    ON CONFLICT (guild_id, commander_id, pos)
                    DO UPDATE SET ship_id = EXCLUDED.ship_id,
                        last_time = EXCLUDED.last_time,
                        updated_at = CURRENT_TIMESTAMP
                """),
                {
                    "guild_id": guild_id,
                    "commander_id": commander_id,
                    "pos": slot["pos"],
                    "ship_id": slot["ship_id"],
                    "last_time": now,
                },
            )
        session.commit()


def list_guild_assault_recommendations(guild_id: int) -> list[dict]:
    with get_sync_session() as session:
        rows = session.execute(
            select(GuildAssaultRecommendation).where(
                GuildAssaultRecommendation.guild_id == guild_id,
            ).order_by(GuildAssaultRecommendation.commander_id.asc(), GuildAssaultRecommendation.ship_id.asc())
        ).scalars().all()
        return [
            {
                "guild_id": r.guild_id,
                "commander_id": r.commander_id,
                "ship_id": r.ship_id,
            }
            for r in rows
        ]


def set_guild_assault_recommendation(guild_id: int, commander_id: int, ship_id: int, recommended: bool) -> None:
    with get_sync_session() as session:
        if recommended:
            session.execute(
                text("SELECT id FROM guilds WHERE id = :gid FOR UPDATE"),
                {"gid": guild_id},
            )
            exists = session.execute(
                text("""
                    SELECT EXISTS(
                        SELECT 1 FROM guild_assault_recommendations
                        WHERE guild_id = :gid AND commander_id = :cid AND ship_id = :sid
                    )
                """),
                {"gid": guild_id, "cid": commander_id, "sid": ship_id},
            ).scalar()
            if not exists:
                count = session.execute(
                    text("SELECT COUNT(*) FROM guild_assault_recommendations WHERE guild_id = :gid"),
                    {"gid": guild_id},
                ).scalar()
                if count >= GUILD_ASSAULT_RECOMMENDATION_LIMIT:
                    raise ValueError("guild permission denied: recommendation limit reached")
            session.execute(
                text("""
                    INSERT INTO guild_assault_recommendations (guild_id, commander_id, ship_id)
                    VALUES (:gid, :cid, :sid)
                    ON CONFLICT (guild_id, commander_id, ship_id) DO NOTHING
                """),
                {"gid": guild_id, "cid": commander_id, "sid": ship_id},
            )
        else:
            session.execute(
                text("""
                    DELETE FROM guild_assault_recommendations
                    WHERE guild_id = :gid AND commander_id = :cid AND ship_id = :sid
                """),
                {"gid": guild_id, "cid": commander_id, "sid": ship_id},
            )
        session.commit()


def upsert_guild_boss_mission_fleets(guild_id: int, operation_id: int, fleets: list[dict]) -> None:
    with get_sync_session() as session:
        for fleet in fleets:
            ships_json = json.dumps(fleet.get("ships", []), ensure_ascii=False)
            commanders_json = json.dumps(fleet.get("commanders", []), ensure_ascii=False)
            session.execute(
                text("""
                    INSERT INTO guild_boss_mission_fleets (guild_id, operation_id, fleet_id, ships, commanders, updated_at)
                    VALUES (:gid, :oid, :fid, :ships, :cmds, CURRENT_TIMESTAMP)
                    ON CONFLICT (guild_id, operation_id, fleet_id)
                    DO UPDATE SET ships = EXCLUDED.ships,
                        commanders = EXCLUDED.commanders,
                        updated_at = CURRENT_TIMESTAMP
                """),
                {
                    "gid": guild_id,
                    "oid": operation_id,
                    "fid": fleet["fleet_id"],
                    "ships": ships_json,
                    "cmds": commanders_json,
                },
            )
        session.commit()


def list_guild_boss_mission_fleets(guild_id: int, operation_id: int) -> list[dict]:
    with get_sync_session() as session:
        rows = session.execute(
            text("""
                SELECT guild_id, operation_id, fleet_id, ships, commanders
                FROM guild_boss_mission_fleets
                WHERE guild_id = :gid AND operation_id = :oid
                ORDER BY fleet_id ASC
            """),
            {"gid": guild_id, "oid": operation_id},
        ).fetchall()
        result = []
        for row in rows:
            result.append({
                "guild_id": row[0],
                "operation_id": row[1],
                "fleet_id": row[2],
                "ships": json.loads(row[3]) if row[3] else [],
                "commanders": json.loads(row[4]) if row[4] else [],
            })
        result.sort(key=lambda x: x["fleet_id"])
        return result


def has_guild_boss_mission_fleet(guild_id: int, operation_id: int) -> bool:
    with get_sync_session() as session:
        return session.execute(
            text("""
                SELECT EXISTS(
                    SELECT 1 FROM guild_boss_mission_fleets
                    WHERE guild_id = :gid AND operation_id = :oid
                )
            """),
            {"gid": guild_id, "oid": operation_id},
        ).scalar() or False


list_guild_assault_fleet_slots_by_commander_sync = list_guild_assault_fleet_slots_by_commander
list_guild_assault_fleet_slots_by_guild_sync = list_guild_assault_fleet_slots_by_guild
upsert_guild_assault_fleet_slots_sync = upsert_guild_assault_fleet_slots
list_guild_assault_recommendations_sync = list_guild_assault_recommendations
set_guild_assault_recommendation_sync = set_guild_assault_recommendation
upsert_guild_boss_mission_fleets_sync = upsert_guild_boss_mission_fleets
list_guild_boss_mission_fleets_sync = list_guild_boss_mission_fleets
has_guild_boss_mission_fleet_sync = has_guild_boss_mission_fleet
