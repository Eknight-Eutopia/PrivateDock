import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from src.answer.activity_constants import (
    NEW_SERVER_SHOP_RESULT_OK,
    NEW_SERVER_SHOP_RESULT_FAILED,
    NEW_SERVER_SHOP_RESULT_INSUFFICIENT,
    NEW_SERVER_SHOP_RESULT_LIMIT,
    NEW_SERVER_SHOP_RESULT_UNSUPPORTED,
    NEW_SERVER_SHOP_GOODS_TYPE_FIXED,
    NEW_SERVER_SHOP_GOODS_TYPE_SELECTABLE,
)
from src.answer.new_server_shop_shared import (
    load_new_server_shop_activity,
    default_new_server_shop_state,
    normalize_new_server_shop_state,
    sorted_unique_uint32,
)
from src.orm import (
    get_new_server_shop_state,
    upsert_new_server_shop_state,
    has_enough_resource,
    has_enough_item,
    consume_resource,
    consume_item,
    add_resource,
    add_item,
    add_owned_equipment,
    add_ship,
    add_commander_furniture,
    give_skin,
)

PACKET_ID = 26044


async def _apply_drops(client: Client, drops: list):
    cid = client.commander.commander_id
    from src.consts.drop_types import (DROP_TYPE_RESOURCE, DROP_TYPE_ITEM, DROP_TYPE_LOVE_LETTER, DROP_TYPE_EQUIP, DROP_TYPE_SHIP, DROP_TYPE_FURNITURE, DROP_TYPE_SKIN,
                                       DROP_TYPE_ICON_FRAME, DROP_TYPE_CHAT_FRAME, DROP_TYPE_COMBAT_UI_STYLE)
    for drop in drops:
        if drop.type in (DROP_TYPE_ICON_FRAME, DROP_TYPE_CHAT_FRAME, DROP_TYPE_COMBAT_UI_STYLE):
            from src.orm.commander_attire import grant_commander_attire_drop_sync
            grant_commander_attire_drop_sync(cid, drop.type, drop.id, drop.number)
        elif drop.type == DROP_TYPE_RESOURCE:
            await add_resource(cid, drop.id, drop.number)
        elif drop.type in (DROP_TYPE_ITEM, DROP_TYPE_LOVE_LETTER):
            await add_item(cid, drop.id, drop.number)
        elif drop.type == DROP_TYPE_EQUIP:
            add_owned_equipment(cid, drop.id, drop.number)
        elif drop.type == DROP_TYPE_SHIP:
            for _ in range(drop.number):
                await add_ship(cid, drop.id)
        elif drop.type == DROP_TYPE_FURNITURE:
            await add_commander_furniture(cid, drop.id, drop.number)
        elif drop.type == DROP_TYPE_SKIN:
            for _ in range(drop.number):
                await give_skin(cid, drop.id)


async def _consume_cost(client: Client, entry, purchase_count: int) -> Optional[str]:
    total_cost = entry.resource_num * purchase_count
    cid = client.commander.commander_id
    from src.consts.drop_types import DROP_TYPE_RESOURCE, DROP_TYPE_ITEM
    if entry.resource_category == DROP_TYPE_RESOURCE:
        if not await has_enough_resource(cid, entry.resource_type, total_cost):
            return "insufficient resource"
        await consume_resource(cid, entry.resource_type, total_cost)
        return None
    elif entry.resource_category == DROP_TYPE_ITEM:
        if not await has_enough_item(cid, entry.resource_type, total_cost):
            return "insufficient item"
        await consume_item(cid, entry.resource_type, total_cost)
        return None
    else:
        return f"unsupported cost category {entry.resource_category}"


def _merge_drops(drops: list) -> list:
    merged = {}
    for d in drops:
        key = (d.type, d.id)
        if key in merged:
            merged[key].number += d.number
        else:
            merged[key] = protobuf.DROPINFO(type=d.type, id=d.id, number=d.number)
    result = list(merged.values())
    result.sort(key=lambda x: (x.type, x.id))
    return result


