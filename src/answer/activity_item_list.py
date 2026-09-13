import asyncio
import json
from typing import Optional

from src.connection.client import Client
from src.connection.server import send_proto_message
from src.protobuf import protobuf

ACTIVITY_ITEM_RESULT_SUCCESS = 0
ACTIVITY_ITEM_RESULT_FAILURE = 1


def _collect_uint32_values(value, out: list) -> list:
    if isinstance(value, (int, float)):
        if value > 0:
            out.append(int(value))
    elif isinstance(value, str):
        try:
            parsed = int(value)
            if parsed > 0:
                out.append(parsed)
        except (ValueError, TypeError):
            pass
    elif isinstance(value, list):
        for item in value:
            out = _collect_uint32_values(item, out)
    elif isinstance(value, dict):
        for item in value.values():
            out = _collect_uint32_values(item, out)
    return out


def _collect_activity_scoped_item_ids(template) -> list:
    raw_parts = []
    if template.config_data is not None:
        try:
            data = json.loads(template.config_data) if isinstance(template.config_data, str) else template.config_data
            raw_parts.append(data)
        except (json.JSONDecodeError, TypeError):
            pass
    if template.config_client is not None:
        try:
            data = json.loads(template.config_client) if isinstance(template.config_client, str) else template.config_client
            raw_parts.append(data)
        except (json.JSONDecodeError, TypeError):
            pass

    ids = []
    for value in raw_parts:
        ids = _collect_uint32_values(value, ids)

    seen = set()
    result = []
    for aid in ids:
        if aid > 0 and aid not in seen:
            seen.add(aid)
            result.append(aid)
    result.sort()
    return result


def _build_activity_item_list(balances: dict) -> list:
    item_ids = sorted(
        item_id for item_id, count in balances.items() if count > 0
    )
    result = []
    for item_id in item_ids:
        entry = protobuf.PB_ACTIVITY_ITEM()
        entry.id = item_id
        entry.num = balances[item_id]
        result.append(entry)
    return result


def handle_activity_item_list(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_26106()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 26107, e

    act_id = payload.act_id
    response = protobuf.SC_26107(ret=ACTIVITY_ITEM_RESULT_FAILURE)

    from src.answer.activity_templates import load_activity_template
    template = load_activity_template(act_id)
    if template is None:
        asyncio.create_task(send_proto_message(26107, client, response))
        return 0, 26107, None

    item_ids = _collect_activity_scoped_item_ids(template)

    from src.orm.commander_item import list_commander_item_balances
    try:
        balances = list_commander_item_balances(client.commander.commander_id, item_ids)
    except Exception:
        asyncio.create_task(send_proto_message(26107, client, response))
        return 0, 26107, None

    response.ret = ACTIVITY_ITEM_RESULT_SUCCESS
    for item in _build_activity_item_list(balances):
        response.item_list.append(item)
    asyncio.create_task(send_proto_message(26107, client, response))
    return 0, 26107, None
