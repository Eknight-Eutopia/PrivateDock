import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from .commander_ids_helpers import normalize_commander_ids
from .commander_friend_list import _build_friend_info


def handle_commander_friend_batch_get(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 50019
    payload = protobuf.CS_50018()
    payload.ParseFromString(buffer)

    response = protobuf.SC_50019()
    ids = normalize_commander_ids(list(payload.user_id_list), 0)
    if not ids:
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    from src.orm.profile import get_commander_social_profiles_by_ids
    try:
        profiles_by_id = get_commander_social_profiles_by_ids(ids)
    except Exception:
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    for cid in ids:
        profile = profiles_by_id.get(cid)
        if profile is None:
            continue
        response.user_list.append(_build_friend_info(profile, client))

    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None
