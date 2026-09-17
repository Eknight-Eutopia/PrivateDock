import json
import random
import time
from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.protobuf import protobuf

DEFAULT_EVENT_FINISH_CRIT_CHANCE_PERCENT = 100
COLLECTION_TEMPLATE_CATEGORY = "ShareCfg/collection_template.json"
SHIP_LEVEL_CATEGORY = "ShareCfg/ship_level.json"
SURPLUS_EXP_CAP = 3000000


def _send_event_finish_fail(client, result: int):
    msg = protobuf.SC_13006(result=result, exp=0, is_cri=0)
    data = msg.SerializeToString()
    client.write_to_buffer(generate_packet_header(13006, data, client.packet_index) + data)


def _do_finish_collection(client: Client, row_id: int) -> Optional[Exception]:
    from src.orm import event_collection as ec

    if row_id == 0:
        _send_event_finish_fail(client, 1)
        return None

    # The client sends the template id; resolve the player's in-progress row.
    event = ec.get_commission_by_template_sync(
        client.commander.commander_id, row_id, ec.STATE_STARTED
    )
    if event is None:
        _send_event_finish_fail(client, 2)
        return None

    template = _load_collection_template(event.commission_id)
    if template is None:
        _send_event_finish_fail(client, 1)
        return None
    if isinstance(template, Exception):
        return template

    now = int(time.time())
    over_time = template.get("over_time", 0)
    ship_num = template.get("ship_num", 0)
    exp = template.get("exp", 0)

    if over_time > 0 and now >= over_time:
        _send_event_finish_fail(client, 3)
        return None

    finish_time = event.finish_time or 0
    if finish_time == 0 or now < finish_time:
        _send_event_finish_fail(client, 2)
        return None

    # Ship validation (minimum count / ownership / busy) now happens at dispatch
    # time (see event_collection_start._do_start_collection), so by the time the
    # player collects the reward the assignment is already trusted. We only need
    # the ship list to credit exp to ships still owned; ships that were retired
    # or sold during the commission are simply skipped.
    ship_ids = [int(s) for s in (event.ship_ids or [])]

    try:
        drops, is_cri = _build_event_finish_drops(template)
    except Exception as e:
        return e

    try:
        ec.delete_commission_sync(event.id)
    except Exception as e:
        return e

    for ship_id in ship_ids:
        owned = client.commander.owned_ships_map.get(ship_id)
        if owned is None:
            continue
        try:
            _apply_owned_ship_exp_gain(client, owned, exp)
        except Exception as e:
            return e

    for drop in drops.values():
        try:
            _apply_event_drop(client, drop["type"], drop["id"], drop["number"])
        except Exception as e:
            return e

    # Wiki: "A new Commission is generated when a Daily is completed."
    # Originally delivers the replacement inside SC_13006.new_collection,
    # which the client applies silently — no eventForMsg, so no "Urgent
    # Commission!" msgbox for a plain daily card.
    new_rows: list = []
    try:
        from src.answer.event_collection_spawn import spawn_daily_on_complete_sync
        new_rows = spawn_daily_on_complete_sync(client) or []
    except Exception:
        pass

    resp = protobuf.SC_13006(result=0, exp=exp)
    for d in drops.values():
        resp.drop_list.append(protobuf.DROPINFO(type=d["type"], id=d["id"], number=d["number"]))
    resp.is_cri = 1 if is_cri else 0
    for row in new_rows:
        col = resp.new_collection.add()
        col.id = row.commission_id
        col.finish_time = row.finish_time or 0
        col.over_time = row.expires_at or 0
        for sid in (row.ship_ids or []):
            col.ship_id_list.append(int(sid))

    data = resp.SerializeToString()
    client.write_to_buffer(generate_packet_header(13006, data, client.packet_index) + data)

    # Server-authoritative task progress: completing a commission (collecting
    # its reward) advances "Complete X commissions" tasks (sub_type 80).
    try:
        from src.answer.task_handlers import schedule_emit
        schedule_emit(client, 80, 0, 1)
    except Exception:
        pass
    return None


