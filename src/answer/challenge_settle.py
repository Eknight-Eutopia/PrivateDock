import asyncio
from typing import Optional

from src.answer.challenge_initial import _is_valid_challenge_mode
from src.connection.client import Client
from src.protobuf import protobuf

PACKET_ID = 24010

CHALLENGE_MODE_CASUAL = 0
CHALLENGE_MODE_INFINITE = 1


async def _do_challenge_settle(client: Client, activity_id: int, mode: int, score: int):
    if activity_id > 0 and _is_valid_challenge_mode(mode) and score > 0:
        from src.orm import get_challenge_mode_state, upsert_challenge_mode_state
        try:
            state = await get_challenge_mode_state(client.commander.commander_id, activity_id, mode)
            if state is not None:
                state.current_score += score
                await upsert_challenge_mode_state(state)
        except Exception:
            pass

    await client.send_message(PACKET_ID, protobuf.SC_24010(score=score))


def _parse_settle_payload(data: bytes) -> tuple:
    activity_id = 0
    mode = 0
    score = 0
    try:
        payload = protobuf.CS_24009()
        payload.ParseFromString(data)
        activity_id = payload.activity_id
        mode = payload.mode
        score = payload.score
    except Exception:
        pass
    return activity_id, mode, score


def handle_challenge_settle(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    activity_id, mode, score = _parse_settle_payload(buffer)
    asyncio.create_task(_do_challenge_settle(client, activity_id, mode, score))
    return 0, PACKET_ID, None
