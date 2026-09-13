import asyncio
import json
from typing import Optional, Set

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.db.store import get_default_store
from src.orm.config_entry import list_config_entries
from src.protobuf import protobuf
from src.logger.logger import log_event, LOG_LEVEL_DEBUG

from .build_rates import draw_ship as _draw_ship
from .build_logic import build_cost_create_id as _build_cost_create_id, build_info_from_row as _build_info_from_row
from .helpers import plan_builds_sync

CATEGORY = "ShareCfg/activity_ship_create.json"
COIN_RESOURCE_ID = 1


def _all_pools() -> list:
    entries = list_config_entries(CATEGORY)
    pools = []
    for e in entries:
        data = json.loads(e.data) if isinstance(e.data, str) else e.data
        if isinstance(data, dict) and "pickup_list" in data:
            pools.append(data)
    return pools


def get_wishing_well_activity_ids() -> set:
    return {p["activity_id"] for p in _all_pools() if "activity_id" in p}


def _pools_for_activity(activity_id) -> list:
    return [p for p in _all_pools() if p.get("activity_id") == activity_id]


def _pool_by_id(activity_id, pool_id) -> Optional[dict]:
    for p in _pools_for_activity(activity_id):
        if p.get("id") == pool_id:
            return p
    return None


def _load_focus(commander_id, activity_id) -> tuple:
    store = get_default_store()
    if store is None:
        return (0, 0, 0)
    row = store.fetchrow(
        "SELECT data1, data2, data3 FROM activity_store_states "
        "WHERE commander_id=$1 AND activity_id=$2",
        commander_id, activity_id,
    )
    if not row:
        return (0, 0, 0)
    return (row[0] or 0, row[1] or 0, row[2] or 0)


def _save_focus(commander_id, activity_id, pool_id, f1, f2):
    store = get_default_store()
    if store is None:
        return
    ships = [s for s in (f1, f2) if s]
    store.execute(
        "INSERT INTO activity_store_states "
        "(commander_id, activity_id, data1, data2, data3, data1_list, str_data1, created_at, updated_at) "
        "VALUES ($1, $2, $3, $4, $5, $6, '', NOW(), NOW()) "
        "ON CONFLICT (commander_id, activity_id) DO UPDATE SET "
        "data1=$3, data2=$4, data3=$5, data1_list=$6, updated_at=NOW()",
        commander_id, activity_id, pool_id, f1, f2, json.dumps(ships),
    )


def _has_enough_resource(commander_id, resource_id, amount) -> bool:
    store = get_default_store()
    row = store.fetchrow(
        "SELECT amount FROM owned_resources WHERE commander_id=$1 AND resource_id=$2",
        commander_id, resource_id,
    )
    return (row[0] if row else 0) >= amount


def _consume_resource(commander_id, resource_id, amount):
    store = get_default_store()
    store.execute(
        "INSERT INTO owned_resources (commander_id, resource_id, amount) VALUES ($1,$2,$3) "
        "ON CONFLICT (commander_id, resource_id) DO UPDATE SET amount = owned_resources.amount - $3",
        commander_id, resource_id, amount,
    )


def _wishing_well_ships(pool: dict) -> list:
    """All (template_id, rarity_id) pairs in the pool's pickup_list."""
    picks = pool.get("pickup_list") or []
    if not picks:
        return []
    ph = ",".join("$%d" % (i + 1) for i in range(len(picks)))
    store = get_default_store()
    rows = store.fetch(
        "SELECT template_id, rarity_id FROM ships WHERE template_id IN (%s)" % ph,
        *picks,
    )
    return [(r["template_id"], r["rarity_id"]) for r in rows]


def _draw_wishing_well_ship(pool: dict, focus: Set[int]) -> Optional[int]:
    ships = _wishing_well_ships(pool)
    if not ships:
        return None
    # Wishing Well uses Event-construction rates: focus (rate-up) ships get a fixed
    # boost share, the rest share the remainder of each rarity's base rate.
    return _draw_ship(ships, focus=focus, mode="event")


