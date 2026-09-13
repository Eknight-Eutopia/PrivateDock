import asyncio
import json
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

PACKET_ID = 14204


def _send_14204(client, result=1):
    asyncio.create_task(client.send_message(PACKET_ID, protobuf.SC_14204(result=result)))

SPWEAPON_DATA_STATISTICS_CATEGORY = "sharecfgdata/spweapon_data_statistics.json"
ITEM_DATA_STATISTICS_CATEGORY = "sharecfgdata/item_data_statistics.json"


def _count_id_list(ids: list) -> dict:
    counts = {}
    for item_id in ids:
        counts[item_id] = counts.get(item_id, 0) + 1
    return counts


def _raw_uint32(raw) -> tuple[int, bool]:
    if raw is None:
        return 0, False
    if isinstance(raw, (int, float)):
        v = int(raw)
        if v < 0:
            return 0, False
        return v, True
    return 0, False


def _spweapon_upgrade_step_config(template_id: int) -> tuple:
    from src.orm.game_data import get_sp_weapon_data_statistics_config, get_sp_weapon_upgrade_config
    raw = get_sp_weapon_data_statistics_config(template_id)
    if not raw:
        return 0, 0, 0, None
    next_id = 0
    need_pt = 0
    gold = 0

    if "next" in raw:
        next_id, _ = _raw_uint32(raw["next"])
    elif "upgrade_id" in raw:
        next_id, _ = _raw_uint32(raw["upgrade_id"])
    elif "upgrade_to" in raw:
        next_id, _ = _raw_uint32(raw["upgrade_to"])

    upgrade_id = raw.get("upgrade_id", 0)
    up_config = get_sp_weapon_upgrade_config(upgrade_id) if upgrade_id else None

    if up_config:
        if "upgrade_use_pt" in up_config:
            need_pt, _ = _raw_uint32(up_config["upgrade_use_pt"])
        if "upgrade_use_gold" in up_config:
            gold, _ = _raw_uint32(up_config["upgrade_use_gold"])

    if need_pt == 0:
        if "upgrade_pt" in raw:
            need_pt, _ = _raw_uint32(raw["upgrade_pt"])
        elif "upgrade_need_pt" in raw:
            need_pt, _ = _raw_uint32(raw["upgrade_need_pt"])
        elif "pt" in raw:
            need_pt, _ = _raw_uint32(raw["pt"])

    if gold == 0:
        if "upgrade_use_gold" in raw:
            gold, _ = _raw_uint32(raw["upgrade_use_gold"])
        elif "trans_use_gold" in raw:
            gold, _ = _raw_uint32(raw["trans_use_gold"])
        elif "use_gold" in raw:
            gold, _ = _raw_uint32(raw["use_gold"])

    return next_id, need_pt, gold, None


def _compute_spweapon_upgrade(start_template_id: int, pt: int) -> tuple:
    template_id = start_template_id
    remainder = pt
    gold_cost = 0
    upgraded = False
    for _ in range(20):
        next_id, need_pt, step_gold, err = _spweapon_upgrade_step_config(template_id)
        if err is not None:
            return 0, 0, 0, False, err
        if next_id == 0 or need_pt == 0:
            break
        if remainder < need_pt:
            break
        remainder -= need_pt
        gold_cost += step_gold
        template_id = next_id
        upgraded = True
    return template_id, remainder, gold_cost, upgraded, None


def _spweapon_consume_pt(template_id: int) -> tuple:
    from src.orm.game_data import get_sp_weapon_data_statistics_config, get_sp_weapon_upgrade_config
    raw = get_sp_weapon_data_statistics_config(template_id)
    if not raw:
        return 0, None
    upgrade_id = raw.get("upgrade_id", 0)
    up_config = get_sp_weapon_upgrade_config(upgrade_id) if upgrade_id else None
    if up_config and "upgrade_supply_pt" in up_config:
        pt, ok = _raw_uint32(up_config["upgrade_supply_pt"])
        if ok and pt > 0:
            return pt, None
    if "upgrade_get_pt" in raw:
        return _raw_uint32(raw["upgrade_get_pt"])[0], None
    if "destory_get_pt" in raw:
        return _raw_uint32(raw["destory_get_pt"])[0], None
    if "consume_pt" in raw:
        return _raw_uint32(raw["consume_pt"])[0], None
    return 0, None


def _item_consume_pt(item_id: int) -> tuple:
    from src.orm.config_entry import get_config_entry_sync
    entry = get_config_entry_sync(ITEM_DATA_STATISTICS_CATEGORY, str(item_id))
    raw = entry.data if entry and entry.data else None
    if not raw:
        try:
            from src.misc.update_data_helpers import get_privatedock_data
            d = get_privatedock_data("EN", ITEM_DATA_STATISTICS_CATEGORY)
            if isinstance(d, dict):
                raw = d.get(str(item_id))
        except Exception:
            pass
    if not raw:
        return 0, None
    if isinstance(raw, str):
        raw = json.loads(raw)
    if "spweapon_pt" in raw:
        return _raw_uint32(raw["spweapon_pt"])[0], None
    if "pt" in raw:
        return _raw_uint32(raw["pt"])[0], None
    if "usage_arg" in raw:
        usage_arg = raw["usage_arg"]
        if isinstance(usage_arg, str):
            try:
                usage_arg = json.loads(usage_arg)
            except Exception:
                pass
        if isinstance(usage_arg, (int, float)):
            return int(usage_arg), None
        if isinstance(usage_arg, list) and len(usage_arg) > 0:
            return int(usage_arg[0]), None
    return 0, None


