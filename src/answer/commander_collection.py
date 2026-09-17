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

    for gid in _load_transform_list(commander_id):
        response.transform_list.append(gid)

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


_TRANS_MAPS: Optional[tuple[set[int], dict[int, int], dict[int, int]]] = None


def _get_trans_mappings() -> tuple[set[int], dict[int, int], dict[int, int]]:
    """Returns (valid_groups, skin_to_group, node_to_group) for retrofit data."""
    global _TRANS_MAPS
    if _TRANS_MAPS is not None:
        return _TRANS_MAPS

    import json
    import os
    from src.misc import DATA_DIR

    valid_groups: set[int] = set()
    skin_to_group: dict[int, int] = {}
    node_to_group: dict[int, int] = {}

    try:
        path = os.path.join(DATA_DIR, "EN", "ShareCfg", "ship_data_trans.json")
        with open(path, "r", encoding="utf-8") as f:
            trans_data = json.load(f)
        items = trans_data if isinstance(trans_data, list) else trans_data.values()
        for item in items:
            gid = item.get("group_id")
            skid = item.get("skin_id")
            if gid and skid:
                gid_int = int(gid)
                skid_int = int(skid)
                valid_groups.add(gid_int)
                skin_to_group[skid_int] = gid_int
    except Exception:
        pass

    try:
        path = os.path.join(DATA_DIR, "EN", "ShareCfg", "transform_data_template.json")
        with open(path, "r", encoding="utf-8") as f:
            node_data = json.load(f)
        items = node_data if isinstance(node_data, list) else node_data.values()
        for node in items:
            skid = node.get("skin_id")
            if skid and int(skid) in skin_to_group:
                node_to_group[int(node["id"])] = skin_to_group[int(skid)]
    except Exception:
        pass

    _TRANS_MAPS = (valid_groups, skin_to_group, node_to_group)
    return _TRANS_MAPS


def _load_transform_list(cid: int) -> list[int]:
    try:
        from src.db.store import get_default_store
        store = get_default_store()
        if store is None:
            return []

        valid_groups, skin_to_group, node_to_group = _get_trans_mappings()
        if not valid_groups:
            return []

        retrofitted: set[int] = set()

        # 1. From owned_skins (modernization awards the unique retrofit skin)
        skin_rows = store.fetch(
            "SELECT skin_id FROM owned_skins WHERE commander_id = $1", cid
        )
        for r in skin_rows:
            gid = skin_to_group.get(r["skin_id"])
            if gid:
                retrofitted.add(gid)

        # 2. From owned_ships (active ships wearing or initialized with retrofit skin)
        ship_rows = store.fetch(
            "SELECT skin_id FROM owned_ships WHERE owner_id = $1", cid
        )
        for r in ship_rows:
            gid = skin_to_group.get(r["skin_id"])
            if gid:
                retrofitted.add(gid)

        # 3. From owned_ship_transforms (completed modernization node)
        trans_rows = store.fetch(
            "SELECT transform_id, level FROM owned_ship_transforms WHERE owner_id = $1", cid
        )
        for r in trans_rows:
            if r["level"] >= 1:
                gid = node_to_group.get(r["transform_id"])
                if gid:
                    retrofitted.add(gid)

        # Invariant: ONLY ship groups that exist in pg.ship_data_trans can EVER be sent!
        return sorted(list(retrofitted.intersection(valid_groups)))
    except Exception:
        return []


def _load_ship_stats(cid: int) -> list[dict]:
    try:
        from src.db.store import get_default_store
        store = get_default_store()
        if store is None:
            return []
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
        result = []
        for r in rows:
            gid = int(r["group_id"])
            intimacy_max = int(r["max_intimacy"])
            if 0 < intimacy_max <= 100:
                intimacy_max *= 100
            elif intimacy_max == 0:
                intimacy_max = 5000

            star = int(r["max_star"])
            heart_count = int(r["heart_count"])
            heart_flag = int(r["heart_flag"])

            result.append({
                "id": gid,
                "star": star,
                "heart_flag": heart_flag,
                "heart_count": heart_count,
                "marry_flag": int(r["marry_flag"]),
                "intimacy_max": intimacy_max,
                "lv_max": int(r["max_level"]),
            })
        return result
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
