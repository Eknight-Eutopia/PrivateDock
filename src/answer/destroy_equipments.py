import json
from typing import Optional

from src.connection.client import Client
from src.db.store import get_default_store
from src.protobuf import protobuf

DESTROY_EQUIPMENT_RESPONSE_ID = 14009
DE_RESULT_OK = 0
DE_RESULT_FAILURE = 1
DE_RESULT_NOT_ENOUGH = 2
DE_RESULT_UNKNOWN_EQUIP = 3


def _parse_destroy_equipment_items(raw) -> dict[int, int]:
    if not raw:
        return {}
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, list):
        return {}
    out = {}
    for pair in raw:
        if not isinstance(pair, list) or len(pair) != 2:
            continue
        item_id = pair[0]
        count = pair[1]
        if item_id == 0 or count == 0:
            continue
        out[item_id] = out.get(item_id, 0) + count
    return out


async def handle_destroy_equipments(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_14008()
    payload.ParseFromString(buffer)

    if not payload.equip_list:
        await client.send_message(DESTROY_EQUIPMENT_RESPONSE_ID, protobuf.SC_14009(result=DE_RESULT_FAILURE))
        return 0, DESTROY_EQUIPMENT_RESPONSE_ID, None

    if getattr(client.commander, "owned_equipment_map", None) is None or getattr(client.commander, "owned_resources_map", None) is None or getattr(client.commander, "commander_items_map", None) is None or getattr(client.commander, "misc_items_map", None) is None:
        try:
            client.commander.load()
        except Exception as e:
            await client.send_message(DESTROY_EQUIPMENT_RESPONSE_ID, protobuf.SC_14009(result=DE_RESULT_FAILURE))
            return 0, DESTROY_EQUIPMENT_RESPONSE_ID, e

    equipment_counts = {}
    for entry in payload.equip_list:
        equipment_id = entry.id
        count = entry.count
        if equipment_id == 0 or count == 0:
            await client.send_message(DESTROY_EQUIPMENT_RESPONSE_ID, protobuf.SC_14009(result=DE_RESULT_FAILURE))
            return 0, DESTROY_EQUIPMENT_RESPONSE_ID, None
        equipment_counts[equipment_id] = equipment_counts.get(equipment_id, 0) + count

    store = get_default_store()
    if store is None:
        return 0, DESTROY_EQUIPMENT_RESPONSE_ID, RuntimeError("DB not initialized")

    total_gold = 0
    items = {}

    for equipment_id, count in equipment_counts.items():
        owned_map = getattr(client.commander, "owned_equipment_map", {})
        owned = owned_map.get(equipment_id)
        if owned is None or owned.get("count", 0) < count:
            await client.send_message(DESTROY_EQUIPMENT_RESPONSE_ID, protobuf.SC_14009(result=DE_RESULT_NOT_ENOUGH))
            return 0, DESTROY_EQUIPMENT_RESPONSE_ID, None

        try:
            row = await store.afetchrow(
                "SELECT destroy_gold, destroy_item FROM equipments WHERE id = $1",
                equipment_id,
            )
        except Exception:
            row = None
        if row is None:
            await client.send_message(DESTROY_EQUIPMENT_RESPONSE_ID, protobuf.SC_14009(result=DE_RESULT_UNKNOWN_EQUIP))
            return 0, DESTROY_EQUIPMENT_RESPONSE_ID, None

        destroy_gold = row["destroy_gold"] or 0
        destroy_item_raw = row["destroy_item"]

        total_gold += destroy_gold * count

        rewards = _parse_destroy_equipment_items(destroy_item_raw)
        for item_id, per in rewards.items():
            items[item_id] = items.get(item_id, 0) + per * count

    try:
        for equipment_id, count in equipment_counts.items():
            result = await store.aexecute(
                """UPDATE owned_equipments
                   SET count = count - $3
                   WHERE commander_id = $1 AND equipment_id = $2 AND count >= $3""",
                client.commander.commander_id, equipment_id, count,
            )
            if result == "0":
                raise RuntimeError("not enough equipment")

            result = await store.afetchval(
                "SELECT count FROM owned_equipments WHERE commander_id = $1 AND equipment_id = $2",
                client.commander.commander_id, equipment_id,
            )
            if result is not None and result == 0:
                await store.aexecute(
                    "DELETE FROM owned_equipments WHERE commander_id = $1 AND equipment_id = $2",
                    client.commander.commander_id, equipment_id,
                )

        if total_gold > 0:
            from src.orm.resource import add_resource
            add_resource(client.commander.commander_id, 1, total_gold)

        from src.orm.item import add_item
        for item_id, item_count in items.items():
            if item_count == 0:
                continue
            add_item(client.commander.commander_id, item_id, item_count)
    except Exception:
        await client.send_message(DESTROY_EQUIPMENT_RESPONSE_ID, protobuf.SC_14009(result=DE_RESULT_FAILURE))
        return 0, DESTROY_EQUIPMENT_RESPONSE_ID, None

    for equipment_id, count in equipment_counts.items():
        owned_map = getattr(client.commander, "owned_equipment_map", {})
        if equipment_id in owned_map:
            owned_map[equipment_id]["count"] = max(0, owned_map[equipment_id].get("count", 0) - count)
            if owned_map[equipment_id]["count"] == 0:
                del owned_map[equipment_id]

    if total_gold > 0:
        res_map = getattr(client.commander, "owned_resources_map", {})
        if 1 in res_map:
            res_map[1]["amount"] = res_map[1].get("amount", 0) + total_gold
        else:
            res_map[1] = {"commander_id": client.commander.commander_id, "resource_id": 1, "amount": total_gold}

    for item_id, item_count in items.items():
        if item_count == 0:
            continue
        items_map = getattr(client.commander, "commander_items_map", {})
        if item_id in items_map:
            items_map[item_id]["count"] = items_map[item_id].get("count", 0) + item_count
        else:
            items_map[item_id] = {"commander_id": client.commander.commander_id, "item_id": item_id, "count": item_count}

    # Akashi's Commission 4 "Tidy up storage *Nyaa*! (Recycle gear)" is
    # sub_type 41 (30=build ship, 41=destroy gear, 42=compose gear) — the
    # client does not report this event itself (no CS_20016 on 14008), so the
    # server must emit it here for the task to progress.
    from src.answer import schedule_emit
    schedule_emit(client, 41, 0, sum(equipment_counts.values()))

    await client.send_message(DESTROY_EQUIPMENT_RESPONSE_ID, protobuf.SC_14009(result=DE_RESULT_OK))
    return 0, DESTROY_EQUIPMENT_RESPONSE_ID, None
