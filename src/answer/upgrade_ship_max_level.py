import asyncio
import json
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def _load_ship_level_config(level: int) -> Optional[dict]:
    if level == 0:
        return None
    from src.orm.config_entry import fetch_config_entry_data
    cfg = fetch_config_entry_data("ShareCfg/ship_level.json", level)
    if cfg is None:
        cfg = fetch_config_entry_data("sharecfgdata/ship_level.json", level)
    return cfg if isinstance(cfg, dict) else None


def _find_next_ship_max_level(current_max_level: int) -> int:
    for level in range(current_max_level + 1, 201):
        entry = _load_ship_level_config(level)
        if entry is None:
            return 0
        if entry.get("level_limit") == 1:
            return level
    return 0


def _get_ship_rarity(owned, template_id: int) -> int:
    if isinstance(owned, dict) and "rarity" in owned:
        return int(owned["rarity"])
    ship_obj = getattr(owned, "ship", None)
    if ship_obj is not None:
        r = getattr(ship_obj, "rarity_id", getattr(ship_obj, "rarity", None))
        if r is not None:
            return int(r)
    from src.orm.config_entry import fetch_config_entry_data
    cfg = fetch_config_entry_data("sharecfgdata/ship_data_statistics.json", template_id)
    if cfg is None:
        cfg = fetch_config_entry_data("ShareCfg/ship_data_statistics.json", template_id)
    if cfg and "rarity" in cfg:
        try:
            return int(cfg["rarity"])
        except (ValueError, TypeError):
            return 0
    return 0


def _ship_max_level_upgrade_requirements(current_max_level: int, rarity: int) -> list[dict]:
    root = _load_ship_level_config(current_max_level)
    if root is None:
        return []
    key = f"need_item_rarity{rarity}"
    raw = root.get(key)
    if raw is None:
        return []
    tuples = raw if isinstance(raw, list) else json.loads(raw)
    reqs = []
    for tup in tuples:
        if len(tup) < 3:
            raise ValueError("invalid ship_level need_item_rarity tuple")
        reqs.append({"drop_type": tup[0], "id": tup[1], "count": tup[2]})
    return reqs


def _has_max_level_upgrade_requirements(commander, reqs: list[dict]) -> bool:
    for req in reqs:
        count = req.get("count", 0)
        if count == 0:
            continue
        drop_type = req.get("drop_type")
        res_or_item_id = req.get("id")
        if drop_type == 1:
            if not commander.has_enough_resource(res_or_item_id, count):
                return False
        elif drop_type == 2:
            if not commander.has_enough_item(res_or_item_id, count):
                return False
        else:
            return False
    return True


def _consume_max_level_upgrade_requirements(commander, reqs: list[dict]) -> None:
    for req in reqs:
        count = req.get("count", 0)
        if count == 0:
            continue
        drop_type = req.get("drop_type")
        res_or_item_id = req.get("id")
        if drop_type == 1:
            commander.consume_resource(res_or_item_id, count)
        elif drop_type == 2:
            commander.consume_item(res_or_item_id, count)
        else:
            raise ValueError(f"unsupported requirement type {drop_type}")


def _convert_surplus_exp_after_max_level_increase(owned, next_max_level: int, rarity: int = 0):
    level = owned["level"] if isinstance(owned, dict) else getattr(owned, "level", 0)
    cur_exp = owned["exp"] if isinstance(owned, dict) else getattr(owned, "exp", 0)
    surplus_exp = owned.get("surplus_exp", 0) if isinstance(owned, dict) else getattr(owned, "surplus_exp", 0)
    exp = cur_exp + surplus_exp
    surplus = 0

    while level < next_max_level:
        config = _load_ship_level_config(level)
        if config is None:
            break
        required = config.get("exp_ur", config.get("exp", 0)) if rarity >= 6 else config.get("exp", 0)
        if required == 0 or exp < required:
            break
        exp -= required
        level += 1

    if level >= next_max_level and next_max_level >= 100 and exp > 0:
        from src.answer.event_finish import _add_surplus_exp
        surplus = _add_surplus_exp(0, exp)
        exp = 0

    return level, exp, surplus


def _send_max_level_result(client, result: int):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(client.send_message(12039, protobuf.SC_12039(result=result)))
    except RuntimeError:
        res = client.send_message(12039, protobuf.SC_12039(result=result))
        if asyncio.iscoroutine(res):
            res.close()


def handle_upgrade_ship_max_level(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    ship_id = 0
    try:
        payload = protobuf.CS_12038.FromString(buffer)
        ship_id = payload.ship_id
    except Exception:
        try:
            payload = json.loads(buffer.decode("utf-8", errors="replace"))
            ship_id = payload.get("ship_id", 0) if isinstance(payload, dict) else 0
        except Exception as e:
            return 0, 12038, e

    if not ship_id:
        _send_max_level_result(client, 1)
        return 0, 12039, None

    owned = client.commander.owned_ships_map.get(ship_id)
    if owned is None:
        _send_max_level_result(client, 1)
        return 0, 12039, None

    level = owned["level"] if isinstance(owned, dict) else getattr(owned, "level", 0)
    max_level = owned["max_level"] if isinstance(owned, dict) else getattr(owned, "max_level", 0)
    owned_id = owned["id"] if isinstance(owned, dict) else getattr(owned, "id", ship_id)
    template_id = owned["ship_id"] if isinstance(owned, dict) else getattr(owned, "ship_id", 0)

    if level != max_level or max_level < 100:
        _send_max_level_result(client, 1)
        return 0, 12039, None

    try:
        next_max_level = _find_next_ship_max_level(max_level)
    except Exception as e:
        return 0, 12038, e

    if next_max_level == 0:
        _send_max_level_result(client, 1)
        return 0, 12039, None

    rarity = _get_ship_rarity(owned, template_id)
    try:
        reqs = _ship_max_level_upgrade_requirements(max_level, rarity)
    except Exception as e:
        return 0, 12038, e

    if not reqs:
        _send_max_level_result(client, 1)
        return 0, 12039, None

    if not _has_max_level_upgrade_requirements(client.commander, reqs):
        _send_max_level_result(client, 1)
        return 0, 12039, None

    try:
        new_level, new_exp, new_surplus = _convert_surplus_exp_after_max_level_increase(
            owned, next_max_level, rarity
        )
    except Exception as e:
        return 0, 12038, e

    try:
        _consume_max_level_upgrade_requirements(client.commander, reqs)
        from src.orm.owned_ship import update_owned_ship
        update_owned_ship(
            client.commander,
            owned_id,
            max_level=next_max_level,
            level=new_level,
            exp=new_exp,
            surplus_exp=new_surplus,
        )
    except Exception as e:
        return 0, 12038, e

    if isinstance(owned, dict):
        owned["max_level"] = next_max_level
        owned["level"] = new_level
        owned["exp"] = new_exp
        owned["surplus_exp"] = new_surplus
    else:
        owned.max_level = next_max_level
        owned.level = new_level
        owned.exp = new_exp
        owned.surplus_exp = new_surplus

    ships = getattr(client.commander, "ships", None)
    if ships:
        for s in ships:
            if getattr(s, "id", None) == owned_id:
                s.max_level = next_max_level
                s.level = new_level
                s.exp = new_exp
                s.surplus_exp = new_surplus
                break

    _send_max_level_result(client, 0)
    try:
        from src.answer.task_handlers import schedule_emit, schedule_possession_sync
        schedule_emit(client, 83, 0, 10000)
        schedule_possession_sync(client)
    except Exception:
        pass
    return 0, 12039, None
