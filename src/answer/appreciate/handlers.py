from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from src.answer.appreciate.helpers import (
    set_commander_appreciation_gallery_unlock,
    set_commander_appreciation_gallery_favor,
    set_commander_appreciation_music_favor,
    get_or_create_commander_appreciation_state,
    save_commander_appreciation_state,
)


def handle_appreciate_gallery_unlock(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_17501()
    payload.ParseFromString(buffer)
    set_commander_appreciation_gallery_unlock(client.commander["commander_id"], payload.id)
    response = protobuf.SC_17502()
    response.result = 0
    import asyncio
    asyncio.create_task(client.send_message(17502, response))
    return 0, 17502, None


def handle_appreciate_gallery_like_toggle(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_17505()
    payload.ParseFromString(buffer)
    action = payload.action
    if action == 0:
        set_commander_appreciation_gallery_favor(client.commander["commander_id"], payload.id, True)
    elif action == 1:
        set_commander_appreciation_gallery_favor(client.commander["commander_id"], payload.id, False)
    response = protobuf.SC_17506()
    response.result = 0
    import asyncio
    asyncio.create_task(client.send_message(17506, response))
    return 0, 17506, None


def handle_appreciate_music_unlock(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    response = protobuf.SC_17504()
    response.result = 0
    import asyncio
    asyncio.create_task(client.send_message(17504, response))
    return 0, 17504, None


def handle_appreciate_music_like_toggle(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_17507()
    payload.ParseFromString(buffer)
    action = payload.action
    if action == 0:
        set_commander_appreciation_music_favor(client.commander["commander_id"], payload.id, True)
    elif action == 1:
        set_commander_appreciation_music_favor(client.commander["commander_id"], payload.id, False)
    response = protobuf.SC_17508()
    response.result = 0
    import asyncio
    asyncio.create_task(client.send_message(17508, response))
    return 0, 17508, None


def handle_appreciate_music_player_settings(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_17513()
    payload.ParseFromString(buffer)
    response = protobuf.SC_17514()
    response.result = 0
    state = get_or_create_commander_appreciation_state(client.commander["commander_id"])
    if state is None:
        response.result = 1
        import asyncio
        asyncio.create_task(client.send_message(17514, response))
        return 0, 17514, None
    state.music_no = payload.music_no
    state.music_mode = payload.music_mode
    save_commander_appreciation_state(state)
    import asyncio
    asyncio.create_task(client.send_message(17514, response))
    return 0, 17514, None
