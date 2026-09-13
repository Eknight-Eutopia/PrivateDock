from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, JSON, select, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


class GuildOperationState(Base):
    __tablename__ = "guild_operation_states"
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chapter_id: Mapped[int] = mapped_column(BigInteger, default=0)
    start_time: Mapped[int] = mapped_column(BigInteger, default=0)
    end_time: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class GuildOperationEvent(Base):
    __tablename__ = "guild_operation_events"
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_tid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    position: Mapped[int] = mapped_column(BigInteger, default=0)
    start_time: Mapped[int] = mapped_column(BigInteger, default=0)
    complete_time: Mapped[int] = mapped_column(BigInteger, default=0)
    efficiency: Mapped[int] = mapped_column(BigInteger, default=0)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    shipinevent: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    attr_acc_list: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    attr_count_list: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    eventnodes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    personship: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    formation_time: Mapped[int] = mapped_column(BigInteger, default=0)


class GuildOperationPerf(Base):
    __tablename__ = "guild_operation_perfs"
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_tid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    perf_index: Mapped[int] = mapped_column(BigInteger, default=0)


class GuildReport(Base):
    __tablename__ = "guild_reports"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, default=0)
    event_id: Mapped[int] = mapped_column(BigInteger, default=0)
    event_type: Mapped[int] = mapped_column(BigInteger, default=0)
    score: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[int] = mapped_column(BigInteger, default=0)
    claimed: Mapped[bool] = mapped_column(Boolean, default=False)
    drop_type: Mapped[int] = mapped_column(BigInteger, default=0)
    drop_id: Mapped[int] = mapped_column(BigInteger, default=0)
    drop_count: Mapped[int] = mapped_column(BigInteger, default=0)


class GuildReportNode(Base):
    __tablename__ = "guild_report_nodes"
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    report_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    node_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    status: Mapped[int] = mapped_column(BigInteger, default=0)


class GuildOperationParticipant(Base):
    __tablename__ = "guild_operation_participants"
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    join_times: Mapped[int] = mapped_column(BigInteger, default=0)
    is_participant: Mapped[int] = mapped_column(BigInteger, default=0)


GO_DUTY_COMMANDER = 1
GO_DUTY_DEPUTY = 2
ERR_GUILD_PERMISSION = ValueError("guild permission denied")
ERR_GUILD_INSUFFICIENT_CAP = ValueError("insufficient capital")


