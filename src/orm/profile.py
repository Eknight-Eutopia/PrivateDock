from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy import text as sa_text

from src.db.session import get_session, get_sync_session
from src.orm.commander import Commander
from src.orm.commander_furniture import CommanderFurniture
from src.orm.commander_medal_display import CommanderMedalDisplay
from src.orm.owned_skin import OwnedSkin


# ── Async CRUD (prefixed with _async) ──


async def _async_get_player_profile_stats(commander_id: int) -> dict:
    async with get_session() as session:
        return _build_profile_stats(session, commander_id)


async def _async_get_commander_social_profiles_by_ids(commander_ids: list[int]) -> dict:
    async with get_session() as session:
        result = await session.execute(
            select(
                Commander.commander_id,
                Commander.name,
                Commander.level,
                Commander.last_login,
                Commander.display_skin_id,
                Commander.display_icon_id,
            ).where(
                Commander.commander_id.in_(commander_ids),
                Commander.deleted_at.is_(None),
            )
        )
        profiles = {}
        for row in result.fetchall():
            profiles[row.commander_id] = row
        return profiles


async def _async_list_friend_profiles(commander_id: int) -> list:
    async with get_session() as session:
        result = await session.execute(
            sa_text(
                "SELECT c.commander_id, c.name, c.level, c.last_login, "
                "c.display_skin_id, c.display_icon_id "
                "FROM commanders c "
                "JOIN friend_relationships f ON f.friend_id = c.commander_id "
                "WHERE f.commander_id = :cid AND c.deleted_at IS NULL"
            ),
            {"cid": commander_id},
        )
        return list(result.fetchall())


# ── Sync CRUD (prefixed with _sync) ──


def _sync_get_player_profile_stats(commander_id: int) -> dict:
    with get_sync_session() as session:
        return _build_profile_stats(session, commander_id)


def _sync_get_commander_social_profiles_by_ids(commander_ids: list[int]) -> dict:
    with get_sync_session() as session:
        result = session.execute(
            select(
                Commander.commander_id,
                Commander.name,
                Commander.level,
                Commander.last_login,
                Commander.display_skin_id,
                Commander.display_icon_id,
            ).where(
                Commander.commander_id.in_(commander_ids),
                Commander.deleted_at.is_(None),
            )
        )
        profiles = {}
        for row in result.fetchall():
            profiles[row.commander_id] = row
        return profiles


def _sync_list_friend_profiles(commander_id: int) -> list:
    with get_sync_session() as session:
        result = session.execute(
            sa_text(
                "SELECT c.commander_id, c.name, c.level, c.last_login, "
                "c.display_skin_id, c.display_icon_id "
                "FROM commanders c "
                "JOIN friend_relationships f ON f.friend_id = c.commander_id "
                "WHERE f.commander_id = :cid AND c.deleted_at IS NULL"
            ),
            {"cid": commander_id},
        )
        return list(result.fetchall())


# ── Shared helpers ──


def _build_profile_stats(session, commander_id: int) -> dict:
    result = {
        "medal_number": 0,
        "furniture_number": 0,
        "ship_num_total": 0,
        "ship_num_120": 0,
        "ship_num_125": 0,
        "marry_number": 0,
        "love200_num": 0,
        "collect_num": 0,
        "character_id": 100001,
        "first_lady_id": 0,
        "first_lady_name": "",
        "first_lady_time": 0,
        "skin_num": 0,
        "skin_ship_num": 0,
    }
    medal_count = session.execute(
        select(func.count()).select_from(CommanderMedalDisplay).where(
            CommanderMedalDisplay.commander_id == commander_id,
        )
    ).scalar()
    if medal_count:
        result["medal_number"] = medal_count

    furniture_sum = session.execute(
        select(func.coalesce(func.sum(CommanderFurniture.count), 0)).where(
            CommanderFurniture.commander_id == commander_id,
        )
    ).scalar()
    if furniture_sum is not None:
        result["furniture_number"] = int(furniture_sum)

    ship_row = session.execute(
        sa_text(
            "SELECT COUNT(*) AS ship_num_total, "
            "COUNT(*) FILTER (WHERE max_level >= 120) AS ship_num_120, "
            "COUNT(*) FILTER (WHERE max_level >= 125) AS ship_num_125, "
            "COUNT(*) FILTER (WHERE propose = TRUE) AS marry_number, "
            "COUNT(*) FILTER (WHERE intimacy >= 20000) AS love200_num, "
            "COUNT(DISTINCT ship_id / 10) AS collect_num "
            "FROM owned_ships WHERE owner_id = :cid AND deleted_at IS NULL"
        ),
        {"cid": commander_id},
    ).fetchone()
    if ship_row:
        result["ship_num_total"] = int(ship_row[0])
        result["ship_num_120"] = int(ship_row[1])
        result["ship_num_125"] = int(ship_row[2])
        result["marry_number"] = int(ship_row[3])
        result["love200_num"] = int(ship_row[4])
        result["collect_num"] = int(ship_row[5])

    char_row = session.execute(
        sa_text(
            "SELECT COALESCE("
            "(SELECT ship_id FROM owned_ships WHERE owner_id = :cid1 AND deleted_at IS NULL "
            "AND is_secretary = TRUE ORDER BY COALESCE(secretary_position, 999), id LIMIT 1), "
            "(SELECT ship_id FROM owned_ships WHERE owner_id = :cid2 AND deleted_at IS NULL "
            "ORDER BY id LIMIT 1), 100001)"
        ),
        {"cid1": commander_id, "cid2": commander_id},
    ).scalar()
    if char_row:
        result["character_id"] = int(char_row)

    lady_row = session.execute(
        sa_text(
            "SELECT ship_id, COALESCE(NULLIF(custom_name, ''), ships.name, ''), "
            "EXTRACT(EPOCH FROM create_time)::bigint "
            "FROM owned_ships LEFT JOIN ships ON ships.template_id = owned_ships.ship_id "
            "WHERE owner_id = :cid AND deleted_at IS NULL AND propose = TRUE "
            "ORDER BY create_time, id LIMIT 1"
        ),
        {"cid": commander_id},
    ).fetchone()
    if lady_row:
        result["first_lady_id"] = int(lady_row[0])
        result["first_lady_name"] = lady_row[1] or ""
        result["first_lady_time"] = int(lady_row[2]) if lady_row[2] else 0

    skin_count = session.execute(
        select(func.count()).select_from(OwnedSkin).where(
            OwnedSkin.commander_id == commander_id,
            sa_text("(expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)"),
        )
    ).scalar()
    if skin_count:
        result["skin_num"] = skin_count

    skin_ship_row = session.execute(
        sa_text(
            "SELECT COUNT(DISTINCT owned_ships.id) "
            "FROM owned_ships "
            "JOIN skins ON skins.ship_group = (owned_ships.ship_id / 10) "
            "JOIN owned_skins ON owned_skins.commander_id = owned_ships.owner_id "
            "AND owned_skins.skin_id = skins.id "
            "AND (owned_skins.expires_at IS NULL OR owned_skins.expires_at > CURRENT_TIMESTAMP) "
            "WHERE owned_ships.owner_id = :cid AND owned_ships.deleted_at IS NULL"
        ),
        {"cid": commander_id},
    ).scalar()
    if skin_ship_row:
        result["skin_ship_num"] = int(skin_ship_row)

    return result

get_player_profile_stats = _sync_get_player_profile_stats
get_commander_social_profiles_by_ids = _sync_get_commander_social_profiles_by_ids
list_friend_profiles = _sync_list_friend_profiles
