import asyncio
import time
from typing import Optional

from src.connection.client import Client
from src.db.store import NotFoundError
from src.protobuf import protobuf
from .helpers import (
    build_juustagram_message,
    ensure_juustagram_option,
    get_or_create_juustagram_message_state,
    save_juustagram_message_state,
    get_juustagram_player_discuss,
    upsert_juustagram_player_discuss,
    get_juustagram_groups,
    create_juustagram_group,
    mark_juustagram_chat_groups_read,
    juus_group_from_model,
    build_juustagram_messages_for_ids,
    set_commander_cartoon_read_mark,
    set_commander_cartoon_collect_mark,
    JUUSTAGRAM_PLACEHOLDER_SHIP_GROUP,
    JUUSTAGRAM_PLACEHOLDER_CHAT_GROUP,
    JUUSTAGRAM_OP_ACTIVE,
    JUUSTAGRAM_OP_UPDATE,
    JUUSTAGRAM_OP_SHARE,
    JUUSTAGRAM_OP_LIKE,
    JUUSTAGRAM_OP_MARK_READ,
)


def handle_juustagram_action(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_11701()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 11702, e

    if client.commander is None:
        response = protobuf.SC_11702()
        response.result = 1
        asyncio.create_task(client.send_message(11702, response))
        return 0, 11702, None

    now = int(time.time())
    message_id = payload.id
    try:
        state = get_or_create_juustagram_message_state(client.commander.commander_id, message_id, now)
    except Exception as e:
        response = protobuf.SC_11702()
        response.result = 1
        asyncio.create_task(client.send_message(11702, response))
        return 0, 11702, None

    state["updated_at"] = now
    cmd = payload.cmd

    if cmd == JUUSTAGRAM_OP_LIKE:
        if state.get("is_good", 0) == 0:
            state["is_good"] = 1
            state["good_count"] = state.get("good_count", 0) + 1
    elif cmd == JUUSTAGRAM_OP_MARK_READ:
        state["is_read"] = 1
    elif cmd not in (JUUSTAGRAM_OP_ACTIVE, JUUSTAGRAM_OP_UPDATE, JUUSTAGRAM_OP_SHARE):
        response = protobuf.SC_11702()
        response.result = 1
        asyncio.create_task(client.send_message(11702, response))
        return 0, 11702, None

    try:
        save_juustagram_message_state(state)
    except Exception as e:
        response = protobuf.SC_11702()
        response.result = 1
        asyncio.create_task(client.send_message(11702, response))
        return 0, 11702, None

    try:
        message = build_juustagram_message(client.commander.commander_id, message_id, now)
    except Exception as e:
        response = protobuf.SC_11702()
        response.result = 1
        asyncio.create_task(client.send_message(11702, response))
        return 0, 11702, None

    response = protobuf.SC_11702()
    response.result = 0
    response.data.CopyFrom(message)
    asyncio.create_task(client.send_message(11702, response))
    return 0, 11702, None


def handle_juustagram_comment(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_11703()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 11704, e

    if client.commander is None:
        return 0, 11704, Exception("missing commander")

    now = int(time.time())
    try:
        option = ensure_juustagram_option(payload.id, payload.discuss, payload.index)
    except Exception as e:
        return 0, 11704, e

    try:
        entry = get_juustagram_player_discuss(client.commander.commander_id, payload.id, payload.discuss)
    except NotFoundError:
        entry = {
            "commander_id": client.commander.commander_id,
            "message_id": payload.id,
            "discuss_id": payload.discuss,
            "option_index": 0,
            "npc_reply_id": 0,
            "comment_time": 0,
        }

    entry["commander_id"] = client.commander.commander_id
    entry["message_id"] = payload.id
    entry["discuss_id"] = payload.discuss
    entry["option_index"] = payload.index
    entry["npc_reply_id"] = option.npc_reply_id
    entry["comment_time"] = now

    try:
        upsert_juustagram_player_discuss(entry)
    except Exception as e:
        return 0, 11704, e

    try:
        message = build_juustagram_message(client.commander.commander_id, payload.id, now)
    except Exception as e:
        return 0, 11704, e

    response = protobuf.SC_11704()
    response.result = 0
    response.data.CopyFrom(message)
    asyncio.create_task(client.send_message(11704, response))
    return 0, 11704, None


def handle_juustagram_message_range(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_11705()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 11706, e

    if client.commander is None:
        return 0, 11706, Exception("missing commander")

    try:
        messages = build_juustagram_messages_for_ids(client.commander.commander_id, list(payload.id_list))
    except Exception as e:
        return 0, 11706, e

    response = protobuf.SC_11706()
    response.ins_message_list.extend(messages)
    asyncio.create_task(client.send_message(11706, response))
    return 0, 11706, None


def handle_juustagram_data(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    if client.commander is None:
        return 0, 11711, Exception("missing commander")

    try:
        groups = get_juustagram_groups(client.commander.commander_id)
    except Exception as e:
        return 0, 11711, e

    if not groups:
        try:
            group = create_juustagram_group(
                client.commander.commander_id,
                JUUSTAGRAM_PLACEHOLDER_SHIP_GROUP,
                JUUSTAGRAM_PLACEHOLDER_CHAT_GROUP,
            )
            groups = [group]
        except Exception as e:
            return 0, 11711, e

    response_groups = [juus_group_from_model(g) for g in groups]
    response = protobuf.SC_11711()
    response.groups.extend(response_groups)
    asyncio.create_task(client.send_message(11711, response))
    return 0, 11711, None


def handle_juustagram_read_tip(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_11720()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 11721, e

    if client.commander is None:
        return 0, 11721, Exception("missing commander")

    try:
        mark_juustagram_chat_groups_read(
            client.commander.commander_id,
            list(payload.chat_group_id_list),
        )
    except Exception as e:
        return 0, 11721, e

    response = protobuf.SC_11721()
    response.result = 0
    asyncio.create_task(client.send_message(11721, response))
    return 0, 11721, None


def handle_mark_manga_read(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_17509()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 17510, e

    try:
        set_commander_cartoon_read_mark(client.commander.commander_id, payload.id)
    except Exception as e:
        return 0, 17510, e

    response = protobuf.SC_17510()
    response.result = 0
    asyncio.create_task(client.send_message(17510, response))
    return 0, 17510, None


def handle_toggle_manga_like(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_17511()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 17512, e

    action = payload.action
    liked = action == 0
    try:
        set_commander_cartoon_collect_mark(client.commander.commander_id, payload.id, liked)
    except Exception as e:
        return 0, 17512, e

    response = protobuf.SC_17512()
    response.result = 0
    asyncio.create_task(client.send_message(17512, response))
    return 0, 17512, None
