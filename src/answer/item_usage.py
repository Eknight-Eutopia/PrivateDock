import json
import os
import random
import re
from typing import Optional

from src.connection.client import Client
from src.consts.drop_types import (
    DROP_TYPE_CHAT_FRAME,
    DROP_TYPE_COMBAT_UI_STYLE,
    DROP_TYPE_EQUIP,
    DROP_TYPE_EQUIPMENT_SKIN,
    DROP_TYPE_ICON_FRAME,
    DROP_TYPE_ITEM,
    DROP_TYPE_RESOURCE,
    DROP_TYPE_SHIP,
    DROP_TYPE_SKIN,
    DROP_TYPE_SPWEAPON,
    DROP_TYPE_TRANS_ITEM,
    DROP_TYPE_VITEM,
)

# Tech pack drops: {item_id: [equipment_id, ...]}
# Each use picks one random equipment_id and adds it to owned_equipments.
# DROPINFO uses DROP_TYPE_EQUIP so the client's Drop model adds the equipment
# (EquipmentProxy:addEquipmentById) and shows it in the drop popup.
# Equipment pools are configured in configurations/tech_pack_drops.json.
def _resolve_tech_pack_drops_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    cur = here
    for _ in range(6):
        cand = os.path.join(cur, "configurations", "tech_pack_drops.json")
        if os.path.exists(cand):
            return cand
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return os.path.join("configurations", "tech_pack_drops.json")


def load_tech_pack_drops() -> dict[int, list[int]]:
    path = _resolve_tech_pack_drops_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
            return {int(k): [int(x) for x in v] for k, v in raw.items() if not str(k).startswith("_")}
    except (json.JSONDecodeError, OSError, ValueError):
        return {}


def reload_tech_pack_drops() -> None:
    _TECH_PACK_DROPS.clear()
    _TECH_PACK_DROPS.update(load_tech_pack_drops())


_TECH_PACK_DROPS: dict[int, list[int]] = load_tech_pack_drops()


def use_item(client: Client, item_id: int, count: int, arg: list) -> Optional[dict]:
    if count == 0:
        return {"result": 1, "drop_list": []}

    available = _get_commander_item_count(client, item_id)
    if available < count:
        return {"result": 1, "drop_list": []}

    config = _load_item_usage_config(item_id)
    if config is None:
        return {"result": 1, "drop_list": []}

    plan = _prepare_item_usage(client, config, arg, count)
    if plan is None:
        return {"result": 1, "drop_list": []}
    if plan.get("result", 1) != 0:
        return {"result": plan["result"], "drop_list": plan.get("drop_list", [])}

    _consume_commander_item(client, item_id, count)
    apply_fn = plan.get("_apply")
    if apply_fn:
        apply_fn()

    # Server-authoritative task progress: opening tech packs (sub_type 50, e.g.
    # Handbook 22015 "Open a total of 9 tech packs from any faction"). Tech
    # packs are the usage_drop items whose contents come from _TECH_PACK_DROPS
    # (random faction gear). Count each opened pack.
    # Also emit sub_type 120 (use N item X, e.g. EXP books, Quick Finishers, Oxy-colas).
    try:
        from src.answer.task_handlers import schedule_emit, schedule_possession_sync
        item_id = int(config.get("id", 0) or 0)
        schedule_emit(client, 120, item_id, count)
        if item_id in _TECH_PACK_DROPS:
            schedule_emit(client, 50, item_id, count)
        schedule_possession_sync(client)
    except Exception:
        pass

    return {"result": 0, "drop_list": plan.get("drop_list", [])}


def _load_item_usage_config(item_id: int) -> Optional[dict]:
    from src.orm.config_entry import fetch_config_entry_data
    for category in ['sharecfgdata/item_data_statistics.json', 'sharecfgdata/item_virtual_data_statistics.json']:
        data = fetch_config_entry_data(category, item_id)
        if isinstance(data, dict):
            return data
    return None