def handle_upgrade_spweapon(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_14203()
    try:
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, PACKET_ID, e

    if client is None or client.commander is None:
        _send_14204(client)
        return 0, PACKET_ID, None

    commander = client.commander
    if (getattr(commander, "owned_sp_weapons_map", None) is None
            or getattr(commander, "owned_ships_map", None) is None
            or getattr(commander, "owned_resources_map", None) is None
            or getattr(commander, "commander_items_map", None) is None
            or getattr(commander, "misc_items_map", None) is None):
        try:
            commander.load()
        except Exception as e:
            return 0, PACKET_ID, e

    spweapon_id = payload.spweapon_id
    if spweapon_id == 0:
        _send_14204(client)
        return 0, PACKET_ID, None

    target = commander.owned_sp_weapons_map.get(spweapon_id)
    if target is None:
        _send_14204(client)
        return 0, PACKET_ID, None

    target_ship_id = target.get("equipped_ship_id", 0) if isinstance(target, dict) else getattr(target, "equipped_ship_id", 0)
    target_template_id = target.get("template_id", 0) if isinstance(target, dict) else getattr(target, "template_id", 0)
    target_pt = target.get("pt", 0) if isinstance(target, dict) else getattr(target, "pt", 0)

    ship_id = payload.ship_id
    if ship_id != 0:
        if ship_id not in commander.owned_ships_map:
            _send_14204(client)
            return 0, PACKET_ID, None
        if target_ship_id != 0 and target_ship_id != ship_id:
            _send_14204(client)
            return 0, PACKET_ID, None

    consume_spweapon_ids = list(payload.spweapon_id_list)
    seen_spweapons = set()
    pt_gain = 0
    for consume_id in consume_spweapon_ids:
        if consume_id == 0 or consume_id == spweapon_id:
            _send_14204(client)
            return 0, PACKET_ID, None
        if consume_id in seen_spweapons:
            _send_14204(client)
            return 0, PACKET_ID, None
        seen_spweapons.add(consume_id)
        consume = commander.owned_sp_weapons_map.get(consume_id)
        if consume is None:
            _send_14204(client)
            return 0, PACKET_ID, None
        consume_tid = consume.get("template_id", 0) if isinstance(consume, dict) else getattr(consume, "template_id", 0)
        consume_pt = consume.get("pt", 0) if isinstance(consume, dict) else getattr(consume, "pt", 0)
        gain, err = _spweapon_consume_pt(consume_tid)
        if err is not None:
            return 0, PACKET_ID, err
        pt_gain += gain
        pt_gain += consume_pt

    item_ids = list(payload.item_id_list)
    item_counts = _count_id_list(item_ids)
    for item_id, count in item_counts.items():
        if item_id == 0:
            _send_14204(client)
            return 0, PACKET_ID, None
        if not commander.has_enough_item(item_id, count):
            _send_14204(client)
            return 0, PACKET_ID, None
        gain, err = _item_consume_pt(item_id)
        if err is not None:
            return 0, PACKET_ID, err
        if gain == 0:
            continue
        pt_gain += gain * count

    pt_total = target_pt + pt_gain
    upgraded_template_id, remainder_pt, gold_cost, upgraded, err = _compute_spweapon_upgrade(
        target_template_id, pt_total,
    )
    if err is not None:
        return 0, PACKET_ID, err
    if not upgraded and pt_gain == 0:
        _send_14204(client)
        return 0, PACKET_ID, None
    if gold_cost != 0 and not commander.has_enough_gold(gold_cost):
        _send_14204(client)
        return 0, PACKET_ID, None

    from src.orm.spweapon import save_owned_sp_weapon, remove_owned_sp_weapon
    try:
        if gold_cost != 0:
            commander.consume_resource(1, gold_cost)
        for item_id, count in item_counts.items():
            if count == 0:
                continue
            commander.consume_item(item_id, count)
        for consume_id in consume_spweapon_ids:
            remove_owned_sp_weapon(commander.commander_id, consume_id)
            if hasattr(commander, "owned_sp_weapons_map") and commander.owned_sp_weapons_map:
                commander.owned_sp_weapons_map.pop(consume_id, None)
        if hasattr(commander, "owned_sp_weapons") and commander.owned_sp_weapons:
            commander.owned_sp_weapons = [
                sp for sp in commander.owned_sp_weapons
                if (sp.get("id", 0) if isinstance(sp, dict) else getattr(sp, "id", 0)) not in seen_spweapons
            ]

        target = commander.owned_sp_weapons_map.get(spweapon_id)
        if target is None:
            _send_14204(client)
            return 0, PACKET_ID, None
        if isinstance(target, dict):
            target["template_id"] = upgraded_template_id
            target["pt"] = remainder_pt
        else:
            target.template_id = upgraded_template_id
            target.pt = remainder_pt
        save_owned_sp_weapon(target)
    except Exception as e:
        _send_14204(client)
        return 0, PACKET_ID, e

    _send_14204(client, 0)
    return 0, PACKET_ID, None

