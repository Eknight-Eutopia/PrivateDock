import asyncio
import random
from typing import Optional

from src.answer.item_usage import _TECH_PACK_DROPS
from src.connection.client import Client
from src.orm import add_resource, add_item
from src.protobuf import protobuf


def handle_quick_exchange_blueprint(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    import json
    payload = json.loads(buffer.decode("utf-8", errors="replace"))

    use_list = payload.get("use_list", [])
    resp = protobuf.SC_15013()
    for entry in use_list:
        ret = protobuf.SC_15003(result=1)
        try:
            outcome = _use_item(client, entry)
            if outcome is not None:
                ret.result = outcome.get("result", 1)
                for d in outcome.get("drop_list", []):
                    ret.drop_list.append(protobuf.DROPINFO(type=d["type"], id=d["id"], number=d["number"]))
        except Exception:
            pass
        resp.ret_list.append(ret)

    asyncio.create_task(client.send_message(15013, resp))
    return 0, 15013, None


def _use_item(client, item_entry: dict) -> Optional[dict]:
    from src.orm.item import get_commander_item_count

    item_id = item_entry.get("id", 0)
    count = item_entry.get("count", 0)
    if count == 0:
        return {"result": 1, "drop_list": []}

    available = get_commander_item_count(client.commander.commander_id, item_id)
    if available < count:
        return {"result": 1, "drop_list": []}

    from src.orm.config_entry import fetch_config_entry_data
    config = None
    for category in ['sharecfgdata/item_data_statistics.json', 'sharecfgdata/item_virtual_data_statistics.json']:
        data = fetch_config_entry_data(category, item_id)
        if isinstance(data, dict):
            config = data
            break
    if config is None:
        return {"result": 1, "drop_list": []}

    usage = config.get("usage", "")
    usage_arg = config.get("usage_arg", [])
    arg = item_entry.get("arg", [])

    plan = None
    if usage == "usage_drop":
        plan = _prepare_drop_usage(client, config, count)
    elif usage == "usage_drop_template":
        plan = _prepare_drop_template_usage(client, config, count)
    elif usage == "usage_drop_appointed":
        plan = _prepare_drop_appointed_usage(client, config, arg, count)
    elif usage in ("usage_skin_discount", "usage_shop_discount"):
        plan = _prepare_skin_discount_usage(client, config, arg, count)
    else:
        # Fallback: if display_icon has entries, treat as random drops
        di = config.get("display_icon")
        if di and isinstance(di, list) and len(di) > 0:
            plan = _prepare_display_icon_drops(client, config, count)
        else:
            _consume_commander_item(client, item_id, count)
            return {"result": 0, "drop_list": []}

    if plan is None or plan.get("result", 1) != 0:
        return plan

    _consume_commander_item(client, item_id, count)
    apply = plan.get("_apply")
    if apply:
        apply()

    return {"result": 0, "drop_list": plan.get("drop_list", [])}


def _consume_commander_item(client, item_id: int, count: int) -> None:
    from src.orm.item import consume_commander_item
    consume_commander_item(client.commander, item_id, count)
    items_map = getattr(client.commander, "commander_items_map", {})
    if item_id in items_map:
        entry = items_map[item_id]
        entry["count"] = max(0, entry.get("count", 0) - count)


def _prepare_drop_usage(client, config: dict, count: int) -> dict:
    import json
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
        all_entries = list_config_entries_sync("ShareCfg/drop_data_restore.json") or []
        entries = []
        for e in all_entries:
            data = e.data if isinstance(e.data, dict) else json.loads(e.data) if isinstance(e.data, str) else {}
            try:
                did = int(data.get("drop_id", 0))
            except (ValueError, TypeError):
                continue
            if did == drop_id:
                entries.append(data)
        if entries:
            drops = [{"type": 13, "id": e.get("id", 0), "number": count} for e in entries]
            return {"result": 0, "drop_list": drops, "_apply": lambda: _apply_restore_entries(client, entries, count)}

    # Tech pack drops: add random equipment to owned_equipments
    item_id = config.get("id", 0)
    if item_id and item_id in _TECH_PACK_DROPS:
        pool = _TECH_PACK_DROPS[item_id]
        chosen = [pool[random.randint(0, len(pool) - 1)] for _ in range(count)]
        drops = {}
        for eid in chosen:
            key = f"3_{eid}"
            if key in drops:
                drops[key]["number"] += 1
            else:
                drops[key] = {"type": 3, "id": eid, "number": 1}
        def _apply_tech():
            from src.orm.owned_equipment import add_owned_equipment
            for eid in chosen:
                add_owned_equipment(client.commander.commander_id, eid, 1)
        return {"result": 0, "drop_list": list(drops.values()), "_apply": _apply_tech}

    return {"result": 1, "drop_list": []}


def _prepare_drop_template_usage(client, config: dict, count: int) -> dict:
    args = config.get("usage_arg", [])
    if isinstance(args, (int, float)):
        args = [args]
    if not isinstance(args, list) or len(args) < 3:
        return {"result": 1, "drop_list": []}
    gold = args[1] * count
    oil = args[2] * count
    drops = []
    if gold > 0:
        drops.append({"type": 1, "id": 1, "number": gold})
    if oil > 0:
        drops.append({"type": 1, "id": 2, "number": oil})

    def _apply():
        if gold > 0:
            add_resource(client.commander, 1, gold)
        if oil > 0:
            add_resource(client.commander, 2, oil)

    return {"result": 0, "drop_list": drops, "_apply": _apply}


def _prepare_drop_appointed_usage(client, config: dict, arg: list, count: int) -> dict:
    options = config.get("usage_arg", [])
    if not options:
        return {"result": 1, "drop_list": []}
    selection = None
    if len(arg) >= 3:
        for opt in options:
            if len(opt) >= 3 and opt[0] == arg[0] and opt[1] == arg[1] and opt[2] == arg[2]:
                selection = opt
                break
    if selection is None and options:
        selection = options[0]
    if not selection or len(selection) < 3:
        return {"result": 1, "drop_list": []}
    drop_type, drop_id, drop_count = selection[0], selection[1], selection[2] * count

    def _apply():
        if drop_type == 1:
            add_resource(client.commander, drop_id, drop_count)
        elif drop_type == 2:
            add_item(client.commander, drop_id, drop_count)

    return {"result": 0, "drop_list": [{"type": drop_type, "id": drop_id, "number": drop_count}], "_apply": _apply}


def _prepare_skin_discount_usage(_client, _config: dict, arg: list, _count: int) -> dict:
    if not arg:
        return {"result": 1, "drop_list": []}
    shop_id = arg[0]
    return {"result": 0, "drop_list": [], "_apply": None}


def _prepare_display_icon_drops(client, config: dict, count: int) -> dict:
    di = config.get("display_icon")
    if not di or not isinstance(di, list) or len(di) == 0:
        return {"result": 1, "drop_list": []}
    entries = _parse_display_icon(di)
    if not entries:
        return {"result": 1, "drop_list": []}
    drops = {}
    for _ in range(count):
        entry = entries[random.randint(0, len(entries) - 1)]
        key = f"{entry['type']}_{entry['id']}"
        if key in drops:
            drops[key]["number"] += entry["count"]
        else:
            drops[key] = {"type": entry["type"], "id": entry["id"], "number": entry["count"]}
    def _apply():
        for drop in drops.values():
            if drop["type"] == 1:
                add_resource(client.commander, drop["id"], drop["number"])
            elif drop["type"] == 2:
                add_item(client.commander, drop["id"], drop["number"])
            elif drop["type"] == 4:
                for _ in range(drop["number"]):
                    client.commander.add_ship(drop["id"])
            elif drop["type"] == 7:
                for _ in range(drop["number"]):
                    client.commander.give_skin(drop["id"])
    return {"result": 0, "drop_list": list(drops.values()), "_apply": _apply}


def _parse_display_icon(raw) -> list[dict]:
    if raw is None:
        return []
    if isinstance(raw, str):
        if not raw.strip():
            return []
        import json
        raw = json.loads(raw)
    if not isinstance(raw, list):
        return []
    result = []
    for entry in raw:
        if isinstance(entry, list) and len(entry) >= 3:
            result.append({"type": int(entry[0]), "id": int(entry[1]), "count": int(entry[2])})
    return result


def _apply_restore_entries(client, entries: list, count: int) -> None:
    from src.orm.item import add_item
    from src.orm.resource import add_resource
    for entry in entries:
        amount = entry.get("resource_num", 0) * count
        rtype = entry.get("type", 0)
        resource_type = entry.get("resource_type", 0)
        if rtype == 1:
            add_resource(client.commander, resource_type, amount)
        elif rtype == 2:
            add_item(client.commander, resource_type, amount)
