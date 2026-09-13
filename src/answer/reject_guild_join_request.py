import asyncio
import json
from typing import Optional

from src.connection.client import Client
from src.db.session import get_sync_session
from sqlalchemy import select
from src.orm.guild_membership import GuildMembership
from src.orm.guild_request import delete_guild_join_request
from src.answer.simpleops.helpers import GUILD_DUTY_COMMANDER, GUILD_DUTY_DEPUTY

PACKET_ID = 70060
GUILD_RESULT_FAILURE = 1
GUILD_RESULT_SUCCESS = 0


def handle_reject_guild_join_request(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    if client.commander is None:
        asyncio.create_task(client.send_message(PACKET_ID, {"result": GUILD_RESULT_FAILURE}))
        return 0, PACKET_ID, None

    try:
        data = json.loads(buffer.decode("utf-8", errors="replace"))
    except Exception:
        asyncio.create_task(client.send_message(PACKET_ID, {"result": GUILD_RESULT_FAILURE}))
        return 0, PACKET_ID, None

    player_id = data.get("player_id", 0)
    if player_id == 0:
        asyncio.create_task(client.send_message(PACKET_ID, {"result": GUILD_RESULT_FAILURE}))
        return 0, PACKET_ID, None

    cid = client.commander.commander_id
    with get_sync_session() as session:
        membership = session.execute(
            select(GuildMembership).where(GuildMembership.commander_id == cid)
        ).scalar_one_or_none()

    if membership is None:
        asyncio.create_task(client.send_message(PACKET_ID, {"result": GUILD_RESULT_FAILURE}))
        return 0, PACKET_ID, None

    if membership.duty not in (GUILD_DUTY_COMMANDER, GUILD_DUTY_DEPUTY):
        asyncio.create_task(client.send_message(PACKET_ID, {"result": GUILD_RESULT_FAILURE}))
        return 0, PACKET_ID, None

    delete_guild_join_request(membership.guild_id, player_id)
    asyncio.create_task(client.send_message(PACKET_ID, {"result": GUILD_RESULT_SUCCESS}))
    return 0, PACKET_ID, None
