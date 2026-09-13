import asyncio
import json
import time
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def _list_dorm_ships_snapshot(commander_id: int) -> list:
    from src.db.store import get_default_store

    store = get_default_store()
    if store is None:
        return []

    try:
        rows = store.fetch(
            "SELECT id, ship_id, state, skin_id, intimacy, state_info3, state_info4 FROM owned_ships WHERE owner_id = $1 AND deleted_at IS NULL AND (state = 5 OR state = 2)",
            int(commander_id),
        )
        result = [{"id": r[0], "tid": r[1], "state": r[2], "skin_id": r[3], "intimacy": r[4], "state_info3": r[5], "state_info4": r[6], "floor": 1 if r[2] == 5 else 2} for r in rows]
        from src.logger.logger import log_event, LOG_LEVEL_WARN
        log_event("Dorm", "DormShips", f"_list_dorm_ships_snapshot({commander_id}): found {len(result)} ships: {[r['id'] for r in result]}", LOG_LEVEL_WARN)
        return result
    except Exception as e:
        from src.logger.logger import log_event, LOG_LEVEL_ERROR
        log_event("Dorm", "DormShipsError", f"_list_dorm_ships_snapshot({commander_id}) error: {e}", LOG_LEVEL_ERROR)
        return []


def _load_dorm_snapshot(commander_id: int, dorm_name: str) -> Optional[dict]:
    from src.orm.commander_furniture import list_commander_furniture as _list_furn
    from src.orm.commander_dorm_state import get_or_create_commander_dorm_state as _get_state
    from src.orm.commander_dorm_floor_layout import list_commander_dorm_floor_layouts as _list_layouts
    from src.db.store import NotFoundError

    furnitures_raw = _list_furn(commander_id)
    state = _get_state(commander_id)
    state_dict = {c.name: getattr(state, c.name) for c in state.__table__.columns}
    template = {}
    try:
        from .dorm_simulation import load_dorm_level_template
        loaded = load_dorm_level_template(max(state_dict.get("level", 1), 1))
        if loaded is not None:
            template = loaded
    except NotFoundError:
        pass
    layouts_raw = _list_layouts(commander_id)
    ships = _list_dorm_ships_snapshot(commander_id)

    furnitures = []
    for f in furnitures_raw:
        furnitures.append({
            "furniture_id": f.furniture_id,
            "count": f.count,
            "get_time": f.get_time,
        })

    layouts = []
    for l in layouts_raw:
        layouts.append({
            "floor": l.floor,
            "furniture_put_list": l.furniture_put_list,
        })

    return {
        "state": state_dict,
        "template": template,
        "dorm_name": dorm_name,
        "furnitures": furnitures,
        "layouts": layouts,
        "ships": ships,
    }


def _build_dorm_furniture_info_list(response, furnitures: list):
    if not furnitures:
        return
    for f in furnitures:
        entry = protobuf.FURNITUREINFO(
            id=f.get("furniture_id", 0),
            count=f.get("count", 0),
            get_time=f.get("get_time", 0),
        )
        response.furniture_id_list.append(entry)


def _build_dorm_floor_put_list(response, layouts: list):
    if not layouts:
        return
    for layout in layouts:
        floor = layout.get("floor", 0)
        if floor == 0 or floor > 3:
            continue
        raw = layout.get("furniture_put_list", [])
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8", errors="replace")
        if isinstance(raw, str):
            raw = json.loads(raw)
        floor_info = protobuf.FURFLOORPUTINFO(floor=floor)
        for entry in raw:
            f_info = protobuf.FURNITUREPUTINFO(
                id=entry.get("id", ""),
                x=entry.get("x", 0),
                y=entry.get("y", 0),
                dir=entry.get("dir", 0),
                parent=entry.get("parent", 0),
                shipId=0,
            )
            for c in entry.get("child", []):
                child = protobuf.CHILDINFO(id=c.get("id", ""), x=c.get("x", 0), y=c.get("y", 0))
                f_info.child.append(child)
            floor_info.furniture_put_list.append(f_info)
        response.furniture_put_list.append(floor_info)


def _build_dorm_data_response(snapshot: dict) -> protobuf.SC_19001:
    state = snapshot["state"]
    food_val = state.get("food", 0)
    # food_max_increase is the gem-purchased extra capacity only; the client
    # adds the template capacity itself (Dorm.GetCapcity = capacity + food_max_increase).
    max_increase = state.get("food_max_increase", 0) or 0
    response = protobuf.SC_19001(
        lv=max(state.get("level", 0), 1),
        food=food_val,
        food_max_increase=max_increase,
        food_max_increase_count=state.get("food_max_increase_count", 0),
        floor_num=max(min(state.get("floor_num", 1), 3), 1),
        exp_pos=max(state.get("exp_pos", 0), 2),
        next_timestamp=state.get("next_timestamp", 0),
        load_exp=state.get("load_exp", 0),
        load_food=state.get("load_food", 0),
        load_time=state.get("load_time", 0),
        name=snapshot["dorm_name"],
    )

    if snapshot["ships"]:
        for s in snapshot["ships"]:
            dship = protobuf.SHIPINFO_IN_DORM(
                id=s["id"],
                tid=s["tid"],
                floor=s.get("floor", 1),
                pop_icon=int(s.get("state_info4", 0) or 0),
                pop_intimacy=int(s.get("state_info3", 0) or 0),
                skin_id=s.get("skin_id", 0),
            )
            response.ship_list.append(dship)

    _build_dorm_furniture_info_list(response, snapshot["furnitures"])
    _build_dorm_floor_put_list(response, snapshot["layouts"])
    return response


