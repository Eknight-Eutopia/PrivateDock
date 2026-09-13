from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.protobuf import protobuf


def push_equip_skin_list(client: Client) -> None:
    """SC_14101 push after a mid-session skin grant (client on(14101) merges
    it into EquipmentProxy.equipmentSkinIds; without it the client only learns
    of the skin on the next login). Best-effort: a failed push must not fail
    the grant that triggered it."""
    import asyncio

    from src.logger.logger import log_event, LOG_LEVEL_WARN
    from src.orm.equipment_skin import list_owned_equip_skins_sync

    try:
        response = protobuf.SC_14101()
        for skin_id, count in list_owned_equip_skins_sync(client.commander.commander_id):
            response.equip_skin_list.append(protobuf.EQUIPSKININFO(id=skin_id, count=count))
        asyncio.create_task(client.send_message(14101, response))
    except Exception as e:
        log_event("Answer", "EquipSkin", f"SC_14101 push failed: {e}", LOG_LEVEL_WARN)


def handle_equipped_weapon_skin(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 14101

    from src.orm.equipment_skin import list_owned_equip_skins_sync
    try:
        owned = list_owned_equip_skins_sync(client.commander.commander_id)
    except Exception as e:
        return 0, packet_id, e

    response = protobuf.SC_14101()
    for skin_id, count in owned:
        response.equip_skin_list.append(protobuf.EQUIPSKININFO(id=skin_id, count=count))

    data = response.SerializeToString()
    header = generate_packet_header(packet_id, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, packet_id, None
