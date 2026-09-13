from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, text

from src.db.session import get_sync_session
from src.orm.atelier_state import AtelierState


# --- Atelier State (existing) ---

def get_or_create_atelier_state(commander_id: int) -> AtelierState:
    with get_sync_session() as session:
        result = session.execute(
            select(AtelierState).where(AtelierState.commander_id == commander_id)
        )
        obj = result.scalar_one_or_none()
        if obj is None:
            obj = AtelierState(commander_id=commander_id, data={})
            session.add(obj)
            session.commit()
            session.refresh(obj)
        return obj


def lock_atelier_state(commander_id: int) -> AtelierState:
    with get_sync_session() as session:
        result = session.execute(
            select(AtelierState)
            .where(AtelierState.commander_id == commander_id)
            .with_for_update()
        )
        obj = result.scalar_one_or_none()
        if obj is None:
            obj = AtelierState(commander_id=commander_id, data={})
            session.add(obj)
            session.commit()
            session.refresh(obj)
        return obj


def save_atelier_state(commander_id: int, data: dict):
    with get_sync_session() as session:
        result = session.execute(
            select(AtelierState).where(AtelierState.commander_id == commander_id)
        )
        obj = result.scalar_one_or_none()
        if obj is None:
            obj = AtelierState(commander_id=commander_id, data=data)
            session.add(obj)
        else:
            obj.data = data
        session.commit()


# --- Backyard Theme ID helper ---

def backyard_theme_id(commander_id: int, pos: int) -> str:
    return f"{commander_id}{pos}"


# --- Custom Theme Templates ---

def list_backyard_custom_theme_templates(commander_id: int) -> list[dict]:
    with get_sync_session() as session:
        rows = session.execute(
            text("""
                SELECT commander_id, pos, name, furniture_put_list, icon_image_md5, image_md5, upload_time
                FROM backyard_custom_theme_templates
                WHERE commander_id = :cid
                ORDER BY pos ASC
            """),
            {"cid": commander_id},
        ).fetchall()
        return [
            {
                "commander_id": r[0],
                "pos": r[1],
                "name": r[2],
                "furniture_put_list": json.loads(r[3]) if isinstance(r[3], str) else (r[3] or []),
                "icon_image_md5": r[4] or "",
                "image_md5": r[5] or "",
                "upload_time": r[6] or 0,
            }
            for r in rows
        ]


def get_backyard_custom_theme_template(commander_id: int, pos: int) -> Optional[dict]:
    with get_sync_session() as session:
        r = session.execute(
            text("""
                SELECT commander_id, pos, name, furniture_put_list, icon_image_md5, image_md5, upload_time
                FROM backyard_custom_theme_templates
                WHERE commander_id = :cid AND pos = :pos
            """),
            {"cid": commander_id, "pos": pos},
        ).fetchone()
        if r is None:
            return None
        return {
            "commander_id": r[0],
            "pos": r[1],
            "name": r[2],
            "furniture_put_list": json.loads(r[3]) if isinstance(r[3], str) else (r[3] or []),
            "icon_image_md5": r[4] or "",
            "image_md5": r[5] or "",
            "upload_time": r[6] or 0,
        }


def upsert_backyard_custom_theme_template(
    commander_id: int, pos: int, name: str,
    furniture_put_list: Any, icon_md5: str, image_md5: str,
):
    with get_sync_session() as session:
        raw = json.dumps(furniture_put_list) if not isinstance(furniture_put_list, str) else furniture_put_list
        session.execute(
            text("""
                INSERT INTO backyard_custom_theme_templates
                    (commander_id, pos, name, furniture_put_list, icon_image_md5, image_md5, upload_time)
                VALUES (:cid, :pos, :name, :fpl, :icon, :img, 0)
                ON CONFLICT (commander_id, pos)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    furniture_put_list = EXCLUDED.furniture_put_list,
                    icon_image_md5 = EXCLUDED.icon_image_md5,
                    image_md5 = EXCLUDED.image_md5
            """),
            {"cid": commander_id, "pos": pos, "name": name,
             "fpl": raw, "icon": icon_md5, "img": image_md5},
        )
        session.commit()


def delete_backyard_custom_theme_template(commander_id: int, pos: int):
    with get_sync_session() as session:
        session.execute(
            text("""
                DELETE FROM backyard_custom_theme_templates
                WHERE commander_id = :cid AND pos = :pos
            """),
            {"cid": commander_id, "pos": pos},
        )
        session.commit()


# --- Published Theme Versions ---