def _prepare_item_usage(client: Client, config: dict, arg: list, count: int) -> Optional[dict]:
    usage = config.get("usage", "")
    if usage == "usage_drop":
        return _prepare_drop_usage(client, config, count)
    elif usage == "usgae_drop_template" or usage == "usage_drop_template":
        return _prepare_drop_template_usage(client, config, count)
    elif usage == "usage_drop_appointed":
        return _prepare_drop_appointed_usage(client, config, arg, count)
    elif usage == "usage_drop_appointed_skinexchange" or usage == "usage_drop_appointed_skin":
        return _prepare_skin_select_usage(client, config, arg, count)
    elif usage == "usage_drop_random_skin":
        return _prepare_random_skin_usage(client, config, count)
    elif usage == "usage_invitation":
        return _prepare_invitation_usage(client, config, arg, count)
    elif usage == "usage_skin_exp":
        return _prepare_skin_exp_usage(client, config, count)
    elif usage in ("usage_skin_discount", "usage_shop_discount"):
        return _prepare_skin_discount_usage(client, config, arg, count)
    elif usage == "usage_food":
        return _prepare_food_usage(client, config, count)
    elif usage == "usage_dorm_lv_up":
        return _prepare_dorm_lv_up_usage(client, count)
    else:
        # Fallback: if display_icon has entries, treat as random drops
        di = config.get("display_icon")
        if di and isinstance(di, list) and len(di) > 0:
            return _prepare_display_icon_drops(client, config, count)
        return {"result": 1, "drop_list": [], "_apply": lambda: None}


def _prepare_drop_usage(client: Client, config: dict, count: int) -> dict:
    from src.orm.config_entry import list_config_entries_sync
    raw = config.get("usage_arg", 0)
    if isinstance(raw, (int, float)):
        drop_id = int(raw)
    elif isinstance(raw, list) and len(raw) > 0:
        drop_id = int(raw[0])
    else:
        try:
            drop_id = int(raw)
        except (ValueError, TypeError):
            drop_id = None

    if drop_id is not None:
        entries = list_config_entries_sync("ShareCfg/drop_data_restore.json") or []
        matched = []
        for e in entries:
            data = e.data if isinstance(e.data, dict) else json.loads(e.data) if isinstance(e.data, str) else {}
            try:
                did = int(data.get("drop_id", 0))
            except (ValueError, TypeError):
                continue
            if did == drop_id:
                matched.append(data)
        if matched:
            drops = [_new_drop_info(DROP_TYPE_TRANS_ITEM, e.get("id", 0), count) for e in matched]
            def _apply():
                for entry in matched:
                    _apply_drop_restore_entry(client, entry, count)
            return {"result": 0, "drop_list": drops, "_apply": _apply}

    # Tech pack drops: add random equipment to owned_equipments
    item_id = config.get("id", 0)
    if item_id and item_id in _TECH_PACK_DROPS:
        pool = _TECH_PACK_DROPS[item_id]
        chosen = [pool[random.randint(0, len(pool) - 1)] for _ in range(count)]
        drops = {}
        for eid in chosen:
            key = f"{DROP_TYPE_EQUIP}_{eid}"
            if key in drops:
                drops[key]["number"] += 1
            else:
                drops[key] = _new_drop_info(DROP_TYPE_EQUIP, eid, 1)
        def _apply_tech():
            from src.orm.owned_equipment import add_owned_equipment
            for eid in chosen:
                add_owned_equipment(client.commander.commander_id, eid, 1)
        return {"result": 0, "drop_list": list(drops.values()), "_apply": _apply_tech}

    # Fallback: some usage_drop items (e.g. Promise Crate, usage_arg=4100) carry
    # their contents in display_icon when no drop_data_restore entry exists for
    # usage_arg. Resolve them from display_icon instead of leaving an unopenable
    # box in the inventory (which the client cannot open).
    di = config.get("display_icon")
    if di and isinstance(di, list) and len(di) > 0:
        return _prepare_display_icon_drops(client, config, count)

    return {"result": 1, "drop_list": [], "_apply": lambda: None}


def _display_icon_is_random(config: dict) -> bool:
    """True when the item's description marks the display_icon entries as a
    random pool ("Chance to receive a random ...", "... at random", "one of").
    False = the entries are the item's FULL fixed contents ("Open to receive
    the following items", "Contains 1x ... 10x ...", "Use to receive X and Y")
    -- e.g. Battle UI Packs, Fantastic Phoenix gear-skin sets, letters, lucky
    bags. Mirrors the wording rule used by orm/item.py for grant-time virtual
    bundles, so opening a fixed-content box grants every listed entry instead
    of one random pick."""
    return bool(re.search(r"random|chance|one of|at random",
                          str(config.get("display") or ""), re.I))