def handle_event_finish(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = json.loads(buffer.decode("utf-8", errors="replace"))
    except Exception as e:
        return 0, 13006, e
    return 0, 13006, _do_finish_collection(client, payload.get("id", 0))


def handle_commission_collect(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_13005()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 13006, e
    return 0, 13006, _do_finish_collection(client, payload.id)


# Ship EXP (59000) is an unopenable type-98 virtual item in this EN build
# (the client shows no Use button); ship exp from commissions is already
# credited separately via the template's `exp` field. Drop it from loot.
_SHIP_EXP_ITEM_ID = 59000

# Gem commissions ("VIP/Holiday/Patrol Escort") carry their Gems as the
# special_drop with nums "Chance to receive", which _resolve_drop_count parses
# to 1. Private-dock tweak: pay this fixed amount instead.
_GEM_VITEM_IDS = frozenset({59004, 59005})
COMMISSION_GEM_DROP_COUNT = 50


def _entry_count(entry: dict) -> int:
    if entry.get("id") in _GEM_VITEM_IDS:
        return COMMISSION_GEM_DROP_COUNT
    return entry["count"]


def _build_event_finish_drops(template: dict):
    from src.orm.item import resolve_virtual_item_drops

    # `resolve_virtual_item_drops` expands type-98/99 "mystery" virtuals into their
    # concrete contents (gear/skill/tech parts) on receipt, mirroring what add_item
    # does when the grant is actually applied. Resolving here means the drops dict
    # carries the REAL items, so the SC_13006 popup (built from this dict) matches
    # what the client must add locally -- otherwise the client adds the mystery
    # wrapper shown by the server and it vanishes on relogin.
    result = {}
    entries = _parse_collection_drop_objects(template.get("drop_display"))
    if isinstance(entries, Exception):
        return None, False
    for entry in entries:
        if entry["id"] == _SHIP_EXP_ITEM_ID:
            continue
        for (t, i, c) in resolve_virtual_item_drops(entry["id"], _entry_count(entry), entry["type"]):
            key = f"{t}_{i}"
            if key in result:
                result[key]["number"] += c
            else:
                result[key] = {"type": t, "id": i, "number": c}

    special_entries = _parse_collection_drop_objects(template.get("special_drop"))
    if isinstance(special_entries, Exception):
        return None, False
    if not special_entries:
        return result, False

    from src.config.game_variables import get_commission_crit_chance_percent
    crit_chance = get_commission_crit_chance_percent()
    is_cri = random.randint(0, 99) < crit_chance
    if not is_cri:
        return result, False

    for entry in special_entries:
        if entry["id"] == _SHIP_EXP_ITEM_ID:
            continue
        for (t, i, c) in resolve_virtual_item_drops(entry["id"], _entry_count(entry), entry["type"]):
            key = f"{t}_{i}"
            if key in result:
                result[key]["number"] += c
            else:
                result[key] = {"type": t, "id": i, "number": c}
    return result, True


def _parse_collection_drop_objects(raw):
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = json.loads(raw)
    if isinstance(raw, dict):
        # commission `special_drop` entries are stored as a single object, not a list
        raw = [raw]

    if isinstance(raw, list):
        if raw and isinstance(raw[0], dict):
            resolved = []
            for obj in raw:
                count = _resolve_drop_count(obj.get("nums"))
                if isinstance(count, Exception):
                    return count
                drop_type = obj.get("type", 0)
                drop_id = obj.get("id", 0)
                if drop_type == 0 or drop_id == 0 or count == 0:
                    continue
                resolved.append({"type": drop_type, "id": drop_id, "count": count})
            if resolved:
                return resolved

        resolved = []
        for item in raw:
            if not isinstance(item, list) or len(item) < 3:
                continue
            drop_type = _parse_uint32_raw(item[0])
            if drop_type is None:
                continue
            drop_id = _parse_uint32_raw(item[1])
            if drop_id is None:
                continue
            count = _resolve_drop_count(item[2])
            if isinstance(count, Exception):
                return count
            if drop_type == 0 or drop_id == 0 or count == 0:
                continue
            resolved.append({"type": drop_type, "id": drop_id, "count": count})
        return resolved

    return []


def _parse_uint32_raw(raw):
    if isinstance(raw, (int, float)):
        val = int(raw)
        return val if val >= 0 else None
    if isinstance(raw, str):
        try:
            return int(raw)
        except (ValueError, TypeError):
            return None
    if isinstance(raw, bytes):
        try:
            return int(raw.decode())
        except (ValueError, TypeError, UnicodeDecodeError):
            return None
    return None


def _resolve_drop_count(raw):
    if raw is None:
        return 0
    if isinstance(raw, (int, float)):
        return int(raw)
    if isinstance(raw, str):
        raw = raw.strip().replace("\\~", "~")
        if not raw:
            return 0
        if raw.lower() == "chance to receive":
            return 1
        # Rollover commissions (Self Training / Tactical Class / Research
        # Mission / ...) express the coin reward as "3000+"/"4500+" -- the
        # guaranteed base; the official server adds a small ship-match bonus on
        # top (template "4500+" paid out 4566). Parse the base instead of 
        # falling through to the int() failure, which returned 0 and made
        # _parse_collection_drop_objects skip the coins entry entirely (the
        # commission paid out the skill books but never any coins).
        if raw.endswith("+"):
            try:
                return int(raw[:-1])
            except ValueError:
                return 0
        if "~" in raw:
            parts = raw.split("~", 1)
            try:
                mn = int(parts[0].strip())
                mx = int(parts[1].strip())
            except (ValueError, IndexError):
                return 0
            if mx < mn:
                mn, mx = mx, mn
            return mn + random.randint(0, mx - mn)
        try:
            return int(raw)
        except ValueError:
            return 0
    if isinstance(raw, list):
        if not raw:
            return 0
        if len(raw) == 1:
            return int(raw[0])
        mn = int(raw[0])
        mx = int(raw[1])
        if mx < mn:
            mn, mx = mx, mn
        return mn + random.randint(0, mx - mn)
    return 0


def _apply_owned_ship_exp_gain(client, owned, gain: int):
    if gain == 0:
        return
    level = int(owned.get("level", 1) or 1)
    max_level = int(owned.get("max_level", 100) or 100)
    surplus = int(owned.get("surplus_exp", 0) or 0)
    cexp = int(owned.get("exp", 0) or 0)

    def _rarity():
        try:
            from src.orm.game_data import get_ship_template_config
            tpl = get_ship_template_config(int(owned.get("ship_id", 0) or 0))
            if isinstance(tpl, dict):
                return int(tpl.get("rarity", 0) or 0)
        except Exception:
            return 0
        return 0

    if level >= max_level:
        if max_level >= 100:
            surplus = _add_surplus_exp(surplus, gain)
            owned["surplus_exp"] = surplus
            _persist_ship_fields(client, owned, {"surplus_exp": surplus})
        return
    new_exp = cexp + gain
    while level < max_level:
        config = _load_ship_level_config(level)
        if config is None:
            break
        required = config.get("exp", 0)
        if _rarity() == 6:
            required = config.get("exp_ur", 0)
        if required == 0 or new_exp < required:
            break
        new_exp -= required
        level += 1
    owned["exp"] = new_exp
    owned["level"] = level
    if level >= max_level and max_level >= 100 and new_exp > 0:
        surplus = _add_surplus_exp(surplus, new_exp)
        owned["surplus_exp"] = surplus
        new_exp = 0
        owned["exp"] = 0
    _persist_ship_fields(client, owned, {"exp": owned.get("exp", 0), "level": owned.get("level", 1), "surplus_exp": owned.get("surplus_exp", 0)})


def _persist_ship_fields(client, owned, fields: dict):
    try:
        from src.orm.owned_ship import sync_update_owned_ship_fields
        sync_update_owned_ship_fields(
            client.commander.commander_id, int(owned.get("id", 0) or 0), **fields
        )
    except Exception:
        pass


def _add_surplus_exp(current: int, gain: int) -> int:
    if current >= SURPLUS_EXP_CAP:
        return current
    new_value = current + gain
    return min(new_value, SURPLUS_EXP_CAP)


def _load_ship_level_config(level: int):
    from src.orm.config_entry import get_config_entry
    from src.db.store import NotFoundError
    if level == 0:
        return None
    try:
        entry = get_config_entry(SHIP_LEVEL_CATEGORY, str(level))
    except NotFoundError:
        return None
    except Exception:
        return None
    if entry is None:
        return None
    if isinstance(entry, dict):
        return entry
    data = getattr(entry, "data", None)
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            return None
    if isinstance(data, dict):
        return data
    return None


def _apply_event_drop(client, drop_type: int, drop_id: int, drop_count: int):
    if drop_id == 0 or drop_count == 0:
        return
    from src.consts.drop_types import DROP_TYPE_RESOURCE, DROP_TYPE_ITEM
    if drop_type in (14, 15, 31):
        from src.orm.commander_attire import grant_commander_attire_drop_sync
        grant_commander_attire_drop_sync(client.commander.commander_id, drop_type, drop_id, drop_count)
    elif drop_type == DROP_TYPE_RESOURCE:
        client.commander.add_resource(drop_id, drop_count)
    elif drop_type == DROP_TYPE_ITEM:
        client.commander.add_item(drop_id, drop_count)


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