def create_backyard_published_theme_version(
    commander_id: int, pos: int, name: str,
    furniture_put_list: Any, icon_md5: str, image_md5: str,
) -> dict:
    upload_time = int(datetime.now(timezone.utc).timestamp())
    theme_id = backyard_theme_id(commander_id, pos)
    raw = json.dumps(furniture_put_list) if not isinstance(furniture_put_list, str) else furniture_put_list
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO backyard_published_theme_versions
                    (theme_id, upload_time, owner_id, pos, name,
                     furniture_put_list, icon_image_md5, image_md5, like_count, fav_count)
                VALUES (:tid, :ut, :oid, :pos, :name,
                        :fpl, :icon, :img, 0, 0)
            """),
            {
                "tid": theme_id, "ut": upload_time, "oid": commander_id,
                "pos": pos, "name": name, "fpl": raw,
                "icon": icon_md5, "img": image_md5,
            },
        )
        session.commit()
    return {
        "theme_id": theme_id,
        "upload_time": upload_time,
        "owner_id": commander_id,
        "pos": pos,
        "name": name,
        "furniture_put_list": furniture_put_list,
        "icon_image_md5": icon_md5,
        "image_md5": image_md5,
        "like_count": 0,
        "fav_count": 0,
    }


def delete_backyard_published_theme_versions_by_theme_id(theme_id: str):
    with get_sync_session() as session:
        session.execute(
            text("DELETE FROM backyard_published_theme_versions WHERE theme_id = :tid"),
            {"tid": theme_id},
        )
        session.commit()


def latest_backyard_published_theme_version(theme_id: str) -> Optional[dict]:
    with get_sync_session() as session:
        r = session.execute(
            text("""
                SELECT theme_id, upload_time, owner_id, pos, name,
                       furniture_put_list, icon_image_md5, image_md5, like_count, fav_count
                FROM backyard_published_theme_versions
                WHERE theme_id = :tid
                ORDER BY upload_time DESC
                LIMIT 1
            """),
            {"tid": theme_id},
        ).fetchone()
        if r is None:
            return None
        return {
            "theme_id": r[0],
            "upload_time": r[1],
            "owner_id": r[2],
            "pos": r[3],
            "name": r[4],
            "furniture_put_list": json.loads(r[5]) if isinstance(r[5], str) else (r[5] or []),
            "icon_image_md5": r[6] or "",
            "image_md5": r[7] or "",
            "like_count": r[8] or 0,
            "fav_count": r[9] or 0,
        }


def list_backyard_published_theme_ids_by_page(page: int, page_size: int) -> dict:
    with get_sync_session() as session:
        offset = 0
        if page > 1:
            offset = (page - 1) * page_size
        rows = session.execute(
            text("""
                SELECT theme_id
                FROM backyard_published_theme_versions
                GROUP BY theme_id
                ORDER BY MAX(upload_time) DESC
                LIMIT :lim OFFSET :off
            """),
            {"lim": page_size, "off": offset},
        ).fetchall()
        ids = [r[0] for r in rows]
        count_row = session.execute(
            text("SELECT COUNT(DISTINCT theme_id) FROM backyard_published_theme_versions")
        ).fetchone()
        total = count_row[0] if count_row else 0
    return {"list": ids, "page": page, "page_size": page_size, "total": total}


def list_latest_backyard_published_theme_versions() -> list[dict]:
    with get_sync_session() as session:
        rows = session.execute(
            text("""
                -- ``DISTINCT ON (theme_id)`` is PostgreSQL-only; ROW_NUMBER()
                -- expresses the same "newest row per theme" on every engine
                -- (PostgreSQL 8.4+, SQLite 3.25+).
                SELECT theme_id, upload_time, owner_id, pos, name,
                       furniture_put_list, icon_image_md5, image_md5, like_count, fav_count
                FROM (
                    SELECT theme_id, upload_time, owner_id, pos, name,
                           furniture_put_list, icon_image_md5, image_md5, like_count, fav_count,
                           ROW_NUMBER() OVER (
                               PARTITION BY theme_id ORDER BY upload_time DESC
                           ) AS rn
                    FROM backyard_published_theme_versions
                ) latest
                WHERE rn = 1
                ORDER BY upload_time DESC, theme_id ASC
            """),
        ).fetchall()
        return [
            {
                "theme_id": r[0],
                "upload_time": r[1],
                "owner_id": r[2],
                "pos": r[3],
                "name": r[4],
                "furniture_put_list": json.loads(r[5]) if isinstance(r[5], str) else (r[5] or []),
                "icon_image_md5": r[6] or "",
                "image_md5": r[7] or "",
                "like_count": r[8] or 0,
                "fav_count": r[9] or 0,
            }
            for r in rows
        ]


def get_backyard_published_theme_count() -> int:
    with get_sync_session() as session:
        r = session.execute(
            text("SELECT COUNT(DISTINCT theme_id) FROM backyard_published_theme_versions")
        ).fetchone()
        return r[0] if r else 0


# --- Theme Collections ---

def check_backyard_theme_collection_exists(commander_id: int, theme_id: str, upload_time: int) -> bool:
    with get_sync_session() as session:
        r = session.execute(
            text("""
                SELECT 1 FROM backyard_theme_collections
                WHERE commander_id = :cid AND theme_id = :tid AND upload_time = :ut
            """),
            {"cid": commander_id, "tid": theme_id, "ut": upload_time},
        ).fetchone()
        return r is not None


def add_backyard_theme_collection(commander_id: int, theme_id: str, upload_time: int):
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO backyard_theme_collections (commander_id, theme_id, upload_time)
                VALUES (:cid, :tid, :ut)
                ON CONFLICT DO NOTHING
            """),
            {"cid": commander_id, "tid": theme_id, "ut": upload_time},
        )
        session.commit()


