import asyncio
import json
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def _load_ship_level_config_raw(level: int):
    if level == 0:
        return None
    from src.orm.config_entry import get_config_entry
    try:
        entry = get_config_entry("ShareCfg/ship_level.json", str(level))
        return entry.data
    except LookupError:
        return None


def _find_next_ship_max_level(current_max_level: int) -> int:
    for level in range(current_max_level + 1, 201):
        data = _load_ship_level_config_raw(level)
        if data is None:
            return 0
        entry = json.loads(data) if isinstance(data, (bytes, bytearray)) else data
        if entry.get("level_limit") == 1:
            return level
    return 0


def _ship_max_level_upgrade_requirements(current_max_level: int, rarity: int) -> list[dict]:
    data = _load_ship_level_config_raw(current_max_level)
    if data is None:
        return []
    root = json.loads(data) if isinstance(data, (bytes, bytearray)) else data
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
        if req["drop_type"] == 1:
            if not commander.has_enough_resource(req["id"], count):
                return False
        elif req["drop_type"] == 2:
            if not commander.has_enough_item(req["id"], count):
                return False
        else:
            return False
    return True


def _consume_max_level_upgrade_requirements(commander, reqs: list[dict]) -> None:
    from src.orm.item import consume_item
    from src.orm.resource import consume_resource
    for req in reqs:
        count = req.get("count", 0)
        if count == 0:
            continue
        if req["drop_type"] == 1:
            consume_resource(commander, req["id"], count)
        elif req["drop_type"] == 2:
            consume_item(commander, req["id"], count)
        else:
            raise ValueError(f"unsupported requirement type {req['drop_type']}")


def _convert_surplus_exp_after_max_level_increase(owned, next_max_level: int):
    level = owned.level
    exp = owned.exp + owned.surplus_exp
    surplus = 0

    while level < next_max_level:
        data = _load_ship_level_config_raw(level)
        if data is None:
            break
        config = json.loads(data) if isinstance(data, (bytes, bytearray)) else data
        required = config.get("exp", 0)
        if getattr(owned.ship, "rarity_id", None) == 6:
            required = config.get("exp_ur", required)
        if required == 0 or exp < required:
            break
        exp -= required
        level += 1

    if level >= next_max_level and next_max_level >= 100 and exp > 0:
        surplus = exp
        exp = 0

    return level, exp, surplus


def _send_max_level_result(client, result: int):
    asyncio.create_task(client.send_message(12039, protobuf.SC_12039(result=result)))


def handle_upgrade_ship_max_level(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = json.loads(buffer.decode("utf-8", errors="replace"))

    ship_id = payload.get("ship_id", 0)
    owned = client.commander.owned_ships_map.get(ship_id)
    if owned is None:
        _send_max_level_result(client, 1)
        return 0, 12039, None

    if owned.level != owned.max_level:
        _send_max_level_result(client, 1)
        return 0, 12039, None

    if owned.max_level < 100:
        _send_max_level_result(client, 1)
        return 0, 12039, None

    try:
        next_max_level = _find_next_ship_max_level(owned.max_level)
    except Exception as e:
        return 0, 12038, e

    if next_max_level == 0:
        _send_max_level_result(client, 1)
        return 0, 12039, None

    rarity = getattr(owned.ship, "rarity_id", 0)
    try:
        reqs = _ship_max_level_upgrade_requirements(owned.max_level, rarity)
    except Exception as e:
        return 0, 12038, e

    if not reqs:
        _send_max_level_result(client, 1)
        return 0, 12039, None

    if not _has_max_level_upgrade_requirements(client.commander, reqs):
        _send_max_level_result(client, 1)
        return 0, 12039, None

    try:
        new_level, new_exp, new_surplus = _convert_surplus_exp_after_max_level_increase(owned, next_max_level)
    except Exception as e:
        return 0, 12038, e

    try:
        _consume_max_level_upgrade_requirements(client.commander, reqs)
        from src.orm.owned_ship import update_owned_ship
        update_owned_ship(
            client.commander,
            owned.id,
            max_level=next_max_level,
            level=new_level,
            exp=new_exp,
            surplus_exp=new_surplus,
        )
    except Exception as e:
        return 0, 12038, e

    owned.max_level = next_max_level
    owned.level = new_level
    owned.exp = new_exp
    owned.surplus_exp = new_surplus

    _send_max_level_result(client, 0)
    try:
        from src.answer.task_handlers import schedule_emit, schedule_possession_sync
        schedule_emit(client, 83, 0, 10000)
        schedule_possession_sync(client)
    except Exception:
        pass
    return 0, 12039, None
