import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from .guild_core_helpers_compat import build_guild_chat_player

GUILD_CHAT_PLACEHOLDER_ID = 0
CHAT_LOG_MAX_COUNT = 100


def handle_commander_guild_chat(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 60101
    payload = protobuf.CS_60100()
    payload.ParseFromString(buffer)

    count = payload.count
    if count <= 0:
        count = CHAT_LOG_MAX_COUNT
    if count > CHAT_LOG_MAX_COUNT:
        count = CHAT_LOG_MAX_COUNT

    from src.orm.guild_chat import list_guild_chat_messages
    try:
        entries = list_guild_chat_messages(GUILD_CHAT_PLACEHOLDER_ID, count)
    except Exception as e:
        return 0, packet_id, e

    response = protobuf.SC_60101()
    for entry in entries:
        if isinstance(entry, dict):
            sender = entry.get("sender", {})
            content = entry.get("content", "")
            sent_at = entry.get("sent_at", 0)
            if hasattr(sent_at, "timestamp"):
                sent_at = int(sent_at.timestamp())
        else:
            sender = entry.sender if hasattr(entry, "sender") else {}
            content = getattr(entry, "content", "")
            sent_at = getattr(entry, "sent_at", 0)
            if hasattr(sent_at, "timestamp"):
                sent_at = int(sent_at.timestamp())

        chat = protobuf.GUIDE_CHAT()
        chat.player.CopyFrom(build_guild_chat_player(sender))
        chat.content = content
        chat.time = sent_at
        response.chat_list.append(chat)

    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None