async def handle_dorm_data(
    _buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    commander_id = client.commander.commander_id

    # Roll completed offline pop windows (hearts/coins) BEFORE building
    # SC_19001, so the login dorm state already carries fresh collectable
    # pops: the client's Backyard red dot and per-ship collect bubbles read
    # from this packet at main-scene init, and the next dorm tick is up to
    # 30 minutes away (CS_19009 poll) or gated behind entering the dorm
    # (CS_19026). Exp/food are deliberately NOT settled here -- load_time is
    # kept so the CS_19026 "while you were away" popup still shows the real
    # offline window.
    try:
        from .dorm_simulation import settle_dorm_pops_at_login
        await settle_dorm_pops_at_login(commander_id, int(time.time()))
    except Exception as e:
        from src.logger.logger import log_event, LOG_LEVEL_ERROR
        log_event("Dorm", "LoginPopSettle", f"failed to settle offline dorm pops: {e}", LOG_LEVEL_ERROR)

    # SC_19001 must NOT tick/settle the dorm: the client drives settlement
    # through CS_19026 (backyardrequestshipexpcommand.lua). It reads
    # load_time as the start of the settlement window and shows
    # `serverTime - load_time` in the settlement popup. If we tick here,
    # load_time is set to now and all food is consumed before the client
    # ever requests the settlement -> popup shows ~0s and 0 food.
    snapshot = _load_dorm_snapshot(commander_id, client.commander.dorm_name)
    if snapshot is None:
        return 0, 19001, Exception("failed to load dorm snapshot")

    try:
        response = _build_dorm_data_response(snapshot)
    except Exception as e:
        return 0, 19001, e

    data = response.SerializeToString()
    from src.connection.server import generate_packet_header
    header = generate_packet_header(19001, data, client.packet_index)
    client.write_to_buffer(header + data)
    # Server-authoritative task progress: entering the dorm with ships training/resting advances sub_type 62
    try:
        from src.answer.task_handlers import schedule_emit, schedule_possession_sync
        if snapshot.get("ships"):
            schedule_emit(client, 62, 0, 1)
            schedule_possession_sync(client)
    except Exception:
        pass
    return 0, 19001, None


def handle_visit_backyard(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    PACKET_ID = 19102

    try:
        payload = json.loads(buffer.decode("utf-8", errors="replace"))
    except Exception as e:
        return 0, PACKET_ID, e

    target_commander_id = payload.get("user_id", 0)

    from src.db.store import NotFoundError
    from src.db.store import get_default_store

    try:
        store_lookup = get_default_store()
        row = store_lookup.fetchrow(
            "SELECT commander_id, name, dorm_name FROM commanders WHERE commander_id = $1 AND deleted_at IS NULL",
            target_commander_id,
        )
        target_commander = {"commander_id": row[0], "name": row[1], "dorm_name": row[2]} if row else None
    except NotFoundError:
        asyncio.create_task(client.send_message(PACKET_ID, protobuf.SC_19102(
            lv=0, food=0, food_max_increase=0,
            food_max_increase_count=0, floor_num=0,
            exp_pos=0, name="",
        )))
        return 0, PACKET_ID, None
    except Exception as e:
        return 0, PACKET_ID, e

    snapshot = _load_dorm_snapshot(target_commander_id, target_commander.get("dorm_name", ""))
    if snapshot is None:
        return 0, PACKET_ID, Exception("failed to load dorm snapshot")

    state = snapshot["state"]
    response = protobuf.SC_19102(
        lv=state.get("level", 0),
        food=state.get("food", 0),
        food_max_increase=state.get("food_max_increase", 0) or 0,
        food_max_increase_count=state.get("food_max_increase_count", 0),
        floor_num=min(state.get("floor_num", 0), 3),
        exp_pos=state.get("exp_pos", 0),
        name=target_commander.get("name", ""),
    )

    if snapshot["ships"]:
        for s in snapshot["ships"]:
            ship = protobuf.SHIPINFO_IN_DORM(
                id=s["id"],
                tid=s["tid"],
                floor=s.get("floor", 1),
                pop_icon=0,
                pop_intimacy=0,
                skin_id=s.get("skin_id", 0),
            )
            response.ship_list.append(ship)

    _build_dorm_furniture_info_list(response, snapshot["furnitures"])
    _build_dorm_floor_put_list(response, snapshot["layouts"])

    asyncio.create_task(client.send_message(PACKET_ID, response))
    return 0, PACKET_ID, None
