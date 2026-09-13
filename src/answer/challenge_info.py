import asyncio
import json
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from src.answer.activity_constants import ACTIVITY_TYPE_CHALLENGE
from src.answer.activity_templates import load_activity_template

PACKET_ID = 24005


def _load_activity_event_challenge(config_id: int) -> Optional[dict]:
    from src.orm.config_entry import get_config_entry
    raw = get_config_entry("ShareCfg/activity_event_challenge.json", str(config_id))
    if raw is None:
        return None
    data = raw if isinstance(raw, dict) else json.loads(raw) if isinstance(raw, str) else raw
    return data


def _challenge_dungeon_list(config: dict, season_id: int) -> list:
    infinite_stage = config.get("infinite_stage", []) or []
    if not infinite_stage:
        return []
    season_index = max(0, min(season_id - 1, len(infinite_stage) - 1))
    stages = infinite_stage[season_index] if season_index < len(infinite_stage) else []
    return list(stages[0]) if stages else []


async def _do_challenge_info(client: Client, payload: protobuf.CS_24004):
    activity = load_activity_template(payload.activity_id)
    if activity is None or activity.type != ACTIVITY_TYPE_CHALLENGE:
        response = protobuf.SC_24005(result=1)
        await client.send_message(PACKET_ID, response)
        return

    config = _load_activity_event_challenge(activity.config_id)
    if config is None:
        response = protobuf.SC_24005(result=1)
        await client.send_message(PACKET_ID, response)
        return

    season_id = max(config.get("id", 0), 1)
    buff_list = config.get("buff", []) or []
    dungeon_ids = _challenge_dungeon_list(config, season_id)

    current = protobuf.CHALLENGEINFO(
        season_max_score=0,
        activity_max_score=0,
        season_max_level=0,
        activity_max_level=0,
        season_id=season_id,
        dungeon_id_list=dungeon_ids,
        buff_list=buff_list,
    )

    from src.orm import list_challenge_mode_states
    states = await list_challenge_mode_states(client.commander.commander_id, payload.activity_id)
    user_challenges = []
    for s in states:
        season = s.season_id if s.season_id > 0 else season_id
        groups = []
        if s.regular_group_id > 0:
            ships = [
                protobuf.SHIPINCHALLENGE(id=sid, hp_rant=10000)
                for sid in (s.regular_ship_ids or [])
            ]
            groups.append(protobuf.GROUPINFOINCHALLENGE(
                id=s.regular_group_id,
                ships=ships,
            ))
        if s.submarine_group_id > 0:
            ships = [
                protobuf.SHIPINCHALLENGE(id=sid, hp_rant=10000)
                for sid in (s.submarine_ship_ids or [])
            ]
            groups.append(protobuf.GROUPINFOINCHALLENGE(
                id=s.submarine_group_id,
                ships=ships,
            ))
        user_challenges.append(protobuf.USERCHALLENGEINFO(
            current_score=s.current_score,
            level=s.level,
            groupinc_list=groups,
            mode=s.mode,
            issl=s.issl,
            season_id=season,
            dungeon_id_list=list(dungeon_ids),
            buff_list=list(buff_list),
        ))

    user_challenges.sort(key=lambda x: x.mode)

    response = protobuf.SC_24005(result=0)
    response.current_challenge.CopyFrom(current)
    response.user_challenge.extend(user_challenges)
    await client.send_message(PACKET_ID, response)


def handle_challenge_info(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_24004()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, PACKET_ID, e
    asyncio.create_task(_do_challenge_info(client, payload))
    return 0, PACKET_ID, None
