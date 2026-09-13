import json
import time
from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.protobuf import protobuf
from src.orm import event_collection as ec

COLLECTION_TEMPLATE_CATEGORY = "ShareCfg/collection_template.json"


def _fail(client, reason):
    from src.logger.logger import log_event, LOG_LEVEL_WARN
    log_event("Commission", "DispatchFail", f"reason={reason}", LOG_LEVEL_WARN)
    msg = protobuf.SC_13004(result=1)
    data = msg.SerializeToString()
    client.write_to_buffer(generate_packet_header(13004, data, client.packet_index) + data)


def _max_commission_slots(client) -> int:
    # Per the Azur Lane commission rules: the first slot unlocks at commander
    # level 10. Each additional slot (up to four) unlocks after the player has
    # cleared the 4th stage of the main campaign chapters 1 / 2 / 3 (1-4, 2-4,
    # 3-4). A chapter_progress row with progress > 0 means the chapter has been
    # cleared at least once, which requires its stage 4 to have been beaten.
    level = getattr(client.commander, "level", 0)
    if level < 10:
        return 0
    from src.orm.chapter import get_chapter_progress_sync
    cid = client.commander.commander_id
    slots = 1
    for chapter_id in (101, 201, 301):
        prog = get_chapter_progress_sync(cid, chapter_id)
        if prog is not None and prog.progress > 0:
            slots += 1
    return slots


def _do_start_collection(client: Client, row_id: int, ship_ids) -> Optional[Exception]:
    from src.logger.logger import log_event, LOG_LEVEL_WARN
    log_event("Commission", "DispatchStart", f"cid={client.commander.commander_id} row_id={row_id} ship_ids={list(ship_ids)} owned_keys={list(client.commander.owned_ships_map.keys())[:10]}", LOG_LEVEL_WARN)
    if row_id == 0:
        _fail(client, "zero_id")
        return None

    from src.orm.event_collection import (
        get_commission_by_template_sync,
        list_commissions_sync,
        update_commission_sync,
    )

    # The client sends back the *template* id it received on the board, so we
    # resolve the player's commission row by (commander_id, commission_id).
    row = get_commission_by_template_sync(client.commander.commander_id, row_id, ec.STATE_AVAILABLE)
    if row is None:
        _fail(client, "no_instance")
        return None

    template = _load_collection_template(row.commission_id)
    if template is None:
        _fail(client, "no_template")
        return None
    if isinstance(template, Exception):
        return template

    ship_ids = [int(s) for s in ship_ids]
    if not ship_ids:
        _fail(client, "empty_ships")
        return None

    # The client enforces ship class / level restrictions in its own UI before
    # dispatching; the official server trusts that selection. Our
    # collection_template data can drift from the client's version, so we do not
    # re-validate class/level here (that would reject valid client selections).
    # We do require a non-empty, owned selection and the minimum ship count.
    tpl_to_owned = {}
    for _oid, _od in client.commander.owned_ships_map.items():
        tpl_to_owned.setdefault(int(_od.get("ship_id", 0) or 0), _oid)

    resolved_ship_ids = []
    for ship_id in ship_ids:
        owned = client.commander.owned_ships_map.get(ship_id)
        if owned is None:
            alt = tpl_to_owned.get(ship_id)
            if alt is not None:
                ship_id = alt
                owned = client.commander.owned_ships_map.get(ship_id)
        if owned is None:
            _fail(client, f"ship_not_owned id={ship_id}")
            return None
        resolved_ship_ids.append(ship_id)

    # Minimum ship count required by the commission. This used to be checked at
    # collect time, but a ship can be retired/sold mid-commission, which made
    # collection fail and lose the reward. Validated here at dispatch instead so
    # any rejection happens up front (recoverable) rather than at payout.
    ship_num = template.get("ship_num", 0)
    if ship_num > 0 and len(resolved_ship_ids) < ship_num:
        _fail(client, "insufficient_ships")
        return None

    oil = template.get("oil", 0)
    over_time = template.get("over_time", 0)
    collect_time = template.get("collect_time", 0)

    if oil > 0 and not client.commander.has_enough_resource(2, oil):
        _fail(client, "no_oil")
        return None

    server_time = int(time.time())
    if over_time > 0 and server_time >= over_time:
        _fail(client, "over_time")
        return None

    # Concurrent *in-progress* commissions: 1 slot at Lv.10, +1 each for
    # clearing the 4th stage of campaign chapters 1 / 2 / 3 (see
    # _max_commission_slots). Unstarted offers do not count against the cap.
    max_slots = _max_commission_slots(client)
    if max_slots > 0 and ec.count_started_sync(client.commander.commander_id) >= max_slots:
        _fail(client, "commission_slots_full")
        return None

    busy = set()
    for a in list_commissions_sync(client.commander.commander_id):
        if a.state != ec.STATE_STARTED:
            continue
        for s in (a.ship_ids or []):
            busy.add(int(s))
    for ship_id in resolved_ship_ids:
        if ship_id in busy:
            _fail(client, f"ship_busy id={ship_id}")
            return None

    if oil > 0:
        client.commander.consume_resource(2, oil)
        cur = client.commander.owned_resources_map.get(2, {}).get("amount", 0)
        client.commander.owned_resources_map[2] = {"resource_id": 2, "amount": max(0, cur - oil)}

    finish_time = server_time + collect_time if collect_time > 0 else server_time
    update_commission_sync(
        row.id,
        state=ec.STATE_STARTED,
        ship_ids=resolved_ship_ids,
        start_time=server_time,
        finish_time=finish_time,
    )

    # Official replies to CS_13003 with SC_13004 alone (mitm capture 20260910:
    # four dispatches -> four 2-byte SC_13004s, no SC_13011). The client already
    # knows the commission it just dispatched; an SC_13011 here would only pollute
    # ChapterAutoProxy:RecordNewEventIds (the handover "new commissions" badge).

    msg = protobuf.SC_13004(result=0)
    data = msg.SerializeToString()
    client.write_to_buffer(generate_packet_header(13004, data, client.packet_index) + data)
    log_event("Commission", "DispatchOk", f"cid={client.commander.commander_id} row_id={row_id} commission_id={row.commission_id}", LOG_LEVEL_WARN)
    return None


def handle_event_collection_start(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = json.loads(buffer.decode("utf-8", errors="replace"))
    except Exception as e:
        return 0, 13004, e
    return 0, 13004, _do_start_collection(
        client, payload.get("id", 0), payload.get("ship_id_list", [])
    )


def handle_commission_dispatch(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_13003()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 13004, e
    return 0, 13004, _do_start_collection(
        client, payload.id, list(payload.ship_id_list)
    )


def _ship_type_for_owned(owned: dict):
    try:
        from src.orm.game_data import get_ship_template_config
        tpl = get_ship_template_config(int(owned.get("ship_id", 0)))
        if isinstance(tpl, dict):
            return tpl.get("type")
    except Exception:
        return None
    return None


def _load_collection_template(collection_id: int):
    from src.orm.config_entry import get_config_entry
    from src.db.store import NotFoundError
    try:
        raw = get_config_entry(COLLECTION_TEMPLATE_CATEGORY, str(collection_id))
    except NotFoundError:
        return None
    except Exception as e:
        return e
    if isinstance(raw, dict):
        return raw
    if hasattr(raw, "data"):
        raw = raw.data
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw) if isinstance(raw, str) else dict(raw)
    except Exception:
        return None