async def _do_purchase(client: Client, payload: protobuf.CS_26043):
    response = protobuf.SC_26044(result=NEW_SERVER_SHOP_RESULT_FAILED, drop_list=[])
    if client.commander is None or payload.act_id == 0 or payload.goodsid == 0:
        await client.send_message(PACKET_ID, response)
        return

    activity, active = load_new_server_shop_activity(payload.act_id)
    if not active:
        await client.send_message(PACKET_ID, response)
        return

    entry = activity.goods_by_id.get(payload.goodsid)
    if entry is None:
        await client.send_message(PACKET_ID, response)
        return

    state = await get_new_server_shop_state(client.commander.commander_id, payload.act_id)
    if state is None:
        state = default_new_server_shop_state(client.commander.commander_id, payload.act_id, activity.goods)
        await upsert_new_server_shop_state(state)
        state = await get_new_server_shop_state(client.commander.commander_id, payload.act_id)
        if state is None:
            await client.send_message(PACKET_ID, response)
            return

    if normalize_new_server_shop_state(state, activity.goods):
        await upsert_new_server_shop_state(state)

    goods_idx = -1
    for i, gs in enumerate(state.goods):
        if gs.id == entry.id:
            goods_idx = i
            break
    if goods_idx < 0:
        await client.send_message(PACKET_ID, response)
        return

    selected_by_item = {}
    for sel in (payload.selected or []):
        if sel.itemid == 0 or sel.count == 0:
            continue
        selected_by_item[sel.itemid] = selected_by_item.get(sel.itemid, 0) + sel.count

    purchase_count = 1
    drops = []

    if entry.goods_type == NEW_SERVER_SHOP_GOODS_TYPE_FIXED:
        if selected_by_item or not entry.goods:
            response.result = NEW_SERVER_SHOP_RESULT_LIMIT
            await client.send_message(PACKET_ID, response)
            return
        drops.append(protobuf.DROPINFO(type=entry.type, id=entry.goods[0], num=entry.num))
    else:
        if not selected_by_item:
            response.result = NEW_SERVER_SHOP_RESULT_LIMIT
            await client.send_message(PACKET_ID, response)
            return
        allowed = set(entry.goods)
        bought_set = set(state.goods[goods_idx].bought_record or [])

        item_ids = []
        for item_id, count in selected_by_item.items():
            if item_id not in allowed:
                response.result = NEW_SERVER_SHOP_RESULT_LIMIT
                await client.send_message(PACKET_ID, response)
                return
            if entry.goods_type == NEW_SERVER_SHOP_GOODS_TYPE_SELECTABLE:
                if count != 1:
                    response.result = NEW_SERVER_SHOP_RESULT_LIMIT
                    await client.send_message(PACKET_ID, response)
                    return
                if item_id in bought_set:
                    response.result = NEW_SERVER_SHOP_RESULT_LIMIT
                    await client.send_message(PACKET_ID, response)
                    return
            purchase_count += count
            item_ids.append(item_id)
            for _ in range(count):
                drops.append(protobuf.DROPINFO(type=entry.type, id=item_id, num=entry.num))

        purchase_count -= 1

        if entry.goods_type == NEW_SERVER_SHOP_GOODS_TYPE_SELECTABLE:
            state.goods[goods_idx].bought_record = sorted_unique_uint32(
                (state.goods[goods_idx].bought_record or []) + item_ids
            )

    if purchase_count == 0 or state.goods[goods_idx].count < purchase_count:
        response.result = NEW_SERVER_SHOP_RESULT_LIMIT
        await client.send_message(PACKET_ID, response)
        return

    err_msg = await _consume_cost(client, entry, purchase_count)
    if err_msg is not None:
        err_lower = err_msg.lower()
        if "insufficient" in err_lower:
            response.result = NEW_SERVER_SHOP_RESULT_INSUFFICIENT
        elif "limit" in err_lower or "selected" in err_lower or "already" in err_lower:
            response.result = NEW_SERVER_SHOP_RESULT_LIMIT
        else:
            response.result = NEW_SERVER_SHOP_RESULT_UNSUPPORTED
        await client.send_message(PACKET_ID, response)
        return

    await _apply_drops(client, drops)
    state.goods[goods_idx].count -= purchase_count
    await upsert_new_server_shop_state(state)

    response.result = NEW_SERVER_SHOP_RESULT_OK
    response.drop_list = _merge_drops(drops)
    await client.send_message(PACKET_ID, response)


def handle_new_server_shop_purchase(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_26043()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, PACKET_ID, e
    asyncio.create_task(_do_purchase(client, payload))
    return 0, PACKET_ID, None