def _prepare_display_icon_drops(client: Client, config: dict, count: int) -> dict:
    di = config.get("display_icon")
    if not di or not isinstance(di, list) or len(di) == 0:
        return {"result": 1, "drop_list": [], "_apply": lambda: None}
    entries = _parse_display_icon(di)
    if not entries:
        return {"result": 1, "drop_list": [], "_apply": lambda: None}
    if _display_icon_is_random(config):
        # Random pool: one randomly-chosen entry per use (gear skin boxes etc.).
        drops = {}
        for _ in range(count):
            entry = entries[random.randint(0, len(entries) - 1)]
            key = f"{entry['type']}_{entry['id']}"
            if key in drops:
                drops[key]["number"] += entry["count"]
            else:
                drops[key] = _new_drop_info(entry["type"], entry["id"], entry["count"])
    else:
        # Fixed bundle: display_icon IS the full contents -- grant every entry
        # scaled by the used count (Battle UI Pack = theme + coins, Fantastic
        # Phoenix = all three gear skins, letters, ...). Never a random pick.
        drops = {}
        for entry in entries:
            key = f"{entry['type']}_{entry['id']}"
            drops[key] = _new_drop_info(entry["type"], entry["id"],
                                        entry["count"] * count)
    def _apply():
        for drop in drops.values():
            _apply_drop(client, drop["type"], drop["id"], drop["number"])
    return {"result": 0, "drop_list": list(drops.values()), "_apply": _apply}


def _build_template_drop_entries(config: dict, count: int) -> list[tuple]:
    """Resolve a `usage_drop_template` pack into its concrete drops.

    Returns a list of (drop_type, drop_id, count) tuples: the gold/oil from
    ``usage_arg`` plus one randomly-picked non-resource entry from
    ``display_icon`` per pack. The resource entries inside ``display_icon`` are
    excluded so they are not double-counted with the ``usage_arg`` gold/oil.
    """
    raw = _normalize_usage_arg(config.get("usage_arg", []))
    if not isinstance(raw, list) or len(raw) < 3:
        return []

    gold = int(raw[1]) * count if len(raw) > 1 else 0
    oil = int(raw[2]) * count if len(raw) > 2 else 0

    entries = []
    if gold > 0:
        entries.append((DROP_TYPE_RESOURCE, 1, gold))
    if oil > 0:
        entries.append((DROP_TYPE_RESOURCE, 2, oil))

    display_entries = _parse_display_icon(config.get("display_icon"))
    filtered = _filter_display_icons(display_entries, gold > 0, oil > 0)

    # Template packs (Daily/Weekly/Monthly Supplies, level packs, ...) are
    # FIXED bundles: the display_icon list IS the full contents with real
    # counts (Daily Supplies Pack = 8000 gold + 2x Mystery T3 Tech Pack +
    # 8x Wisdom Cube + 4x Quick Finisher; "Lv. 10 Pack" = 10 cubes + ...).
    # Grant EVERY entry scaled by the pack count — no random pick. The gold/
    # oil showcase entries are already filtered out above (they come from
    # usage_arg). Genuinely random pools (gear skin boxes etc.) use plain
    # usage_drop and keep their one-pick behavior.
    for entry in filtered:
        entries.append((entry["type"], entry["id"], entry["count"] * count))

    return entries


def _prepare_drop_template_usage(client: Client, config: dict, count: int) -> dict:
    entries = _build_template_drop_entries(config, count)
    if not entries:
        return {"result": 1, "drop_list": []}

    drops = [_new_drop_info(t, i, c) for (t, i, c) in entries]

    def _apply():
        for (t, i, c) in entries:
            _apply_drop(client, t, i, c)

    return {"result": 0, "drop_list": drops, "_apply": _apply}


def _prepare_drop_appointed_usage(client: Client, config: dict, arg: list, count: int) -> dict:
    raw = _normalize_usage_arg(config.get("usage_arg", []))
    options = raw if isinstance(raw, list) else []
    if not options:
        return {"result": 1, "drop_list": []}

    selection = _select_drop_option(options, arg)
    if selection is None or len(selection) < 3:
        return {"result": 1, "drop_list": []}

    drop_type = int(selection[0])
    drop_id = int(selection[1])
    drop_count = int(selection[2]) * count

    def _apply():
        _apply_drop(client, drop_type, drop_id, drop_count)

    return {
        "result": 0,
        "drop_list": [_new_drop_info(drop_type, drop_id, drop_count)],
        "_apply": _apply,
    }