def _no_op(client: Client) -> tuple:
    response = protobuf.SC_11203(result=0)
    asyncio.create_task(client.send_message(11203, response))
    return 0, 11203, None


def _varint(n: int) -> bytes:
    n &= 0xFFFFFFFF
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def _build_focus_response_bytes(pool_id: int, ships: list) -> bytes:
    """SC_11203 with result=0 plus data1 (selected pool) and data1_list (selected
    ship template ids). The client's PrayPool UI reads getData1()/getData1List()
    which are NOT present in the generated SC_11203 descriptor, so we append those
    fields manually on the wire (fields 9 / 10)."""
    msg = protobuf.SC_11203()
    msg.result = 0
    body = bytearray(msg.SerializeToString())
    body += bytes([0x48]) + _varint(pool_id)  # field 9: data1 (int32)
    for s in ships:
        if s:
            body += bytes([0x50]) + _varint(s)  # field 10: data1_list (repeated int32)
    return bytes(body)


def handle_wishing_well(payload, client: Client) -> tuple[int, int, Optional[Exception]]:
    activity_id = payload.activity_id
    cmd = payload.cmd
    arg1 = payload.arg1
    arg2 = payload.arg2
    arg3 = payload.arg3

    pools = _pools_for_activity(activity_id)
    log_event("WishingWell", "Debug",
              f"activity_id={activity_id} cmd={cmd} arg1={arg1} arg2={arg2} arg3={arg3} pools={[p.get('id') for p in pools]}",
              LOG_LEVEL_DEBUG)
    if not pools:
        return _no_op(client)

    commander_id = client.commander.commander_id
    store = get_default_store()
    if store is None:
        return _no_op(client)

    if cmd == 2:
        # cmd=2 is used for two things by the client:
        #  - selecting the focus ships: arg1 = pool, arg2/arg3 = ship ids. Persist
        #    the selection and return SC_11203 with data1/data1_list so the success
        #    view can populate them.
        #  - "BEGIN BUILDING" (START_BUILD_SHIP_EVENT): arg1 = count, arg2=arg3=0.
        #    Create that many timed constructions in the normal build queue.
        if arg2 or arg3:
            pool = _pool_by_id(activity_id, arg1)
            if pool is None:
                return _no_op(client)
            # Save the client's selected ship ids verbatim (see cmd==1 note):
            # they are guaranteed valid ship ids; filtering against the server's
            # pickup_list was wrong and produced an empty data1_list.
            focus = [s for s in (arg2, arg3) if s]
            focus = list(dict.fromkeys(focus))
            _save_focus(commander_id, activity_id, arg1,
                        focus[0] if len(focus) > 0 else 0,
                        focus[1] if len(focus) > 1 else 0)
            body = _build_focus_response_bytes(arg1, focus)
            header = generate_packet_header(11203, body, client.packet_index)
            client.write_to_buffer(header + body)
            return len(body), 11203, None
        # BEGIN BUILDING -> real construction(s).
        return _do_pray_build(client, commander_id, activity_id, pools, arg1)

    if cmd == 1:
        # CLICK_BUILD_BTN: confirm the selection (the 2 focus ships the client
        # picked from its own pickup_list) and open the success view.
        pool = _pool_by_id(activity_id, arg1) if arg1 else None
        if pool is None:
            f_pool, f1, f2 = _load_focus(commander_id, activity_id)
            pool = _pool_by_id(activity_id, f_pool) or pools[0]
        # Save the selected ship template ids verbatim. They are guaranteed valid
        # ship ids (the client only lists real ships), so PrayPoolSuccessView can
        # render them. Filtering against the server's pickup_list was WRONG: the
        # client's bundled pool list can differ, which dropped the selection and
        # left an empty data1_list -- and the success view requires exactly 2
        # selected ships, so it crashed (attempt to index nil). Rate-up still
        # works because _draw_wishing_well_ship only applies focus to ships that
        # are actually present in the pool.
        focus = [s for s in (arg2, arg3) if s]
        if not focus:
            _, f1, f2 = _load_focus(commander_id, activity_id)
            focus = [s for s in (f1, f2) if s]
        focus = list(dict.fromkeys(focus))
        if focus:
            _save_focus(commander_id, activity_id, pool.get("id", 1),
                        focus[0], focus[1] if len(focus) > 1 else 0)
        response = protobuf.SC_11203(result=0)
        asyncio.create_task(client.send_message(11203, response))
        return 0, 11203, None

    return _no_op(client)


