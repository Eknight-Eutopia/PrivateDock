import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

from src.consts.drop_types import (
    DROP_TYPE_RESOURCE,
    DROP_TYPE_ITEM,
    DROP_TYPE_SHIP,
    DROP_TYPE_SKIN,
    DROP_TYPE_FURNITURE,
    DROP_TYPE_VITEM,
    DROP_TYPE_EQUIP,
)
from src.connection.client import Client
from src.protobuf import protobuf

PACKET_ID = 16202

ERR_INVALID = 1
ERR_INSUFFICIENT = 2
ERR_LIMIT = 3
ERR_UNSUPPORTED = 4
ERR_DB_ERROR = 5


from src.orm.config_entry import entry_data as _unwrap


def _current_month_key() -> int:
    from src.shopreset.framework import monthly_window

    try:
        return monthly_window(datetime.now(timezone.utc)).key
    except Exception:
        now = datetime.now(timezone.utc)
        return now.year * 100 + now.month


def _build_drop(drop_type: int, drop_id: int, amount: int) -> protobuf.DROPINFO:
    d = protobuf.DROPINFO()
    d.type = drop_type
    d.id = drop_id
    d.number = amount
    return d


def _select_month_shop_template(entries: list) -> Optional[dict]:
    month = _current_month_key() % 100
    for entry in entries:
        if entry.get("id", 0) == month:
            return entry
    entries_sorted = sorted(entries, key=lambda x: x.get("id", 0))
    if not entries_sorted:
        return None
    index = (month - 1) % len(entries_sorted)
    return entries_sorted[index]


def _has_month_shop_content(entry: dict) -> bool:
    if entry.get("id", 0) != 0:
        return True
    fields = ["core_shop_goods", "blueprint_shop_goods", "blueprint_shop_limit_goods",
              "honormedal_shop_goods", "blueprint_shop_limit_goods_2", "blueprint_shop_goods_2",
              "blueprint_shop_limit_goods_3", "blueprint_shop_goods_3", "blueprint_shop_goods_4",
              "blueprint_shop_limit_goods_4"]
    return any(entry.get(f) for f in fields)


def _load_month_shop_template():
    from src.orm.config_entry import list_config_entries as _list
    entries = _list("ShareCfg/month_shop_template.json")
    if not entries:
        return None
    templates = []
    for entry_data in entries:
        d = _unwrap(entry_data)
        if isinstance(d, dict) and _has_month_shop_content(d):
            templates.append(d)
        elif isinstance(d, list):
            for item in d:
                if isinstance(item, dict) and _has_month_shop_content(item):
                    templates.append(item)
    if not templates:
        return None
    return _select_month_shop_template(templates)


def _month_shop_ids_by_type(template: dict, typ: int) -> list:
    if typ == 1:
        return template.get("core_shop_goods", []) or []
    elif typ == 2:
        ids = []
        for field in ["blueprint_shop_goods", "blueprint_shop_limit_goods",
                       "blueprint_shop_goods_2", "blueprint_shop_limit_goods_2",
                       "blueprint_shop_goods_3", "blueprint_shop_limit_goods_3",
                       "blueprint_shop_goods_4", "blueprint_shop_limit_goods_4"]:
            val = template.get(field, []) or []
            ids.extend(val)
        return ids
    elif typ == 3:
        return template.get("honormedal_shop_goods", []) or []
    return []


def _load_activity_shop_entry(goods_id: int) -> Optional[dict]:
    from src.orm.config_entry import get_config_entry as _get, list_config_entries as _list
    entry = _get("ShareCfg/activity_shop_template.json", str(goods_id))
    if entry is not None:
        data = _unwrap(entry)
        if isinstance(data, dict):
            return data
    for entry_data in _list("ShareCfg/activity_shop_template.json"):
        data = _unwrap(entry_data)
        if isinstance(data, dict) and data.get("id") == goods_id:
            return data
    return None