def remove_backyard_theme_collection(commander_id: int, theme_id: str):
    with get_sync_session() as session:
        session.execute(
            text("""
                DELETE FROM backyard_theme_collections
                WHERE commander_id = :cid AND theme_id = :tid
            """),
            {"cid": commander_id, "tid": theme_id},
        )
        session.commit()


def count_backyard_theme_collections(commander_id: int) -> int:
    with get_sync_session() as session:
        r = session.execute(
            text("SELECT COUNT(*) FROM backyard_theme_collections WHERE commander_id = :cid"),
            {"cid": commander_id},
        ).fetchone()
        return r[0] if r else 0


def list_backyard_theme_collections(commander_id: int) -> dict:
    with get_sync_session() as session:
        rows = session.execute(
            text("""
                SELECT theme_id, upload_time
                FROM backyard_theme_collections
                WHERE commander_id = :cid
                ORDER BY upload_time DESC
            """),
            {"cid": commander_id},
        ).fetchall()
        collections = [
            {"theme_id": r[0], "upload_time": r[1]}
            for r in rows
        ]
        total = len(collections)
        pages = (total + 9) // 10 if total > 0 else 1
    return {"collections": collections, "pages": max(pages, 1)}


def list_backyard_theme_collection_upload_times(commander_id: int) -> set[int]:
    with get_sync_session() as session:
        rows = session.execute(
            text("SELECT upload_time FROM backyard_theme_collections WHERE commander_id = :cid"),
            {"cid": commander_id},
        ).fetchall()
        return {r[0] for r in rows}


# --- Theme Likes ---

def check_backyard_theme_like_exists(commander_id: int, theme_id: str, upload_time: int) -> bool:
    with get_sync_session() as session:
        r = session.execute(
            text("""
                SELECT 1 FROM backyard_theme_likes
                WHERE commander_id = :cid AND theme_id = :tid AND upload_time = :ut
            """),
            {"cid": commander_id, "tid": theme_id, "ut": upload_time},
        ).fetchone()
        return r is not None


def add_backyard_theme_like(commander_id: int, theme_id: str, upload_time: int):
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO backyard_theme_likes (commander_id, theme_id, upload_time)
                VALUES (:cid, :tid, :ut)
                ON CONFLICT DO NOTHING
            """),
            {"cid": commander_id, "tid": theme_id, "ut": upload_time},
        )
        session.commit()


def increment_backyard_theme_like_count(theme_id: str, upload_time: int):
    with get_sync_session() as session:
        session.execute(
            text("""
                UPDATE backyard_published_theme_versions
                SET like_count = like_count + 1
                WHERE theme_id = :tid AND upload_time = :ut
            """),
            {"tid": theme_id, "ut": upload_time},
        )
        session.commit()


def increment_backyard_theme_fav_count(theme_id: str, upload_time: int):
    with get_sync_session() as session:
        session.execute(
            text("""
                UPDATE backyard_published_theme_versions
                SET fav_count = fav_count + 1
                WHERE theme_id = :tid AND upload_time = :ut
            """),
            {"tid": theme_id, "ut": upload_time},
        )
        session.commit()


def decrement_backyard_theme_fav_count(theme_id: str, upload_time: int):
    with get_sync_session() as session:
        session.execute(
            text("""
                UPDATE backyard_published_theme_versions
                SET fav_count = fav_count - 1
                WHERE theme_id = :tid AND upload_time = :ut
                  AND fav_count > 0
            """),
            {"tid": theme_id, "ut": upload_time},
        )
        session.commit()


# --- Theme Informs ---

def insert_backyard_theme_inform(
    reporter_id: int, target_id: int,
    target_name: str, theme_id: str,
    theme_name: str, reason: int,
):
    created_at = int(datetime.now(timezone.utc).timestamp())
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO backyard_theme_informs
                    (reporter_id, target_id, target_name, theme_id, theme_name, reason, created_at)
                VALUES (:rid, :tid, :tn, :thid, :thn, :r, :ca)
            """),
            {
                "rid": reporter_id, "tid": target_id, "tn": target_name,
                "thid": theme_id, "thn": theme_name, "r": reason, "ca": created_at,
            },
        )
        session.commit()


# --- Utility ---

def to_furniture_put_info_list(furniture_put_list: Any) -> list:
    if furniture_put_list is None:
        return []
    if isinstance(furniture_put_list, str):
        try:
            return json.loads(furniture_put_list)
        except (json.JSONDecodeError, TypeError):
            return []
    if isinstance(furniture_put_list, list):
        return furniture_put_list
    return []