def _do_pray_build(client, commander_id, activity_id, pools, count):
    from datetime import datetime, timezone
    from src.protobuf import protobuf as _pb
    from src.orm.item import has_enough_item as _hei, consume_item as _ci
    from src.consts.build import MAX_BUILD_WORK_COUNT

    saved_pool, f1, f2 = _load_focus(commander_id, activity_id)
    pool = _pool_by_id(activity_id, saved_pool) or pools[0]
    if pool is None:
        return _no_op(client)
    pickup = set(pool.get("pickup_list") or [])
    focus = [s for s in (f1, f2) if s and s in pickup]
    focus = list(dict.fromkeys(focus))
    focus_set = set(focus)

    count = max(1, int(count or 1))
    # Count only in-progress (not-yet-finished) builds against the slot cap, so a
    # finished-but-not-yet-collected build does not permanently block new builds.
    now_utc = datetime.now(timezone.utc)
    cur = 0
    for b in (getattr(client.commander, "builds", []) or []):
        fa = b.get("finishes_at")
        if fa is None:
            cur += 1
            continue
        if fa.tzinfo is None:
            fa = fa.replace(tzinfo=timezone.utc)
        if fa > now_utc:
            cur += 1
    count = min(count, max(0, MAX_BUILD_WORK_COUNT - cur))
    if count <= 0:
        response = _pb.SC_11203(result=2)
        asyncio.create_task(client.send_message(11203, response))
        return 0, 11203, None

    create_id = int(pool.get("create_id") or 0)
    gold_cost, cube_cost = _build_cost_create_id(create_id)
    gold_cost *= count
    cube_cost *= count
    pool_id = pool.get("id", 1)

    if not _has_enough_resource(commander_id, 1, gold_cost):
        response = _pb.SC_11203(result=2)
        asyncio.create_task(client.send_message(11203, response))
        return 0, 11203, None
    if not _hei(commander_id, 20001, cube_cost):
        response = _pb.SC_11203(result=3)
        asyncio.create_task(client.send_message(11203, response))
        return 0, 11203, None

    drawn = []
    for _ in range(count):
        ship = _draw_wishing_well_ship(pool, focus_set)
        if ship is None:
            response = _pb.SC_11203(result=1)
            asyncio.create_task(client.send_message(11203, response))
            return 0, 11203, None
        drawn.append(ship)

    # Route through the shared 4-slot dock queue: only 4 constructions tick at
    # once, the rest wait INACTIVE until a slot frees.
    all_rows, new_rows = plan_builds_sync(
        commander_id,
        [{"ship_id": s, "pool_id": pool_id} for s in drawn],
        now_utc,
    )
    try:
        client.commander.builds = all_rows
    except Exception:
        pass
    build_infos = [_build_info_from_row(row, now_utc) for row in new_rows]

    _consume_resource(commander_id, 1, gold_cost)
    _ci(commander_id, 20001, cube_cost)

    # The client (ActivityOperationCommand.updateActivityData, BUILDSHIP_1 branch)
    # adds builds from SC_11203.build (field 3), iterating uv2.build. So the build
    # list MUST go here -- a separate SC_12003 push is ignored (no on(12003) listener).
    response = _pb.SC_11203(result=0)
    response.build.extend(build_infos)
    asyncio.create_task(client.send_message(11203, response))
    return 0, 11203, None
