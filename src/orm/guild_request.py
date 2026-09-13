from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session

GUILD_SEARCH_LIMIT = 20


class GuildJoinRequest(Base):
    __tablename__ = "guild_join_requests"
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    applicant_commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    content: Mapped[str] = mapped_column(String, default="")
    requested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


def upsert_guild_join_request(guild_id: int, applicant_commander_id: int, content: str, requested_at: datetime) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO guild_join_requests (guild_id, applicant_commander_id, content, requested_at)
                VALUES (:gid, :cid, :content, :req_at)
                ON CONFLICT (guild_id, applicant_commander_id)
                DO UPDATE SET content = EXCLUDED.content, requested_at = EXCLUDED.requested_at
            """),
            {"gid": guild_id, "cid": applicant_commander_id, "content": content, "req_at": requested_at},
        )
        session.commit()


def delete_guild_join_request(guild_id: int, applicant_commander_id: int) -> bool:
    with get_sync_session() as session:
        result = session.execute(
            text("""
                DELETE FROM guild_join_requests
                WHERE guild_id = :gid AND applicant_commander_id = :cid
            """),
            {"gid": guild_id, "cid": applicant_commander_id},
        )
        session.commit()
        return result.rowcount > 0


def has_guild_join_request(guild_id: int, applicant_commander_id: int) -> bool:
    with get_sync_session() as session:
        return session.execute(
            text("""
                SELECT EXISTS(
                    SELECT 1 FROM guild_join_requests
                    WHERE guild_id = :gid AND applicant_commander_id = :cid
                )
            """),
            {"gid": guild_id, "cid": applicant_commander_id},
        ).scalar() or False


def count_guild_join_requests_by_applicant(applicant_commander_id: int) -> int:
    with get_sync_session() as session:
        return session.execute(
            text("SELECT COUNT(*) FROM guild_join_requests WHERE applicant_commander_id = :cid"),
            {"cid": applicant_commander_id},
        ).scalar() or 0


def list_guild_join_requests(guild_id: int) -> list[dict]:
    with get_sync_session() as session:
        rows = session.execute(
            text("""
                SELECT
                    gr.guild_id,
                    gr.applicant_commander_id,
                    gr.content,
                    gr.requested_at,
                    c.name,
                    c.level,
                    c.manifesto,
                    EXTRACT(EPOCH FROM c.last_login)::bigint,
                    c.display_icon_id,
                    c.display_skin_id,
                    c.selected_icon_frame_id,
                    c.selected_chat_frame_id,
                    c.display_icon_theme_id
                FROM guild_join_requests gr
                JOIN commanders c ON c.commander_id = gr.applicant_commander_id
                WHERE gr.guild_id = :gid
                ORDER BY gr.requested_at ASC, gr.applicant_commander_id ASC
            """),
            {"gid": guild_id},
        ).fetchall()
        result = []
        for r in rows:
            entry = {
                "guild_id": r[0],
                "applicant_commander_id": r[1],
                "content": r[2],
                "requested_at": r[3],
                "applicant": {
                    "commander_id": r[1],
                    "name": r[4],
                    "level": r[5],
                    "manifesto": r[6],
                    "last_login_unix": r[7] if r[7] else 0,
                    "display_icon_id": r[8],
                    "display_skin_id": r[9],
                    "selected_icon_frame_id": r[10],
                    "selected_chat_frame_id": r[11],
                    "display_icon_theme_id": r[12],
                },
            }
            result.append(entry)
        return result


def search_guild_directory_by_id(guild_id: int) -> list[dict]:
    if guild_id == 0:
        return []
    return _query_guild_directory("g.id = :gid", {"gid": guild_id})


def search_guild_directory_by_name(keyword: str) -> list[dict]:
    trimmed = keyword.strip()
    if not trimmed:
        return []
    return _query_guild_directory("LOWER(g.name) = LOWER(:kw)", {"kw": trimmed})


def _query_guild_directory(where_clause: str, params: dict) -> list[dict]:
    with get_sync_session() as session:
        sql = f"""
            SELECT
                g.id,
                g.policy,
                g.faction,
                g.name,
                g.level,
                g.announce,
                g.manifesto,
                g.exp,
                g.member_count,
                g.change_faction_cd,
                g.kick_leader_cd,
                g.capital,
                g.tech_id,
                COALESCE(c.commander_id, 0),
                COALESCE(c.name, ''),
                COALESCE(c.level, 0),
                COALESCE(c.manifesto, ''),
                COALESCE(EXTRACT(EPOCH FROM c.last_login)::bigint, 0),
                COALESCE(c.display_icon_id, 0),
                COALESCE(c.display_skin_id, 0),
                COALESCE(c.selected_icon_frame_id, 0),
                COALESCE(c.selected_chat_frame_id, 0),
                COALESCE(c.display_icon_theme_id, 0)
            FROM guilds g
            LEFT JOIN guild_members gm
                ON gm.guild_id = g.id AND gm.duty = 1
            LEFT JOIN commanders c
                ON c.commander_id = gm.commander_id AND c.deleted_at IS NULL
            WHERE g.deleted_at IS NULL
              AND {where_clause}
            ORDER BY g.id ASC
            LIMIT {GUILD_SEARCH_LIMIT}
        """
        full_params = dict(params)
        rows = session.execute(text(sql), full_params).fetchall()
        result = []
        for r in rows:
            entry = {
                "guild": {
                    "id": r[0],
                    "policy": r[1],
                    "faction": r[2],
                    "name": r[3],
                    "level": r[4],
                    "announce": r[5],
                    "manifesto": r[6],
                    "exp": r[7],
                    "member_count": r[8],
                    "change_faction_cd": r[9],
                    "kick_leader_cd": r[10],
                    "capital": r[11],
                    "tech_id": r[12],
                },
                "leader": {
                    "commander_id": r[13],
                    "name": r[14],
                    "level": r[15],
                    "manifesto": r[16],
                    "last_login_unix": r[17] if r[17] else 0,
                    "display_icon_id": r[18],
                    "display_skin_id": r[19],
                    "selected_icon_frame_id": r[20],
                    "selected_chat_frame_id": r[21],
                    "display_icon_theme_id": r[22],
                },
                "tech_seat": 0,
            }
            result.append(entry)
        return result


upsert_guild_join_request_sync = upsert_guild_join_request
delete_guild_join_request_sync = delete_guild_join_request
has_guild_join_request_sync = has_guild_join_request
count_guild_join_requests_by_applicant_sync = count_guild_join_requests_by_applicant
list_guild_join_requests_sync = list_guild_join_requests
search_guild_directory_by_id_sync = search_guild_directory_by_id
search_guild_directory_by_name_sync = search_guild_directory_by_name
