import asyncio
import json
from typing import Optional

from src.connection.client import Client

REVERT_EQUIPMENT_ITEM_ID = 15007


def handle_revert_equipment(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 14011
    payload = json.loads(buffer.decode("utf-8", errors="replace"))

    response = {"result": 0}
    equip_id = payload.get("equip_id", 0)

    if equip_id == 0:
        response["result"] = 1
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    owned = client.commander.get_owned_equipment(equip_id)
    if owned is None or (owned.get("count", 0) if isinstance(owned, dict) else getattr(owned, "count", 0)) == 0:
        response["result"] = 1
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    if not client.commander.has_enough_item(REVERT_EQUIPMENT_ITEM_ID, 1):
        response["result"] = 1
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    root_equip_id, refund_items, refund_coins, ok, err = _compute_revert_equipment_refunds(equip_id)
    if err is not None:
        response["result"] = 1
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, err

    if not ok:
        response["result"] = 1
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    try:
        client.commander.consume_item(REVERT_EQUIPMENT_ITEM_ID, 1)
        client.commander.remove_owned_equipment(equip_id, 1)
        client.commander.add_owned_equipment(root_equip_id, 1)
        for item_id, count in refund_items.items():
            client.commander.add_item(item_id, count)
        if refund_coins != 0:
            client.commander.add_resource(1, refund_coins)
    except Exception:
        response["result"] = 1
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def _compute_revert_equipment_refunds(equip_id: int) -> tuple:
    current = _load_equipment_config(equip_id)
    if current is None:
        return 0, {}, 0, False, ValueError(f"equipment config not found for {equip_id}")

    if isinstance(current, dict):
        prev = current.get("prev", 0)
        level = current.get("level", 0)
    else:
        prev = getattr(current, "prev", 0)
        level = getattr(current, "level", 0)

    if prev == 0 or level <= 1:
        return 0, {}, 0, False, None

    refund_items = {}
    refund_coins = 0
    current = _load_equipment_config(equip_id)

    while True:
        if isinstance(current, dict):
            prev_id = current.get("prev", 0)
        else:
            prev_id = getattr(current, "prev", 0)

        if prev_id == 0:
            break

        prev_config = _load_equipment_config(prev_id)
        if prev_config is None:
            return 0, {}, 0, False, ValueError(f"equipment config not found for {prev_id}")

        if isinstance(prev_config, dict):
            refund_coins += prev_config.get("trans_use_gold", 0)
            trans_use_item = prev_config.get("trans_use_item", [])
        else:
            refund_coins += getattr(prev_config, "trans_use_gold", 0)
            trans_use_item = getattr(prev_config, "trans_use_item", [])

        _add_trans_use_items(refund_items, trans_use_item)
        current = prev_config

    if isinstance(current, dict):
        root_id = current.get("id", 0)
    else:
        root_id = getattr(current, "id", 0)

    return root_id, refund_items, refund_coins, True, None


def _load_equipment_config(equip_id: int) -> Optional[dict]:
    from src.orm.config_entry import get_config_entry
    import json
    try:
        entry = get_config_entry("sharecfgdata/equip_data_statistics.json", str(equip_id))
        data = entry.data if isinstance(entry.data, str) else json.dumps(entry.data)
        return json.loads(data)
    except Exception:
        return None


def _add_trans_use_items(refund_items: dict, trans_use_items: list) -> None:
    for item in trans_use_items:
        if len(item) < 2:
            continue
        item_id = item[0]
        count = item[1]
        refund_items[item_id] = refund_items.get(item_id, 0) + count
