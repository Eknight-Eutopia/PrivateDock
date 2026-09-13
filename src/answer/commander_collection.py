from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.orm.commander_trophy_progress import list_commander_trophy_progress
from src.orm import list_commander_storeup_awards


def handle_commander_collection(
    _buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    from src.protobuf import protobuf
    commander_id = client.commander.commander_id

    response = protobuf.SC_17001(daily_discuss=0)

    for stat in _load_ship_stats(commander_id):
        si = protobuf.SHIP_STATISTICS_INFO(
            id=stat["id"], star=stat["star"], heart_flag=stat["heart_flag"],
            heart_count=stat["heart_count"], marry_flag=stat["marry_flag"],
            intimacy_max=stat["intimacy_max"], lv_max=stat["lv_max"],
        )
        response.ship_info_list.append(si)

    for prog in _load_trophy_progress(commander_id):
        ai = protobuf.ACHIEVEMENT_INFO(id=prog["id"], progress=prog["progress"], timestamp=prog["timestamp"])
        response.progress_list.append(ai)

    try:
        storeup_rows = list_commander_storeup_awards(commander_id)
        for r in storeup_rows:
            last_index = r[1]
            if last_index != 0:
                sa = protobuf.SHIP_STATISTICS_AWARD(id=r[0], award_index=[last_index])
                response.ship_award_list.append(sa)
    except Exception:
        pass

    data = response.SerializeToString()
    header = generate_packet_header(17001, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 17001, None


def _load_ship_stats(cid: int) -> list[dict]:
    try:
        from src.db.store import get_default_store
        store = get_default_store()
        rows = store.fetch("""
            SELECT
                stats.group_id,
                stats.max_star,
                stats.max_intimacy,
                stats.max_level,
                stats.marry_flag,
                (SELECT COUNT(*) FROM likes WHERE group_id = stats.group_id AND liker_id = $1) AS heart_flag,
                (SELECT COUNT(*) FROM likes WHERE group_id = stats.group_id) AS heart_count
            FROM (
                SELECT
                    owned_ships.ship_id / 10 AS group_id,
                    MAX(ships.star) AS max_star,
                    MAX(intimacy) AS max_intimacy,
                    MAX(level) AS max_level,
                    MAX(CASE WHEN propose THEN 1 ELSE 0 END) AS marry_flag
                FROM owned_ships
                INNER JOIN ships ON owned_ships.ship_id = ships.template_id
                WHERE owner_id = $2
                GROUP BY owned_ships.ship_id / 10
            ) AS stats
        """, cid, cid)
        return [
            {
                "id": r["group_id"],
                "star": r["max_star"],
                "heart_flag": r["heart_flag"],
                "heart_count": r["heart_count"],
                "marry_flag": r["marry_flag"],
                "intimacy_max": r["max_intimacy"],
                "lv_max": r["max_level"],
            }
            for r in rows
        ]
    except Exception:
        return []


def _load_trophy_progress(cid: int) -> list[dict]:
    try:
        rows = list_commander_trophy_progress(cid)
        return [
            {
                "id": r[1],
                "progress": r[2],
                "timestamp": r[3] or 0,
            }
            for r in rows
        ]
    except Exception:
        return []
