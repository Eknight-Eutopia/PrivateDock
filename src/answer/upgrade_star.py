import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


# Rarity lists each test ship (bulin) may limit break, matching the EN client
# `Ship.testShip` tables in model/vo/ship.lua (index into the list built from
# gameset test_ship_config_1/2/3):
#   config_1 -> {2,3,4}, config_2 -> {5}, config_3 -> {6}
_TEST_SHIP_RARITY_LISTS = (
    (2, 3, 4),
    (5,),
    (6,),
)


def _breakout_items(breakout) -> list[dict]:
    items = []
    for entry in getattr(breakout, "use_item", []) or []:
        if len(entry) < 2:
            raise ValueError("invalid breakout item entry")
        items.append({"id": entry[0], "count": entry[1]})
    return items


def _has_enough_breakout_items(commander, items: list[dict]) -> bool:
    for item in items:
        count = item.get("count", 0)
        if count == 0:
            continue
        if not commander.has_enough_item(item["id"], count):
            return False
    return True


def _load_test_ship_rarity_map() -> dict[int, tuple]:
    """Return {material_template_id: allowed_target_rarities} for the three
    test ships (bulins), read from gameset config_entries (test_ship_config_1/2/3).
    Mirrors the client: a bulin may only be used to limit break ships whose
    rarity is in its testShip list.
    """
    from src.orm.config_entry import get_config_entry_sync
    result: dict[int, tuple] = {}
    for idx, rarities in enumerate(_TEST_SHIP_RARITY_LISTS):
        entry = get_config_entry_sync("ShareCfg/gameset.json", f"test_ship_config_{idx + 1}")
        if entry is None:
            continue
        kv = entry.data.get("key_value")
        if kv:
            result[int(kv)] = rarities
    return result


def _get_ship_rarity(template_id: int) -> int:
    """Target ship's rarity from the ships game-data table (mirrors client
    `Ship.getConfig("rarity")` = ship_data_statistics.rarity).
    """
    from src.orm.ship import Ship
    from src.db.session import get_sync_session
    with get_sync_session() as session:
        row = session.get(Ship, template_id)
        return row.rarity_id if row is not None else 0


def _validate_breakout_materials(
    commander, ship_id: int, material_ids: list[int], group_type: int, target_rarity: int
) -> bool:
    test_ship_rarity = _load_test_ship_rarity_map()
    seen = set()
    for mat_id in material_ids:
        if mat_id == ship_id:
            return False
        if mat_id in seen:
            return False
        seen.add(mat_id)
        material = commander.owned_ships_map.get(mat_id)
        if material is None:
            return False
        from src.orm.owned_equipment import get_ship_template_config
        template = get_ship_template_config(material["ship_id"])
        if template["group_type"] == group_type:
            continue
        allowed_rarities = test_ship_rarity.get(material["ship_id"])
        if allowed_rarities and target_rarity in allowed_rarities:
            continue
        return False
    return True


def _send_star_result(client, result: int):
    asyncio.create_task(client.send_message(12028, protobuf.SC_12028(result=result)))


def handle_upgrade_star(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_12027.FromString(buffer)

    ship_id = payload.ship_id
    ship = client.commander.owned_ships_map.get(ship_id)
    if ship is None:
        _send_star_result(client, 1)
        return 0, 12028, None

    from src.orm.game_data import get_ship_breakout_config
    try:
        breakout = get_ship_breakout_config(ship["ship_id"])
    except Exception as e:
        return 0, 12027, e

    if breakout is None or breakout.breakout_id == 0:
        _send_star_result(client, 1)
        return 0, 12028, None

    if ship["level"] < breakout.level:
        _send_star_result(client, 1)
        return 0, 12028, None

    materials = list(payload.material_id_list)
    if breakout.use_char_num == 0:
        if len(materials) != 0:
            _send_star_result(client, 1)
            return 0, 12028, None
    elif len(materials) != breakout.use_char_num:
        _send_star_result(client, 1)
        return 0, 12028, None

    if len(materials) > 0:
        target_rarity = _get_ship_rarity(ship["ship_id"])
        if not _validate_breakout_materials(
            client.commander, ship["id"], materials, breakout.use_char, target_rarity
        ):
            _send_star_result(client, 1)
            return 0, 12028, None

    try:
        items = _breakout_items(breakout)
    except Exception as e:
        return 0, 12027, e

    if breakout.use_gold > 0 and not client.commander.has_enough_gold(breakout.use_gold):
        _send_star_result(client, 1)
        return 0, 12028, None

    if not _has_enough_breakout_items(client.commander, items):
        _send_star_result(client, 1)
        return 0, 12028, None

    from src.orm.owned_equipment import get_ship_template_config
    try:
        updated_template = get_ship_template_config(breakout.breakout_id)
    except Exception as e:
        return 0, 12027, e

    try:
        from src.orm.owned_ship import consume_mod_material_ships, update_owned_ship

        if breakout.use_gold > 0:
            client.commander.consume_resource(1, breakout.use_gold)

        for item in items:
            count = item.get("count", 0)
            if count == 0:
                continue
            client.commander.consume_item(item["id"], count)

        if len(materials) > 0:
            consume_mod_material_ships(client.commander, materials)

        update_owned_ship(
            client.commander,
            ship["id"],
            ship_id=breakout.breakout_id,
            max_level=updated_template["max_level"],
        )
    except Exception as e:
        return 0, 12027, e

    ship["ship_id"] = breakout.breakout_id
    ship["max_level"] = updated_template["max_level"]
    if len(materials) > 0:
        for mat_id in materials:
            client.commander.owned_ships_map.pop(mat_id, None)

    _send_star_result(client, 0)
    # Server-authoritative task progress: a limit break advances "Limit Break a
    # ship X times" (sub_type 32), "Possess 1 shipgirl at Limit Break stage X"
    # (sub_type 1027, state-based, recomputed by the possession sync) and the
    # possession sync also covers max_level-derived gates.
    try:
        from src.answer.task_handlers import schedule_emit, schedule_possession_sync
        schedule_emit(client, 32, 0, 1)
        schedule_possession_sync(client)
    except Exception:
        pass
    return 0, 12028, None