def _parse_timer_timestamp(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (ValueError, TypeError):
            pass
    return None


def _furniture_time_allows_purchase(time_data, now: datetime) -> bool:
    if not time_data:
        return True
    if isinstance(time_data, list) and len(time_data) == 2:
        start = _parse_timer_timestamp(time_data[0])
        end = _parse_timer_timestamp(time_data[1])
        if start is not None and end is not None:
            return start <= now <= end
    return True


def _load_furniture_shop_entry(goods_id: int) -> Optional[dict]:
    from src.orm.config_entry import get_config_entry as _get, list_config_entries as _list
    entry = _get("ShareCfg/furniture_shop_template.json", str(goods_id))
    if entry is not None:
        data = _unwrap(entry)
        if isinstance(data, dict):
            return data
    for entry_data in _list("ShareCfg/furniture_shop_template.json"):
        data = _unwrap(entry_data)
        if isinstance(data, dict) and data.get("id") == goods_id:
            return data
    return None


def _load_month_shop_good(goods_id: int) -> Optional[dict]:
    activity_entry = _load_activity_shop_entry(goods_id)
    if activity_entry is not None:
        return {
            "resource_category": activity_entry.get("resource_category", 0),
            "resource_type": activity_entry.get("resource_type", 0),
            "resource_num": activity_entry.get("resource_num", 0),
            "commodity_type": activity_entry.get("commodity_type", 0),
            "commodity_id": activity_entry.get("commodity_id", 0),
            "num": activity_entry.get("num", 0),
            "num_limit": activity_entry.get("num_limit", 0),
        }
    furniture_entry = _load_furniture_shop_entry(goods_id)
    if furniture_entry is not None:
        if not _furniture_time_allows_purchase(furniture_entry.get("time"), datetime.now(timezone.utc)):
            return None
        gem_price = furniture_entry.get("gem_price", 0) or 0
        dorm_icon_price = furniture_entry.get("dorm_icon_price", 0) or 0
        if gem_price > 0:
            currency = 14
            price = gem_price
        elif dorm_icon_price > 0:
            currency = 15
            price = dorm_icon_price
        else:
            return None
        return {
            "resource_category": DROP_TYPE_RESOURCE,
            "resource_type": currency,
            "resource_num": price,
            "commodity_type": DROP_TYPE_FURNITURE,
            "commodity_id": goods_id,
            "num": 1,
            "num_limit": 0,
        }
    return None


async def _do_purchase(client: Client, payload: protobuf.CS_16201):
    from src.orm import (
        get_month_shop_purchase_count,
        increment_month_shop_purchase,
        has_enough_resource,
        has_enough_item,
        consume_resource,
        consume_item,
        add_resource,
        add_item,
    )

    response = protobuf.SC_16202(result=0)
    count = payload.count
    if count == 0:
        response.result = 1
        await client.send_message(PACKET_ID, response)
        return

    goods_type = payload.type
    goods_id = payload.id

    template = _load_month_shop_template()
    if template is None:
        response.result = 1
        await client.send_message(PACKET_ID, response)
        return

    allowed_ids = _month_shop_ids_by_type(template, goods_type)
    if not allowed_ids or goods_id not in allowed_ids:
        response.result = 1
        await client.send_message(PACKET_ID, response)
        return

    good = _load_month_shop_good(goods_id)
    if good is None:
        response.result = 1
        await client.send_message(PACKET_ID, response)
        return

    total_cost = good["resource_num"] * count
    reward_amount = good["num"] * count

    drop = _build_drop(good["commodity_type"], good["commodity_id"], reward_amount)
    response.drop_list.append(drop)

    commander_id = client.commander.commander_id
    month_key = _current_month_key()

    try:
        if good["num_limit"] > 0:
            current_count = await get_month_shop_purchase_count(commander_id, goods_id, month_key)
            if current_count + count > good["num_limit"]:
                response.result = ERR_LIMIT
                response.drop_list.clear()
                await client.send_message(PACKET_ID, response)
                return

        if good["resource_category"] == DROP_TYPE_RESOURCE:
            if not has_enough_resource(commander_id, good["resource_type"], total_cost):
                response.result = ERR_INSUFFICIENT
                response.drop_list.clear()
                await client.send_message(PACKET_ID, response)
                return
            consume_resource(commander_id, good["resource_type"], total_cost)
        elif good["resource_category"] == DROP_TYPE_ITEM:
            if not has_enough_item(commander_id, good["resource_type"], total_cost):
                response.result = ERR_INSUFFICIENT
                response.drop_list.clear()
                await client.send_message(PACKET_ID, response)
                return
            consume_item(commander_id, good["resource_type"], total_cost)
        else:
            response.result = ERR_UNSUPPORTED
            response.drop_list.clear()
            await client.send_message(PACKET_ID, response)
            return

        commodity_type = good["commodity_type"]
        commodity_id = good["commodity_id"]

        if commodity_type == DROP_TYPE_RESOURCE:
            add_resource(commander_id, commodity_id, reward_amount)
        elif commodity_type == DROP_TYPE_ITEM:
            add_item(commander_id, commodity_id, reward_amount)
        elif commodity_type == DROP_TYPE_SHIP:
            for _ in range(reward_amount):
                from src.orm.owned_ship import add_ship
                add_ship(commander_id, commodity_id)
        elif commodity_type == DROP_TYPE_SKIN:
            from src.orm.owned_skin import give_skin
            for _ in range(reward_amount):
                give_skin(commander_id, commodity_id)
        elif commodity_type == DROP_TYPE_FURNITURE:
            from src.orm.commander_furniture import add_commander_furniture
            add_commander_furniture(commander_id, commodity_id, reward_amount)
        elif commodity_type == DROP_TYPE_EQUIP:
            from src.orm.owned_equipment import add_owned_equipment
            add_owned_equipment(commander_id, commodity_id, reward_amount)
        elif commodity_type == DROP_TYPE_VITEM:
            response.result = ERR_UNSUPPORTED
            response.drop_list.clear()
            await client.send_message(PACKET_ID, response)
            return
        else:
            response.result = ERR_UNSUPPORTED
            response.drop_list.clear()
            await client.send_message(PACKET_ID, response)
            return

        await increment_month_shop_purchase(commander_id, goods_id, month_key, count)
        # Server-authoritative task progress: a Core Shop (Mo.) buy advances
        # "Purchase 1 item in the Core Shop (Mo.)" (sub_type 152).
        try:
            from src.answer.task_handlers import schedule_emit
            schedule_emit(client, 152, 0, 1)
        except Exception:
            pass
    except ValueError:
        response.result = ERR_INSUFFICIENT
        response.drop_list.clear()
        await client.send_message(PACKET_ID, response)
        return
    except Exception:
        response.result = ERR_DB_ERROR
        response.drop_list.clear()
        await client.send_message(PACKET_ID, response)
        return

    await client.send_message(PACKET_ID, response)


def handle_month_shop_purchase(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_16201()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, PACKET_ID, e

    asyncio.create_task(_do_purchase(client, payload))
    return 0, PACKET_ID, None
