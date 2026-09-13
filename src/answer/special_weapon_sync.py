import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


from src.orm.spweapon import to_proto_owned_sp_weapon

_owned_sp_weapon_to_proto = to_proto_owned_sp_weapon


def handle_special_weapon_sync(
     client: Client,
) -> tuple[int, int, Optional[Exception]]:
    owned = getattr(client.commander, "owned_sp_weapons", None)
    if owned is None:
        owned = []
    if isinstance(owned, dict):
        owned = list(owned.values())
    spweapon_list = [to_proto_owned_sp_weapon(spw) for spw in owned if spw is not None]
    response = protobuf.SC_14200(spweapon_list=spweapon_list)
    asyncio.create_task(client.send_message(14200, response))
    return 0, 14200, None

