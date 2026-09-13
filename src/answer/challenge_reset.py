import asyncio
from typing import Optional

from src.answer.challenge_initial import _is_valid_challenge_mode
from src.connection.client import Client
from src.protobuf import protobuf
from src.answer.activity_constants import ACTIVITY_TYPE_CHALLENGE
from src.answer.activity_templates import load_activity_template

PACKET_ID = 24012
CHALLENGE_RESULT_SUCCESS = 0
CHALLENGE_RESULT_FAILURE = 1
CHALLENGE_MODE_CASUAL = 0
CHALLENGE_MODE_INFINITE = 1


async def _do_challenge_reset(client: Client, payload: protobuf.CS_24011):
    response = protobuf.SC_24012(result=CHALLENGE_RESULT_FAILURE)
    activity = load_activity_template(payload.activity_id)
    if activity is None or activity.type != ACTIVITY_TYPE_CHALLENGE or not _is_valid_challenge_mode(payload.mode):
        await client.send_message(PACKET_ID, response)
        return

    from src.orm import delete_challenge_mode_state
    try:
        await delete_challenge_mode_state(client.commander.commander_id, payload.activity_id, payload.mode)
    except Exception:
        await client.send_message(PACKET_ID, response)
        return

    response.result = CHALLENGE_RESULT_SUCCESS
    await client.send_message(PACKET_ID, response)


def handle_challenge_reset(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_24011()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, PACKET_ID, e
    asyncio.create_task(_do_challenge_reset(client, payload))
    return 0, PACKET_ID, None