def _get_guild_for_commander_tx(session, commander_id: int) -> tuple:
    from src.orm.guild_membership import GuildMembership
    from src.orm.guild_core import Guild
    member = session.execute(
        select(GuildMembership).where(
            GuildMembership.commander_id == commander_id,
            GuildMembership.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if member is None:
        raise ValueError("commander not in guild")
    guild = session.execute(
        select(Guild).where(
            Guild.id == member.guild_id,
            Guild.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if guild is None:
        raise ValueError("guild not found")
    return guild, member


def get_guild_operation_state_for_commander(commander_id: int) -> Optional[dict]:
    from src.orm.guild_core import get_guild_for_commander
    guild = get_guild_for_commander(commander_id)
    if guild is None:
        return None
    state = get_guild_operation_state(guild.id)
    if state is None:
        return None
    join_times, is_participant = get_guild_operation_participant(guild.id, commander_id)
    state["join_times"] = join_times
    state["is_participant"] = is_participant
    return state


def get_guild_operation_state(guild_id: int) -> Optional[dict]:
    with get_sync_session() as session:
        row = session.execute(
            select(GuildOperationState).where(GuildOperationState.guild_id == guild_id)
        ).scalar_one_or_none()
        if row is None:
            return None
        events = _list_guild_operation_events(session, guild_id, row.chapter_id)
        perfs = _list_guild_operation_perfs(session, guild_id)
        return {
            "guild_id": row.guild_id,
            "chapter_id": row.chapter_id,
            "start_time": row.start_time,
            "end_time": row.end_time,
            "events": events,
            "perfs": perfs,
            "join_times": 0,
            "is_participant": 0,
        }


def _list_guild_operation_events(session, guild_id: int, chapter_id: int) -> list[dict]:
    rows = session.execute(
        select(GuildOperationEvent).where(
            GuildOperationEvent.guild_id == guild_id,
            GuildOperationEvent.event_tid == chapter_id,
        ).order_by(GuildOperationEvent.event_tid.asc())
    ).scalars().all()
    return [
        {
            "event_tid": r.event_tid,
            "position": r.position,
            "start_time": r.start_time,
            "complete_time": r.complete_time,
            "efficiency": r.efficiency,
            "completed": r.completed,
            "ship_in_event": r.shipinevent,
            "attr_acc_list": r.attr_acc_list,
            "attr_count_list": r.attr_count_list,
            "event_nodes": r.eventnodes,
            "person_ship": r.personship,
            "formation_time": r.formation_time,
        }
        for r in rows
    ]


def _list_guild_operation_perfs(session, guild_id: int) -> list[dict]:
    rows = session.execute(
        select(GuildOperationPerf).where(
            GuildOperationPerf.guild_id == guild_id,
        ).order_by(GuildOperationPerf.event_tid.asc())
    ).scalars().all()
    return [{"event_tid": r.event_tid, "index": r.perf_index} for r in rows]


def get_guild_operation_participant(guild_id: int, commander_id: int) -> tuple:
    with get_sync_session() as session:
        row = session.execute(
            select(GuildOperationParticipant).where(
                GuildOperationParticipant.guild_id == guild_id,
                GuildOperationParticipant.commander_id == commander_id,
            )
        ).scalar_one_or_none()
        if row is None:
            return (0, 0)
        return (row.join_times, row.is_participant)


def activate_guild_operation(commander_id: int, chapter_id: int, consume: int, duration_seconds: int, now: int) -> None:
    with get_sync_session() as session:
        guild, member = _get_guild_for_commander_tx(session, commander_id)
        if member.duty != GO_DUTY_COMMANDER and member.duty != GO_DUTY_DEPUTY:
            raise ERR_GUILD_PERMISSION
        _ensure_no_active_operation(session, guild.id, now)
        result = session.execute(
            text("""
                UPDATE guilds SET capital = capital - :cost, updated_at = CURRENT_TIMESTAMP
                WHERE id = :gid AND capital >= :cost
            """),
            {"gid": guild.id, "cost": consume},
        )
        if result.rowcount == 0:
            raise ERR_GUILD_INSUFFICIENT_CAP
        session.execute(
            text("DELETE FROM guild_operation_participants WHERE guild_id = :gid"),
            {"gid": guild.id},
        )
        session.execute(
            text("""
                INSERT INTO guild_operation_states (guild_id, chapter_id, start_time, end_time, updated_at)
                VALUES (:gid, :ch, :st, :et, CURRENT_TIMESTAMP)
                ON CONFLICT (guild_id)
                DO UPDATE SET chapter_id = EXCLUDED.chapter_id,
                    start_time = EXCLUDED.start_time,
                    end_time = EXCLUDED.end_time,
                    updated_at = CURRENT_TIMESTAMP
            """),
            {"gid": guild.id, "ch": chapter_id, "st": now, "et": now + duration_seconds},
        )
        session.execute(
            text("UPDATE guilds SET capital = capital, updated_at = CURRENT_TIMESTAMP WHERE id = :gid"),
            {"gid": guild.id},
        )
        session.execute(
            text("""
                INSERT INTO guild_operation_events (
                    guild_id, event_tid, position, start_time, complete_time, efficiency,
                    completed, shipinevent, attr_acc_list, attr_count_list, eventnodes,
                    personship, formation_time
                )
                VALUES (:gid, :etid, 1, :st, 0, 0, false,
                    '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, 0)
                ON CONFLICT (guild_id, event_tid)
                DO UPDATE SET
                    position = EXCLUDED.position,
                    start_time = EXCLUDED.start_time,
                    complete_time = EXCLUDED.complete_time,
                    efficiency = EXCLUDED.efficiency,
                    completed = EXCLUDED.completed,
                    shipinevent = EXCLUDED.shipinevent,
                    attr_acc_list = EXCLUDED.attr_acc_list,
                    attr_count_list = EXCLUDED.attr_count_list,
                    eventnodes = EXCLUDED.eventnodes,
                    personship = EXCLUDED.personship,
                    formation_time = EXCLUDED.formation_time
            """),
            {"gid": guild.id, "etid": chapter_id, "st": now},
        )
        session.commit()


def _ensure_no_active_operation(session, guild_id: int, now: int) -> None:
    row = session.execute(
        select(GuildOperationState.end_time).where(GuildOperationState.guild_id == guild_id)
    ).scalar_one_or_none()
    if row is not None and row > now:
        raise ERR_GUILD_PERMISSION


def list_guild_operation_events(guild_id: int, chapter_id: int) -> list[dict]:
    with get_sync_session() as session:
        return _list_guild_operation_events(session, guild_id, chapter_id)


def list_guild_operation_perfs(guild_id: int) -> list[dict]:
    with get_sync_session() as session:
        return _list_guild_operation_perfs(session, guild_id)


def upsert_guild_operation_perf(guild_id: int, event_tid: int, index: int) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO guild_operation_perfs (guild_id, event_tid, perf_index)
                VALUES (:gid, :etid, :idx)
                ON CONFLICT (guild_id, event_tid)
                DO UPDATE SET perf_index = EXCLUDED.perf_index
            """),
            {"gid": guild_id, "etid": event_tid, "idx": index},
        )
        session.commit()


def upsert_guild_operation_perfs_monotonic(guild_id: int, perfs: list[dict]) -> None:
    with get_sync_session() as session:
        ordered = sorted(perfs, key=lambda x: x["event_tid"])
        for perf in ordered:
            existing = session.execute(
                text("""
                    SELECT perf_index FROM guild_operation_perfs
                    WHERE guild_id = :gid AND event_tid = :etid
                    FOR UPDATE
                """),
                {"gid": guild_id, "etid": perf["event_tid"]},
            ).scalar_one_or_none()
            if existing is not None and perf["index"] < existing:
                raise ERR_GUILD_PERMISSION
            session.execute(
                text("""
                    INSERT INTO guild_operation_perfs (guild_id, event_tid, perf_index)
                    VALUES (:gid, :etid, :idx)
                    ON CONFLICT (guild_id, event_tid)
                    DO UPDATE SET perf_index = EXCLUDED.perf_index
                """),
                {"gid": guild_id, "etid": perf["event_tid"], "idx": perf["index"]},
            )
        session.commit()


def get_guild_operation_event(guild_id: int, event_tid: int) -> Optional[dict]:
    with get_sync_session() as session:
        row = session.execute(
            select(GuildOperationEvent).where(
                GuildOperationEvent.guild_id == guild_id,
                GuildOperationEvent.event_tid == event_tid,
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return {
            "event_tid": row.event_tid,
            "position": row.position,
            "start_time": row.start_time,
            "complete_time": row.complete_time,
            "efficiency": row.efficiency,
            "completed": row.completed,
            "ship_in_event": row.shipinevent,
            "attr_acc_list": row.attr_acc_list,
            "attr_count_list": row.attr_count_list,
            "event_nodes": row.eventnodes,
            "person_ship": row.personship,
            "formation_time": row.formation_time,
        }


def update_guild_operation_event_formation(guild_id: int, event_tid: int, person_ship: dict, formation_time: int) -> None:
    with get_sync_session() as session:
        person_ship_json = json.dumps(person_ship, ensure_ascii=False)
        session.execute(
            text("""
                UPDATE guild_operation_events
                SET personship = :ps, formation_time = :ft
                WHERE guild_id = :gid AND event_tid = :etid
            """),
            {"gid": guild_id, "etid": event_tid, "ps": person_ship_json, "ft": formation_time},
        )
        session.commit()


def update_guild_operation_event_refresh(guild_id: int, event_tid: int, formation_time: int) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                UPDATE guild_operation_events
                SET formation_time = :ft
                WHERE guild_id = :gid AND event_tid = :etid
            """),
            {"gid": guild_id, "etid": event_tid, "ft": formation_time},
        )
        session.commit()


def list_guild_reports_since(guild_id: int, index: int) -> list[dict]:
    with get_sync_session() as session:
        rows = session.execute(
            text("""
                SELECT id, guild_id, event_id, event_type, score, status, claimed, drop_type, drop_id, drop_count
                FROM guild_reports
                WHERE guild_id = :gid AND id > :idx
                ORDER BY id ASC
            """),
            {"gid": guild_id, "idx": index},
        ).fetchall()
        result = []
        for row in rows:
            nodes = _list_guild_report_nodes(session, guild_id, row[0])
            result.append({
                "id": row[0],
                "guild_id": row[1],
                "event_id": row[2],
                "event_type": row[3],
                "score": row[4],
                "status": row[5],
                "claimed": row[6],
                "drop_type": row[7],
                "drop_id": row[8],
                "drop_count": row[9],
                "nodes": nodes,
            })
        return result


def _list_guild_report_nodes(session, guild_id: int, report_id: int) -> list[dict]:
    rows = session.execute(
        text("""
            SELECT node_id, status
            FROM guild_report_nodes
            WHERE guild_id = :gid AND report_id = :rid
            ORDER BY node_id ASC
        """),
        {"gid": guild_id, "rid": report_id},
    ).fetchall()
    return [{"node_id": r[0], "status": r[1]} for r in rows]


def claim_guild_reports(guild_id: int, report_ids: list[int]) -> list[dict]:
    with get_sync_session() as session:
        reports = []
        for report_id in report_ids:
            row = session.execute(
                text("""
                    SELECT id, guild_id, event_id, event_type, score, status, claimed, drop_type, drop_id, drop_count
                    FROM guild_reports
                    WHERE guild_id = :gid AND id = :rid
                    FOR UPDATE
                """),
                {"gid": guild_id, "rid": report_id},
            ).fetchone()
            if row is None:
                raise ValueError("report not found")
            report = {
                "id": row[0],
                "guild_id": row[1],
                "event_id": row[2],
                "event_type": row[3],
                "score": row[4],
                "status": row[5],
                "claimed": row[6],
                "drop_type": row[7],
                "drop_id": row[8],
                "drop_count": row[9],
            }
            if report["claimed"] or report["status"] != 1:
                raise ERR_GUILD_PERMISSION
            session.execute(
                text("""
                    UPDATE guild_reports
                    SET claimed = true, status = 2
                    WHERE guild_id = :gid AND id = :rid
                """),
                {"gid": guild_id, "rid": report_id},
            )
            reports.append(report)
        session.commit()
        return reports


def list_guild_report_ranks(guild_id: int, report_id: int) -> list[dict]:
    with get_sync_session() as session:
        rows = session.execute(
            text("""
                SELECT user_id, damage
                FROM guild_report_ranks
                WHERE guild_id = :gid AND report_id = :rid
            """),
            {"gid": guild_id, "rid": report_id},
        ).fetchall()
        ranks = [{"user_id": r[0], "damage": r[1]} for r in rows]
        ranks.sort(key=lambda x: (-x["damage"], x["user_id"]))
        return ranks


def update_guild_operation_participation(commander_id: int, now: int, max_join_times: int, liveness_gain: int) -> None:
    with get_sync_session() as session:
        guild, _ = _get_guild_for_commander_tx(session, commander_id)
        state = session.execute(
            select(GuildOperationState).where(GuildOperationState.guild_id == guild.id)
        ).scalar_one_or_none()
        if state is None or state.end_time <= now:
            raise ERR_GUILD_PERMISSION
        join_times, _ = _get_guild_operation_participant_tx(session, guild.id, commander_id)
        if join_times >= max_join_times:
            result = session.execute(
                text("""
                    UPDATE guild_user_infos
                    SET extra_operation = extra_operation - 1
                    WHERE commander_id = :cid AND extra_operation > 0
                """),
                {"cid": commander_id},
            )
            if result.rowcount == 0:
                raise ERR_GUILD_PERMISSION
        else:
            join_times += 1
        session.execute(
            text("""
                INSERT INTO guild_operation_participants (guild_id, commander_id, join_times, is_participant)
                VALUES (:gid, :cid, :jt, 1)
                ON CONFLICT (guild_id, commander_id)
                DO UPDATE SET join_times = EXCLUDED.join_times, is_participant = 1
            """),
            {"gid": guild.id, "cid": commander_id, "jt": join_times},
        )
        session.execute(
            text("""
                UPDATE guild_members
                SET liveness = liveness + :lg
                WHERE guild_id = :gid AND commander_id = :cid
            """),
            {"gid": guild.id, "cid": commander_id, "lg": liveness_gain},
        )
        session.commit()


def _get_guild_operation_participant_tx(session, guild_id: int, commander_id: int) -> tuple:
    row = session.execute(
        select(GuildOperationParticipant).where(
            GuildOperationParticipant.guild_id == guild_id,
            GuildOperationParticipant.commander_id == commander_id,
        )
    ).scalar_one_or_none()
    if row is None:
        return (0, 0)
    return (row.join_times, row.is_participant)


get_guild_operation_state_for_commander_sync = get_guild_operation_state_for_commander
get_guild_operation_state_sync = get_guild_operation_state
activate_guild_operation_sync = activate_guild_operation
list_guild_operation_events_sync = list_guild_operation_events
list_guild_operation_perfs_sync = list_guild_operation_perfs
get_guild_operation_participant_sync = get_guild_operation_participant
upsert_guild_operation_perf_sync = upsert_guild_operation_perf
upsert_guild_operation_perfs_monotonic_sync = upsert_guild_operation_perfs_monotonic
get_guild_operation_event_sync = get_guild_operation_event
update_guild_operation_event_formation_sync = update_guild_operation_event_formation
update_guild_operation_event_refresh_sync = update_guild_operation_event_refresh
list_guild_reports_since_sync = list_guild_reports_since
claim_guild_reports_sync = claim_guild_reports
list_guild_report_ranks_sync = list_guild_report_ranks
update_guild_operation_participation_sync = update_guild_operation_participation