def _prepare_skin_select_usage(client: Client, config: dict, arg: list, count: int) -> dict:
    selection = arg[0] if arg else 0
    if selection == 0:
        return {"result": 1, "drop_list": []}

    choices = _parse_skin_exchange_choices(config.get("usage_arg"))
    if not _contains_uint32(choices, selection):
        return {"result": 1, "drop_list": []}

    def _apply():
        for _ in range(count):
            client.commander.give_skin(selection)

    return {
        "result": 0,
        "drop_list": [_new_drop_info(DROP_TYPE_SKIN, selection, count)],
        "_apply": _apply,
    }


def _prepare_random_skin_usage(client: Client, config: dict, count: int) -> dict:
    choices = _parse_random_skin_choices(config.get("usage_arg"))
    if not choices:
        return {"result": 1, "drop_list": []}

    random_drops = {}
    for _ in range(count):
        selection = choices[random.randint(0, len(choices) - 1)]
        key = f"{DROP_TYPE_SKIN}_{selection}"
        if key in random_drops:
            random_drops[key]["number"] += 1
        else:
            random_drops[key] = _new_drop_info(DROP_TYPE_SKIN, selection, 1)

    def _apply():
        for drop in random_drops.values():
            _apply_drop(client, drop["type"], drop["id"], drop["number"])

    return {"result": 0, "drop_list": list(random_drops.values()), "_apply": _apply}


def _prepare_invitation_usage(client: Client, config: dict, arg: list, count: int) -> dict:
    if not arg:
        return {"result": 1, "drop_list": []}

    choices = _normalize_usage_arg(config.get("usage_arg", []))
    if not isinstance(choices, list):
        return {"result": 1, "drop_list": []}

    selection = arg[0]
    if not _contains_uint32(choices, selection):
        return {"result": 1, "drop_list": []}

    def _apply():
        for _ in range(count):
            client.commander.add_ship(selection)

    return {
        "result": 0,
        "drop_list": [_new_drop_info(DROP_TYPE_SHIP, selection, count)],
        "_apply": _apply,
    }


def _prepare_skin_exp_usage(client: Client, config: dict, count: int) -> dict:
    raw = _normalize_usage_arg(config.get("usage_arg", []))
    if not isinstance(raw, list) or not raw:
        return {"result": 1, "drop_list": []}

    from src.orm.config_entry import get_config_entry
    shop_id = int(raw[0])
    shop_raw = get_config_entry("ShareCfg/shop_template.json", str(shop_id))
    if shop_raw is None:
        return {"result": 1, "drop_list": []}
    shop_entry = shop_raw if isinstance(shop_raw, dict) else json.loads(shop_raw) if isinstance(shop_raw, str) else shop_raw

    effect_args = _normalize_usage_arg(shop_entry.get("effect_args", []))
    if not isinstance(effect_args, list) or not effect_args:
        return {"result": 1, "drop_list": []}

    time_second = int(shop_entry.get("time_second", 0))
    if time_second == 0:
        return {"result": 1, "drop_list": []}

    import time as _time
    skin_id = int(effect_args[0])
    base_ts = int(_time.time())

    owned_skins = getattr(client.commander, "owned_skins_map", None)
    if owned_skins is not None:
        owned = owned_skins.get(skin_id)
        if owned and owned.get("expires_at", 0) > base_ts:
            base_ts = owned["expires_at"]
    else:
        try:
            from src.orm.skin import get_owned_skin_expiry
            expires_ts = get_owned_skin_expiry(client.commander.commander_id, skin_id)
            if expires_ts is not None and expires_ts > base_ts:
                base_ts = expires_ts
        except Exception:
            pass

    expiry = base_ts + time_second * count

    def _apply():
        client.commander.give_skin_with_expiry(skin_id, expiry)

    return {"result": 0, "drop_list": [], "_apply": _apply}


