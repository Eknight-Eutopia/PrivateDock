import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def handle_charge_start(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    response = protobuf.SC_11502()
    response.result = 5002
    response.pay_id = ""
    response.url = ""
    response.order_sign = ""
    asyncio.create_task(client.send_message(11502, response))
    return 0, 11502, None


def handle_charge_confirm(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    response = protobuf.SC_11505()
    response.result = 5002
    response.shop_id = 0
    response.gem = 0
    response.gem_free = 0
    asyncio.create_task(client.send_message(11505, response))
    return 0, 11505, None


def handle_charge_failure(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    response = protobuf.SC_11511()
    response.result = 0
    asyncio.create_task(client.send_message(11511, response))
    return 0, 11511, None


def handle_refund_charge_start(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    response = protobuf.SC_11514()
    response.result = 5002
    response.pay_id = ""
    response.url = ""
    response.order_sign = ""
    asyncio.create_task(client.send_message(11514, response))
    return 0, 11514, None


def handle_get_charge_list(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    asyncio.create_task(_do_get_charge_list(client))
    return 0, 16105, None


async def _load_charge_items():
    from src.orm.config_entry import afetch_config_entries_data
    rows = await afetch_config_entries_data("ShareCfg/pay_data_display.json")
    return [r for r in rows if isinstance(r, dict)]


async def _do_get_charge_list(client: Client):
    from src.answer.shopping_command_answer import offer_ids, offer_claim_total_count, offer_group_claims
    response = protobuf.SC_16105()
    if client.commander is not None:
        cid = client.commander.commander_id
        for offer_id in offer_ids():
            count = await offer_claim_total_count(cid, offer_id)
            si = protobuf.SHOPINFO(shop_id=offer_id, pay_count=count)
            response.normal_list.append(si)
        for group_id, group_count in await offer_group_claims(cid):
            si = protobuf.SHOPINFO(shop_id=group_id, pay_count=group_count)
            response.normal_group_list.append(si)
        # Real-money / gem charge packs come from pay_data_display and populate
        # the client's getChargedList() (TYPE_CHARGE goods) + first-pay list.
        # Akashi Recommends and the charge shop render these banners from it.
        for item in await _load_charge_items():
            oid = item.get("id")
            if not oid:
                continue
            oid = int(oid)
            count = await offer_claim_total_count(cid, oid)
            response.pay_list.append(protobuf.SHOPINFO(shop_id=oid, pay_count=count))
            if item.get("first_pay_double") == 1:
                # first_pay_list is repeated uint32 (shop ids only), unlike the
                # other three SC_16105 fields which carry SHOPINFO messages.
                response.first_pay_list.append(oid)
    await client.send_message(16105, response)


def handle_get_refund_info(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    response = protobuf.SC_11024()
    response.result = 0
    del response.shop_info[:]
    asyncio.create_task(client.send_message(11024, response))
    return 0, 11024, None
