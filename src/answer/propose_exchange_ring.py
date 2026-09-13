import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

VOW_PROP_CONVERSION_CATEGORY = "ShareCfg/gameset.json"
VOW_PROP_CONVERSION_KEY = "vow_prop_conversion"


def _send_vow_result(client, result: int):
    asyncio.create_task(client.send_message(15011, protobuf.SC_15011(result=result)))


def handle_propose_exchange_ring(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    import json
    payload = json.loads(buffer.decode("utf-8", errors="replace"))

    _ = payload.get("id", 0)

    try:
        from src.orm.config_entry import get_config_entry
        raw = get_config_entry(VOW_PROP_CONVERSION_CATEGORY, VOW_PROP_CONVERSION_KEY)
        if raw is None:
            _send_vow_result(client, 1)
            return 0, 15011, None
        config = raw if isinstance(raw, dict) else json.loads(raw) if isinstance(raw, str) else raw
        desc = config.get("description", [])
        if len(desc) != 2:
            _send_vow_result(client, 1)
            return 0, 15011, None
        from_item_id, to_item_id = desc[0], desc[1]
    except Exception:
        _send_vow_result(client, 1)
        return 0, 15011, None

    try:
        from src.orm.item import consume_item, add_item
        consume_item(client.commander, from_item_id, 1)
        add_item(client.commander, to_item_id, 1)
    except Exception:
        _send_vow_result(client, 1)
        return 0, 15011, None

    _send_vow_result(client, 0)
    return 0, 15011, None
