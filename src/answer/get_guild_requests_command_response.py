import asyncio
import json
from typing import Optional

from src.connection.client import Client
from src.db.session import get_sync_session
from sqlalchemy import select
from src.orm.guild_membership import GuildMembership
from src.orm.guild_request import list_guild_join_requests

PACKET_ID = 70082


def handle_get_guild_requests(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    if client.commander is None:
        asyncio.create_task(client.send_message(PACKET_ID, {"request_list": []}))
        return 0, PACKET_ID, None

    cid = client.commander.commander_id
    payload_id = 0
    try:
        data = json.loads(buffer.decode("utf-8", errors="replace"))
        payload_id = data.get("id", 0)
    except Exception:
        pass

    with get_sync_session() as session:
        membership = session.execute(
            select(GuildMembership).where(GuildMembership.commander_id == cid)
        ).scalar_one_or_none()

    if membership is None:
        asyncio.create_task(client.send_message(PACKET_ID, {"request_list": []}))
        return 0, PACKET_ID, None

    if payload_id != 0 and payload_id != membership.guild_id:
        asyncio.create_task(client.send_message(PACKET_ID, {"request_list": []}))
        return 0, PACKET_ID, None

    requests = list_guild_join_requests(membership.guild_id)
    request_list = []
    for req in requests:
        applicant = req.get("applicant", {})
        ts = 0
        requested_at = req.get("requested_at")
        if requested_at is not None:
            if hasattr(requested_at, "timestamp"):
                ts = int(requested_at.timestamp())
            else:
                ts = int(requested_at)
        request_list.append({
            "timestamp": ts,
            "player": {
                "id": applicant.get("commander_id", 0),
                "name": applicant.get("name", ""),
                "lv": applicant.get("level", 0),
                "display": {
                    "icon": applicant.get("display_icon_id", 0),
                    "icon_frame": applicant.get("selected_icon_frame_id", 0),
                    "skin": applicant.get("display_skin_id", 0),
                    "chat_frame": applicant.get("selected_chat_frame_id", 0),
                    "icon_theme": applicant.get("display_icon_theme_id", 0),
                },
            },
            "content": req.get("content", ""),
        })

    asyncio.create_task(client.send_message(PACKET_ID, {"request_list": request_list}))
    return 0, PACKET_ID, None