def _prepare_skin_discount_usage(client: Client, config: dict, arg: list, count: int) -> dict:
    if not arg:
        return {"result": 1, "drop_list": []}

    shop_id = int(arg[0])
    allowed, discount = _parse_discount_args(config.get("usage_arg"))
    if allowed and 0 not in allowed and not _contains_uint32(allowed, shop_id):
        return {"result": 1, "drop_list": []}

    from src.orm.config_entry import get_config_entry
    shop_raw = get_config_entry("ShareCfg/shop_template.json", str(shop_id))
    if shop_raw is None:
        return {"result": 1, "drop_list": []}
    shop_entry = shop_raw if isinstance(shop_raw, dict) else json.loads(shop_raw) if isinstance(shop_raw, str) else shop_raw

    effect_args = _normalize_usage_arg(shop_entry.get("effect_args", []))
    if not isinstance(effect_args, list) or not effect_args:
        return {"result": 1, "drop_list": []}

    resource_type = int(shop_entry.get("resource_type", 0))
    resource_num = int(shop_entry.get("resource_num", 0))
    cost = max(0, resource_num - discount)
    if cost > 0:
        from src.orm.resource import has_enough_resource
        if not has_enough_resource(client.commander.commander_id, resource_type, cost * count):
            return {"result": 1, "drop_list": []}

    skin_id = int(effect_args[0])

    def _apply():
        if cost > 0:
            from src.orm.resource import consume_resource
            consume_resource(client.commander.commander_id, resource_type, cost * count)
        for _ in range(count):
            client.commander.give_skin(skin_id)

    return {
        "result": 0,
        "drop_list": [_new_drop_info(DROP_TYPE_SKIN, skin_id, count)],
        "_apply": _apply,
    }


def _prepare_food_usage(client: Client, config: dict, count: int) -> dict:
    raw = _normalize_usage_arg(config.get("usage_arg", []))
    if not isinstance(raw, list) or not raw:
        return {"result": 1, "drop_list": []}
    food_amount = int(raw[0]) * count
    from src.orm.commander_dorm_state import get_or_create_commander_dorm_state, save_commander_dorm_state
    from .dorm_simulation import load_dorm_level_template
    state = get_or_create_commander_dorm_state(client.commander.commander_id)
    current = getattr(state, 'food', 0) or 0
    tpl = load_dorm_level_template(max(getattr(state, 'level', 1) or 1, 1))
    capacity = int((tpl or {}).get("capacity", 0) or 0)
    extra = getattr(state, 'food_max_increase', 0) or 0
    state.food = min(current + food_amount, capacity + extra)
    save_commander_dorm_state(state)

    # usage_arg = [food_amount, buff_id, buff_duration_seconds] grants a dorm
    # exp buff (curry 3600s = 1h, royal gourmet 10800s = 3h, full course 21600s
    # = 6h — the item tooltip "for 60/180/360 minutes" matches). Re-using food
    # with the same active buff ADDs the full duration to its current expiry
    # (client CommonBuff.timestamp = end timestamp); TTL from now is capped at
    # benefit_buff_template.max_time (24h stacking bound).
    if len(raw) >= 3 and int(raw[1]) > 0:
        import asyncio
        from datetime import datetime, timedelta, timezone
        from src.orm.commander_buff import upsert_commander_buff, list_commander_buffs
        from src.orm.config_entry import get_config_entry_sync
        from src.answer.miscops.handlers import build_player_buffs_message

        buff_id = int(raw[1])
        duration = int(raw[2]) * count
        now = datetime.now(timezone.utc)
        base = now
        for buff in list_commander_buffs(client.commander.commander_id):
            if buff.buff_id == buff_id and buff.expires_at and buff.expires_at > now:
                base = buff.expires_at
                break
        expires_at = base + timedelta(seconds=duration)
        cfg = get_config_entry_sync("ShareCfg/benefit_buff_template.json", str(buff_id))
        max_time = 0
        if cfg is not None and isinstance(cfg.data, dict):
            try:
                max_time = int(cfg.data.get("max_time", 0) or 0)
            except (TypeError, ValueError):
                max_time = 0
        if max_time > 0 and (expires_at - now).total_seconds() > max_time:
            expires_at = now + timedelta(seconds=max_time)
        upsert_commander_buff(client.commander.commander_id, buff_id, expires_at)
        msg = build_player_buffs_message(client.commander.commander_id)
        asyncio.create_task(client.send_message(11015, msg))

    from src.answer import schedule_emit
    # Daily dorm-snack task (sub_type 61) counts per use; weekly (sub_type 60)
    # counts the ACTUAL snack amount added (capped by dorm capacity, not the raw
    # item amount).
    actual_added = max(0, state.food - current)
    schedule_emit(client, 61, 0, 1)
    if actual_added > 0:
        schedule_emit(client, 60, 0, actual_added)

    return {
        "result": 0,
        "drop_list": [],
        "_apply": lambda: None,
    }


