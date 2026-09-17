import asyncio
import datetime
import time
from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.protobuf import protobuf
from src.config.regions import MONDAY_0CLOCK_TIMESTAMPS
from src.orm.owned_ship import list_ships_by_ids
from src.region.region import current as get_region
from src.logger.logger import log_event, LOG_LEVEL_ERROR, LOG_LEVEL_INFO
from src.orm.build import build_consume, list_builds_by_builder


def handle_send_player_ship_count(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    region = get_region()
    now_unix = int(time.time())
    ship_count = len(getattr(client.commander, "ships", []) or getattr(client.commander, "owned_ships_map", {}) or [])
    response = protobuf.SC_11002()
    response.timestamp = now_unix
    response.monday_0oclock_timestamp = MONDAY_0CLOCK_TIMESTAMPS.get(region, 0)
    response.ship_count = ship_count
    client.server.join_room(client.commander.room_id, client)
    data = response.SerializeToString()
    header = generate_packet_header(11002, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 11002, None


def handle_get_ship_count(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_11800()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 11801, e

    response = protobuf.SC_11801()
    response.ship_count = len(getattr(client.commander, "ships", []) or getattr(client.commander, "owned_ships_map", {}) or [])
    asyncio.create_task(client.send_message(11801, response))
    return 0, 11801, None


def handle_get_ship_discuss(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_17101()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 17102, e

    from src.answer.evaluate_ship import _get_ship_discuss_state, _count_ship_hearts

    group_id = payload.ship_group_id
    state = _get_ship_discuss_state(group_id)

    response = protobuf.SC_17102()
    discuss = protobuf.SHIP_DISCUSS_INFO()
    discuss.ship_group_id = group_id
    discuss.discuss_count = len(state.discuss_list)
    discuss.heart_count = _count_ship_hearts(group_id)
    discuss.daily_discuss_count = state.daily_discuss_count
    for item in state.discuss_list:
        discuss.discuss_list.append(protobuf.DISCUSS_INFO(
            id=item["id"],
            nick_name=item["nick_name"],
            context=item["context"],
            good_count=item["good_count"],
            bad_count=item["bad_count"],
        ))
    response.ship_discuss.CopyFrom(discuss)
    asyncio.create_task(client.send_message(17102, response))
    return 0, 17102, None


def handle_get_ship(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_12025()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 12025, e

    commander = client.commander
    commander_id = commander.commander_id
    pos_list = sorted(payload.pos_list)

    response = protobuf.SC_12026()
    response.result = 0

    if not pos_list:
        asyncio.create_task(client.send_message(12026, response))
        return 0, 12026, None

    builds = sorted(list_builds_by_builder(commander_id), key=lambda b: b["id"])
    log_event("GetShip", "Builds", f"found {len(builds)} builds for cid={commander_id}", LOG_LEVEL_INFO)
    if not builds:
        asyncio.create_task(client.send_message(12026, response))
        return 0, 12026, None

    # pos is the 1-based index into the canonical (ORDER BY id) worklist the
    # client received in SC_12024 / SC_12044 - same order here.
    now = datetime.datetime.now(datetime.timezone.utc)
    target_builds = []
    for pos in sorted(pos_list):
        idx = int(pos) - 1
        if idx < 0 or idx >= len(builds):
            continue
        b = builds[idx]
        ft = b["finishes_at"]
        if ft is None:
            continue
        if ft.tzinfo is None:
            ft = ft.replace(tzinfo=datetime.timezone.utc)
        if ft > now:
            # never consume an in-progress build (would skip its timer)
            continue
        target_builds.append(b)

    owned_ship_ids = []
    consumed_build_ids = set()
    for b in target_builds:
        try:
            result = build_consume(b["id"], b["ship_id"], commander_id)
            consumed_build_ids.add(b["id"])
            if result and result["owned_ship_id"] is not None:
                owned_ship_ids.append(result["owned_ship_id"])
        except Exception as e:
            log_event("GetShip", "ConsumeError", f"build_consume failed: {e}", LOG_LEVEL_ERROR)
            response.result = 1
            asyncio.create_task(client.send_message(12026, response))
            return 0, 12026, None

    # keep the live worklist cache in sync so SC_12024/SC_12044 don't resurrect collected builds
    bl = getattr(commander, "builds", None)
    if bl is not None and consumed_build_ids:
        commander.builds = [w for w in bl if w.get("id") not in consumed_build_ids]

    try:
        rows = list_ships_by_ids(commander_id, owned_ship_ids)
    except Exception as e:
        return 0, 12025, e

    # Update in-memory cache so subsequent operations (e.g., locking) find the new ships
    for row in rows:
        sid = row[0]
        commander.owned_ships_map[sid] = {
            "id": row[0],
            "owner_id": commander_id,
            "ship_id": row[1],
            "level": row[2],
            "energy": row[4],
            "state": row[15],
            "state_info1": row[16],
            "intimacy": row[5],
            "exp": row[3],
            "surplus_exp": 0,
            "max_level": row[7],
            "is_locked": row[8],
            "propose": row[9],
            "create_time": row[12],
        }

    ship_group_ids = [r[1] for r in rows]

    # SHIPINFO snapshot building lives in ONE place
    # (src/answer/shipinfo/builder.py) — tuple rows from list_ships_by_ids
    # are supported directly.
    from src.answer.shipinfo.builder import build_ship_infos
    for s in build_ship_infos(rows, commander_id):
        response.ship_list.append(s)

    asyncio.create_task(client.send_message(12026, response))
    return 0, 12026, None
