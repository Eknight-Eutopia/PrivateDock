import asyncio
import json
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from src.answer.activity_constants import ACTIVITY_TYPE_CHALLENGE
from src.answer.activity_templates import load_activity_template
from src.orm import ChallengeModeState, ChallengeCommanderSlot, upsert_challenge_mode_state

PACKET_ID = 24003

CHALLENGE_MODE_CASUAL = 0
CHALLENGE_MODE_INFINITE = 1
CHALLENGE_RESULT_SUCCESS = 0
CHALLENGE_RESULT_FAILURE = 1
CHALLENGE_SHIP_FULL_HP_RATIO = 10000


def _is_valid_challenge_mode(mode: int) -> bool:
    return mode == CHALLENGE_MODE_CASUAL or mode == CHALLENGE_MODE_INFINITE


async def _do_challenge_initial(client: Client, payload: protobuf.CS_24002):
    if not _is_valid_challenge_mode(payload.mode):
        await client.send_message(PACKET_ID, protobuf.SC_24003(result=CHALLENGE_RESULT_FAILURE))
        return

    activity = load_activity_template(payload.activity_id)
    if activity is None or activity.type != ACTIVITY_TYPE_CHALLENGE:
        await client.send_message(PACKET_ID, protobuf.SC_24003(result=CHALLENGE_RESULT_FAILURE))
        return

    raw = None
    from src.orm.config_entry import get_config_entry
    raw_entry = get_config_entry("ShareCfg/activity_event_challenge.json", str(activity.config_id))
    if raw_entry is not None:
        data = raw_entry if isinstance(raw_entry, dict) else json.loads(raw_entry) if isinstance(raw_entry, str) else raw_entry
        raw = data
    if raw is None:
        await client.send_message(PACKET_ID, protobuf.SC_24003(result=CHALLENGE_RESULT_FAILURE))
        return

    season_id = max(raw.get("id", 0), 1)
    regular_id = payload.mode + 1
    submarine_id = payload.mode + 11

    groups = {}
    for g in payload.group_list:
        if g is None:
            await client.send_message(PACKET_ID, protobuf.SC_24003(result=CHALLENGE_RESULT_FAILURE))
            return
        groups[g.id] = g

    regular_group = groups.get(regular_id)
    submarine_group = groups.get(submarine_id)
    if regular_group is None or submarine_group is None:
        await client.send_message(PACKET_ID, protobuf.SC_24003(result=CHALLENGE_RESULT_FAILURE))
        return

    seen_ship = set()
    for g in [regular_group, submarine_group]:
        for ship_id in (g.ship_list or []):
            if ship_id == 0 or ship_id in seen_ship:
                await client.send_message(PACKET_ID, protobuf.SC_24003(result=CHALLENGE_RESULT_FAILURE))
                return
            seen_ship.add(ship_id)

    state = ChallengeModeState()
    state.commander_id = client.commander.commander_id
    state.activity_id = payload.activity_id
    state.mode = payload.mode
    state.season_id = season_id
    state.level = 1
    state.current_score = 0
    state.issl = 0
    state.regular_group_id = regular_group.id
    state.submarine_group_id = submarine_group.id
    state.regular_ship_ids = list(regular_group.ship_list or [])
    state.submarine_ship_ids = list(submarine_group.ship_list or [])
    state.regular_commanders = [
        ChallengeCommanderSlot(pos=c.pos, commander_id=c.id)
        for c in (regular_group.commanders or [])
    ]
    state.submarine_commanders = [
        ChallengeCommanderSlot(pos=c.pos, commander_id=c.id)
        for c in (submarine_group.commanders or [])
    ]

    try:
        await upsert_challenge_mode_state(state)
    except Exception:
        await client.send_message(PACKET_ID, protobuf.SC_24003(result=CHALLENGE_RESULT_FAILURE))
        return

    await client.send_message(PACKET_ID, protobuf.SC_24003(result=CHALLENGE_RESULT_SUCCESS))


def handle_challenge_initial(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_24002()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, PACKET_ID, e
    asyncio.create_task(_do_challenge_initial(client, payload))
    return 0, PACKET_ID, None