def _prepare_dorm_lv_up_usage(client: Client, count: int) -> dict:
    from src.orm.commander_dorm_state import get_or_create_commander_dorm_state, save_commander_dorm_state
    state = get_or_create_commander_dorm_state(client.commander.commander_id)
    from src.orm.config_entry import get_config_entry
    new_level = getattr(state, 'level', 1) + count
    max_level = 10
    template = get_config_entry("ShareCfg/dorm_data_template.json", str(new_level))
    if template is None:
        if new_level > max_level:
            return {"result": 1, "drop_list": []}
        new_level = max_level
    state.level = new_level
    save_commander_dorm_state(state)
    return {"result": 0, "drop_list": [], "_apply": lambda: None}


def _get_commander_item_count(client: Client, item_id: int) -> int:
    from src.orm.item import get_commander_item_count
    return get_commander_item_count(client.commander.commander_id, item_id)


def _consume_commander_item(client: Client, item_id: int, count: int) -> None:
    from src.orm.item import consume_commander_item
    consume_commander_item(client.commander.commander_id, item_id, count)
    items_map = getattr(client.commander, "commander_items_map", {})
    if item_id in items_map:
        entry = items_map[item_id]
        entry["count"] = max(0, entry.get("count", 0) - count)
    misc_map = getattr(client.commander, "misc_items_map", {})
    if item_id in misc_map:
        entry = misc_map[item_id]
        entry["data"] = max(0, entry.get("data", 0) - count)


def _apply_drop(client: Client, drop_type: int, drop_id: int, drop_count: int, _depth: int = 0) -> bool:
    from src.orm.item import add_item, resolve_virtual_item_drops
    from src.orm.resource import add_resource
    if drop_type == DROP_TYPE_RESOURCE:
        add_resource(client.commander.commander_id, drop_id, drop_count)
        return True
    elif drop_type == DROP_TYPE_ITEM:
        # resolve_virtual_item_drops already fully resolves the mystery box
        # chain; each returned entry is a concrete grant. Apply it directly
        # rather than re-resolving (re-resolving recursively looped forever on
        # items whose resolved form is still tagged type=ITEM).
        for t, i, c in resolve_virtual_item_drops(drop_id, drop_count):
            if t == DROP_TYPE_RESOURCE:
                add_resource(client.commander.commander_id, i, c)
            elif t == DROP_TYPE_SHIP:
                for _ in range(c):
                    client.commander.add_ship(i)
            elif t == DROP_TYPE_SKIN:
                for _ in range(c):
                    client.commander.give_skin(i)
            elif t == DROP_TYPE_VITEM:
                continue
            else:
                add_item(client.commander.commander_id, i, c)
        return True
    elif drop_type == DROP_TYPE_SHIP:
        for _ in range(drop_count):
            client.commander.add_ship(drop_id)
        return True
    elif drop_type == DROP_TYPE_SKIN:
        for _ in range(drop_count):
            client.commander.give_skin(drop_id)
        return True
    elif drop_type == DROP_TYPE_VITEM:
        return True
    elif drop_type == DROP_TYPE_EQUIPMENT_SKIN:
        # persist ownership; SC_14101 lists owned skins with real counts and
        # the client refuses to apply a skin with count == 0.
        from src.orm.equipment_skin import grant_equip_skin_sync
        from src.answer.equipped_weapon_skin import push_equip_skin_list
        grant_equip_skin_sync(client.commander.commander_id, drop_id, max(drop_count, 1))
        push_equip_skin_list(client)
        return True
    elif drop_type == DROP_TYPE_EQUIP:
        from src.orm.owned_equipment import _sync_add_owned_equipment
        _sync_add_owned_equipment(client.commander.commander_id, drop_id, drop_count)
        return True
    elif drop_type == DROP_TYPE_SPWEAPON:
        # augment units have no storage here; consumed.
        return True
    elif drop_type in (DROP_TYPE_ICON_FRAME, DROP_TYPE_CHAT_FRAME, DROP_TYPE_COMBAT_UI_STYLE):
        # attire: persist ownership for SC_11003 lists; the client unlocks the
        # style locally from the same DROPINFO.
        from src.orm.commander_attire import grant_commander_attire_drop_sync
        grant_commander_attire_drop_sync(client.commander.commander_id, drop_type, drop_id, drop_count)
        return True
    return False


