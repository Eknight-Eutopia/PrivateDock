import asyncio
import time
from typing import Optional

from src.connection.client import Client
from src.logger.logger import log_event, LOG_LEVEL_ERROR, LOG_LEVEL_WARN
from src.protobuf import protobuf
from src.db.store import NotFoundError

from .helpers import (
    get_juustagram_chat_group_config,
    ensure_juustagram_group_exists,
    get_juustagram_chat_group,
    create_juustagram_chat_group,
    add_juustagram_chat_reply,
    update_juustagram_group,
    set_juustagram_current_chat_group,
    build_juustagram_red_packet_drops,
)


def handle_instagram_chat_activate_topic(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_11722()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 11723, e

    if client.commander is None:
        return 0, 11723, Exception("missing commander")

    now = int(time.time())
    chat_group_ids = list(payload.chat_group_id_list)
    log_event("InstagramChat", "ActivateTopic",
              f"uid={client.commander.commander_id} ids={chat_group_ids}")
    result_list = []
    for chat_group_id in chat_group_ids:
        if chat_group_id == 0:
            log_event("InstagramChat", "ActivateTopic",
                      f"uid={client.commander.commander_id} chat_group_id={chat_group_id} -> result=1 (zero id)", LOG_LEVEL_ERROR)
            result_list.append(1)
            continue
        config = get_juustagram_chat_group_config(chat_group_id)
        if config is None or config.ship_group == 0:
            log_event("InstagramChat", "ActivateTopic",
                      f"uid={client.commander.commander_id} chat_group_id={chat_group_id} -> result=0 (client has newer topic than server data, accepted)", LOG_LEVEL_WARN)
            result_list.append(0)
            continue
        try:
            ensure_juustagram_group_exists(client.commander.commander_id, config.ship_group, chat_group_id)
        except Exception as e:
            log_event("InstagramChat", "ActivateTopic",
                      f"uid={client.commander.commander_id} chat_group_id={chat_group_id} -> result=1 (ensure_group failed: {type(e).__name__}: {e})", LOG_LEVEL_ERROR)
            result_list.append(1)
            continue
        try:
            get_juustagram_chat_group(client.commander.commander_id, chat_group_id)
        except NotFoundError:
            try:
                create_juustagram_chat_group(client.commander.commander_id, config.ship_group, chat_group_id, now)
            except Exception as e:
                log_event("InstagramChat", "ActivateTopic",
                          f"uid={client.commander.commander_id} chat_group_id={chat_group_id} -> result=1 (create_chat_group failed: {type(e).__name__}: {e})", LOG_LEVEL_ERROR)
                result_list.append(1)
                continue
        result_list.append(0)

    response = protobuf.SC_11723()
    response.result_list.extend(result_list)
    response.op_time = now
    asyncio.create_task(client.send_message(11723, response))
    return 0, 11723, None


def handle_instagram_chat_reply(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_11712()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 11713, e

    if client.commander is None:
        return 0, 11713, Exception("missing commander")

    response = protobuf.SC_11713()
    response.result = 0
    now = int(time.time())
    # op_time is a REQUIRED proto2 field: it must be set before ANY send path,
    # including the error replies (result=1), or serialization fails and the
    # packet is never delivered.
    response.op_time = now
    try:
        updated = add_juustagram_chat_reply(
            client.commander.commander_id,
            payload.chat_group_id,
            payload.chat_id,
            payload.value,
            now,
        )
    except Exception as e:
        log_event("JuustagramChat", "ReplyFailed",
                  f"chat_group_id={payload.chat_group_id} chat_id={payload.chat_id}: "
                  f"{type(e).__name__}: {e}", LOG_LEVEL_ERROR)
        response.result = 1
        asyncio.create_task(client.send_message(11713, response))
        return 0, 11713, None

    response.op_time = updated.get("op_time", now)
    try:
        drops = build_juustagram_red_packet_drops(client, payload.value)
    except Exception as e:
        log_event("JuustagramChat", "RedPacketFailed",
                  f"red_packet_id={payload.value}: {type(e).__name__}: {e}", LOG_LEVEL_ERROR)
        response.result = 1
        asyncio.create_task(client.send_message(11713, response))
        return 0, 11713, None

    response.drop_list.extend(drops)
    asyncio.create_task(client.send_message(11713, response))
    return 0, 11713, None


def handle_instagram_chat_set_care(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_11716()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 11717, e

    if client.commander is None:
        return 0, 11717, Exception("missing commander")

    response = protobuf.SC_11717()
    response.result = 0
    try:
        update_juustagram_group(
            client.commander.commander_id,
            payload.group_id,
            favorite=payload.value,
        )
    except Exception:
        response.result = 1

    asyncio.create_task(client.send_message(11717, response))
    return 0, 11717, None


def handle_instagram_chat_set_skin(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_11714()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 11715, e

    if client.commander is None:
        return 0, 11715, Exception("missing commander")

    response = protobuf.SC_11715()
    response.result = 0
    try:
        update_juustagram_group(
            client.commander.commander_id,
            payload.group_id,
            skin_id=payload.skin_id,
        )
    except Exception:
        response.result = 1

    asyncio.create_task(client.send_message(11715, response))
    return 0, 11715, None


def handle_instagram_chat_set_topic(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_11718()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 11719, e

    if client.commander is None:
        return 0, 11719, Exception("missing commander")

    response = protobuf.SC_11719()
    response.result = 0
    try:
        set_juustagram_current_chat_group(client.commander.commander_id, payload.chat_group_id)
    except Exception:
        response.result = 1

    asyncio.create_task(client.send_message(11719, response))
    return 0, 11719, None
