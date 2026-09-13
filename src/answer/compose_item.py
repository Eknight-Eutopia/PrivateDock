from typing import Optional

from src.connection.client import Client
from src.db.store import get_default_store, NotFoundError
from src.protobuf import protobuf
from src.orm.config_entry import afetch_config_entry_data

ITEM_DATA_STATISTICS_CATEGORY = "sharecfgdata/item_data_statistics.json"
COMPOSE_ITEM_RESPONSE_ID = 15007


async def _load_item_compose_config(item_id: int) -> Optional[dict]:
    try:
        return await afetch_config_entry_data(ITEM_DATA_STATISTICS_CATEGORY, item_id)
    except Exception:
        return None


async def _load_commander_item_counts(commander_id: int, item_id: int) -> tuple[int, int]:
    store = get_default_store()
    if store is None:
        return 0, 0

    from src.orm.item import get_commander_item_count
    try:
        items_count = get_commander_item_count(commander_id, item_id)
    except Exception:
        items_count = 0

    misc_count = 0
    try:
        row = await store.afetchrow(
            "SELECT data FROM commander_misc_items WHERE commander_id = $1 AND item_id = $2",
            commander_id, item_id,
        )
        if row is not None:
            misc_count = row["data"]
    except Exception:
        pass

    return items_count, misc_count


async def handle_compose_item(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_15006()
    payload.ParseFromString(buffer)
    response = protobuf.SC_15007(result=1)

    item_id = payload.id
    num = payload.num
    if item_id == 0 or num == 0:
        await client.send_message(COMPOSE_ITEM_RESPONSE_ID, response)
        return 0, COMPOSE_ITEM_RESPONSE_ID, None

    if getattr(client.commander, "commander_items_map", None) is None or getattr(client.commander, "misc_items_map", None) is None:
        try:
            client.commander.load()
        except Exception as e:
            return 0, COMPOSE_ITEM_RESPONSE_ID, e

    config = await _load_item_compose_config(item_id)
    if config is None or not config.get("compose_number") or not config.get("target_id"):
        await client.send_message(COMPOSE_ITEM_RESPONSE_ID, response)
        return 0, COMPOSE_ITEM_RESPONSE_ID, None

    compose_number = int(config["compose_number"])
    target_id = int(config["target_id"])
    required = num * compose_number
    if required == 0:
        await client.send_message(COMPOSE_ITEM_RESPONSE_ID, response)
        return 0, COMPOSE_ITEM_RESPONSE_ID, None

    items_count, misc_count = await _load_commander_item_counts(client.commander.commander_id, item_id)
    if items_count + misc_count < required:
        await client.send_message(COMPOSE_ITEM_RESPONSE_ID, response)
        return 0, COMPOSE_ITEM_RESPONSE_ID, None

    consume_items = min(items_count, required)
    consume_misc = required - consume_items

    store = get_default_store()
    if store is None:
        return 0, COMPOSE_ITEM_RESPONSE_ID, RuntimeError("DB not initialized")

    try:
        if consume_items > 0:
            result = await store.aexecute(
                """UPDATE commander_items
                   SET count = count - $3
                   WHERE commander_id = $1 AND item_id = $2 AND count >= $3""",
                client.commander.commander_id, item_id, consume_items,
            )
            if result == "0":
                raise NotFoundError("not enough items")

        if consume_misc > 0:
            result = await store.aexecute(
                """UPDATE commander_misc_items
                   SET data = data - $3
                   WHERE commander_id = $1 AND item_id = $2 AND data >= $3""",
                client.commander.commander_id, item_id, consume_misc,
            )
            if result == "0":
                raise NotFoundError("not enough misc items")

        from src.orm.item import add_item
        add_item(client.commander.commander_id, target_id, num)
    except NotFoundError:
        await client.send_message(COMPOSE_ITEM_RESPONSE_ID, response)
        return 0, COMPOSE_ITEM_RESPONSE_ID, None
    except Exception as e:
        return 0, COMPOSE_ITEM_RESPONSE_ID, e

    if consume_items > 0:
        items_map = getattr(client.commander, "commander_items_map", {})
        if item_id in items_map:
            items_map[item_id]["count"] = max(0, items_map[item_id].get("count", 0) - consume_items)

    if consume_misc > 0:
        misc_map = getattr(client.commander, "misc_items_map", {})
        if item_id in misc_map:
            misc_map[item_id]["data"] = max(0, misc_map[item_id].get("data", 0) - consume_misc)

    items_map = getattr(client.commander, "commander_items_map", {})
    if target_id in items_map:
        items_map[target_id]["count"] = items_map[target_id].get("count", 0) + num
    else:
        items_map[target_id] = {"commander_id": client.commander.commander_id, "item_id": target_id, "count": num}

    response.result = 0
    await client.send_message(COMPOSE_ITEM_RESPONSE_ID, response)
    return 0, COMPOSE_ITEM_RESPONSE_ID, None
