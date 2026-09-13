import asyncio
import time
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

from .helpers import (
    is_friend,
    create_friend_direct_message,
    create_player_inform,
    load_commander_social_display,
    build_social_player_info,
    empty_social_player_info,
    DEFAULT_RESULT_SUCCESS,
    DEFAULT_RESULT_OFFLINE,
    DEFAULT_RESULT_FAILED,
)


def handle_send_friend_message(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        request = protobuf.CS_50105()
        request.ParseFromString(buffer)
    except Exception as e:
        return 0, 50106, e

    if not is_friend(client.commander.commander_id, request.id):
        response = protobuf.SC_50106()
        response.result = DEFAULT_RESULT_FAILED
        asyncio.create_task(client.send_message(50106, response))
        return 0, 50106, None

    if client.server is None:
        response = protobuf.SC_50106()
        response.result = DEFAULT_RESULT_OFFLINE
        asyncio.create_task(client.send_message(50106, response))
        return 0, 50106, None

    target_client = client.server.find_client_by_commander(request.id)
    if target_client is None:
        response = protobuf.SC_50106()
        response.result = DEFAULT_RESULT_OFFLINE
        asyncio.create_task(client.send_message(50106, response))
        return 0, 50106, None

    now = int(time.time())

    try:
        create_friend_direct_message(client.commander.commander_id, request.id, request.content, now)
    except Exception:
        response = protobuf.SC_50106()
        response.result = DEFAULT_RESULT_FAILED
        asyncio.create_task(client.send_message(50106, response))
        return 0, 50106, None

    msg = protobuf.SC_50104()
    msg_info = protobuf.MSG_INFO_P50()
    msg_info.timestamp = now
    msg_info.player.CopyFrom(build_social_player_info({
        "commander_id": client.commander.commander_id,
        "name": client.commander.name,
        "level": client.commander.level,
        "display_icon_id": client.commander.display_icon_id,
        "display_skin_id": client.commander.display_skin_id,
        "selected_icon_frame_id": client.commander.selected_icon_frame_id,
        "selected_chat_frame_id": client.commander.selected_chat_frame_id,
        "display_icon_theme_id": client.commander.display_icon_theme_id,
    }))
    msg_info.content = request.content
    msg.msg.CopyFrom(msg_info)

    asyncio.create_task(target_client.send_message(50104, msg))

    response = protobuf.SC_50106()
    response.result = DEFAULT_RESULT_SUCCESS
    asyncio.create_task(client.send_message(50106, response))
    return 0, 50106, None


def handle_report_player(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        request = protobuf.CS_50111()
        request.ParseFromString(buffer)
    except Exception as e:
        return 0, 50112, e

    now = int(time.time())

    try:
        create_player_inform(client.commander.commander_id, request.id, request.info, request.content, now)
    except Exception:
        response = protobuf.SC_50112()
        response.result = 1
        asyncio.create_task(client.send_message(50112, response))
        return 0, 50112, None

    response = protobuf.SC_50112()
    response.result = 0
    asyncio.create_task(client.send_message(50112, response))
    return 0, 50112, None


def handle_get_theme_template_player_info(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        request = protobuf.CS_50113()
        request.ParseFromString(buffer)
    except Exception as e:
        return 0, 50114, e

    commander = load_commander_social_display(request.user_id)

    response = protobuf.SC_50114()
    if commander is None:
        response.result = 1
        response.player.CopyFrom(empty_social_player_info())
    else:
        response.result = 0
        response.player.CopyFrom(build_social_player_info(commander))

    asyncio.create_task(client.send_message(50114, response))
    return 0, 50114, None
