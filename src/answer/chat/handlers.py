import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from .helpers import send_chat_message


def handle_chat_room_change(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_11401()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 11402, e

    if client.server is not None:
        old_room_id = getattr(client.commander, "room_id", 0)
        client.server.change_room(old_room_id, payload.room_id, client)
    if hasattr(client.commander, "room_id"):
        client.commander.room_id = payload.room_id

    response = protobuf.SC_11402()
    response.result = 0
    response.room_id = payload.room_id
    asyncio.create_task(client.send_message(11402, response))
    return 0, 11402, None


def handle_receive_chat_message(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_50102()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 50101, e

    commander = client.commander
    room_id = getattr(commander, "room_id", 0)
    sender_id = getattr(commander, "commander_id", 0)
    sender_name = getattr(commander, "name", "")
    sender_level = getattr(commander, "level", 0)

    msg_id = send_chat_message(room_id, payload.content, sender_id, sender_name,
                               sender_level, getattr(commander, "selected_icon_frame_id", 0))
    if msg_id is None:
        return 0, 50101, Exception("failed to save message")

    # SC_50101 is the room broadcast (chatproxy.lua): the client renders it as a
    # world-channel message from `player` unless type is 100 (ban) or 1000
    # (activity-boss). There is no per-sender ack - the echo below is what makes
    # the sender see their own message.
    msg = protobuf.SC_50101()
    msg.player.id = sender_id
    msg.player.name = sender_name or ""
    msg.player.lv = sender_level
    display = msg.player.display
    display.icon = getattr(commander, "display_icon_id", 0)
    display.skin = getattr(commander, "display_skin_id", 0) or 0
    display.icon_frame = getattr(commander, "selected_icon_frame_id", 0)
    display.chat_frame = getattr(commander, "selected_chat_frame_id", 0)
    # required COMMANDERDISPLAY fields - SerializeToString raises EncodeError
    # (and the packet silently degrades to garbage) if any of these are unset
    display.icon_theme = getattr(commander, "display_icon_theme_id", 0) or 0
    display.marry_flag = 0
    display.transform_flag = 0
    msg.type = payload.type
    msg.content = payload.content

    server = client.server
    if server is not None:
        asyncio.create_task(server.broadcast_room(room_id, 50101, msg))
    return 0, 50101, None
