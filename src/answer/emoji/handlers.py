import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

from .helpers import list_emoji_templates


def handle_emoji_info_request(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_11601()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 11602, e

    entries = list_emoji_templates()
    emoji_list = []
    for entry in entries:
        achieve = entry.get("achieve", 0)
        if achieve == 1:
            emoji_list.append(entry.get("id", 0))

    emoji_list.sort()

    response = protobuf.SC_11602()
    response.emoji_list.extend(emoji_list)
    asyncio.create_task(client.send_message(11602, response))
    return 0, 11602, None