def _apply_drop_restore_entry(client: Client, entry: dict, count: int) -> None:
    from src.orm.item import add_item
    from src.orm.resource import add_resource
    amount = entry.get("resource_num", 0) * count
    rtype = int(entry.get("type", 0))
    resource_type = int(entry.get("resource_type", 0))
    if rtype == DROP_TYPE_RESOURCE:
        add_resource(client.commander.commander_id, resource_type, amount)
    elif rtype == DROP_TYPE_ITEM:
        add_item(client.commander.commander_id, resource_type, amount)
    elif rtype == DROP_TYPE_SHIP:
        for _ in range(amount):
            client.commander.add_ship(resource_type)
    elif rtype == DROP_TYPE_SKIN:
        for _ in range(amount):
            client.commander.give_skin(resource_type)


def _contains_uint32(lst: list, val: int) -> bool:
    return val in lst


def _new_drop_info(drop_type: int, drop_id: int, count: int) -> dict:
    return {"type": drop_type, "id": drop_id, "number": count}


def _parse_destroy_item_entries(raw) -> list[dict]:
    if raw is None:
        return []
    if isinstance(raw, str):
        if not raw.strip():
            return []
        raw = json.loads(raw)
    if not isinstance(raw, list):
        return []
    result = []
    for entry in raw:
        if isinstance(entry, list) and len(entry) >= 2:
            result.append({"id": int(entry[0]), "count": int(entry[1])})
    return result


def _normalize_usage_arg(raw):
    if raw is None:
        return raw
    if isinstance(raw, str):
        stripped = raw.strip()
        if stripped == "":
            return []
        try:
            return json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            return raw
    return raw


def _parse_display_icon(raw) -> list[dict]:
    entries = _normalize_usage_arg(raw)
    if not isinstance(entries, list):
        return []
    result = []
    for entry in entries:
        if isinstance(entry, list) and len(entry) >= 3:
            result.append({
                "type": int(entry[0]),
                "id": int(entry[1]),
                "count": int(entry[2]),
            })
    return result


def _filter_display_icons(entries: list[dict], has_gold: bool, has_oil: bool) -> list[dict]:
    if not has_gold and not has_oil:
        return entries
    filtered = []
    for entry in entries:
        if entry["type"] == DROP_TYPE_RESOURCE:
            if has_gold and entry["id"] == 1:
                continue
            if has_oil and entry["id"] == 2:
                continue
        filtered.append(entry)
    return filtered


def _select_drop_option(options: list, arg: list) -> Optional[list]:
    if not options:
        return None
    if len(arg) >= 3:
        for option in options:
            if not isinstance(option, list) or len(option) < 3:
                continue
            if (int(option[0]) == int(arg[0]) and
                int(option[1]) == int(arg[1]) and
                int(option[2]) == int(arg[2])):
                return option
        return None
    return options[0]


def _parse_skin_exchange_choices(raw) -> list[int]:
    entries = _normalize_usage_arg(raw)
    if not isinstance(entries, list):
        return []
    choices = []
    for entry in entries:
        if isinstance(entry, list):
            choices.extend(int(x) for x in entry)
    return choices


def _parse_random_skin_choices(raw) -> list[int]:
    entries = _normalize_usage_arg(raw)
    if not isinstance(entries, list) or len(entries) < 3:
        return []
    third = entries[2]
    if isinstance(third, list):
        return [int(x) for x in third]
    return []


def _parse_discount_args(raw) -> tuple[list[int], int]:
    entries = _normalize_usage_arg(raw)
    if not isinstance(entries, list):
        return [], 0
    allowed = []
    if len(entries) > 0:
        first = entries[0]
        if isinstance(first, list):
            allowed = [int(x) for x in first]
        else:
            try:
                allowed = [int(first)]
            except (ValueError, TypeError):
                pass
    discount = 0
    if len(entries) > 1:
        try:
            discount = int(entries[1])
        except (ValueError, TypeError):
            pass
    return allowed, discount
