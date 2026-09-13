import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from src.orm import load_limit_challenge_state

PACKET_ID = 24021
LIMIT_CHALLENGE_SUCCESS = 0
LIMIT_CHALLENGE_FAILURE = 1
LIMIT_CHALLENGE_INFO_TYPE_MONTHLY = 1

CONSTELLATION_CHALLENGE_MONTH_CATEGORY = "ShareCfg/constellation_challenge_month.json"
CONSTELLATION_CHALLENGE_TEMPLATE_CATEGORY = "ShareCfg/expedition_constellation_challenge_template.json"


def _load_current_constellation_challenge_month() -> Optional[dict]:
    from src.orm.config_entry import fetch_config_entry_data, fetch_config_entries_data
    from datetime import datetime, timezone

    month_id = datetime.now(timezone.utc).month
    data = fetch_config_entry_data(CONSTELLATION_CHALLENGE_MONTH_CATEGORY, str(month_id))
    if isinstance(data, dict) and data.get("id") == month_id:
        return data

    for entry in fetch_config_entries_data(CONSTELLATION_CHALLENGE_MONTH_CATEGORY):
        if isinstance(entry, dict) and entry.get("id") == month_id:
            return entry
    return None


def _normalized_challenge_ids(ids: list) -> list:
    seen = set()
    result = []
    for cid in (ids or []):
        if cid and cid not in seen:
            seen.add(cid)
            result.append(cid)
    return sorted(result)


async def _do_limit_challenge_info(client: Client, payload: protobuf.CS_24020):
    if payload.type != LIMIT_CHALLENGE_INFO_TYPE_MONTHLY:
        response = protobuf.SC_24021(result=LIMIT_CHALLENGE_FAILURE, times=[], awards=[], pass_ids=[])
        await client.send_message(PACKET_ID, response)
        return

    month_config = _load_current_constellation_challenge_month()
    if month_config is None:
        response = protobuf.SC_24021(result=LIMIT_CHALLENGE_FAILURE, times=[], awards=[], pass_ids=[])
        await client.send_message(PACKET_ID, response)
        return

    state = await load_limit_challenge_state(client.commander.commander_id)
    challenge_ids = _normalized_challenge_ids(month_config.get("stage", []))
    stage_set = set(challenge_ids)

    times = []
    awards = []
    for cid in challenge_ids:
        times.append(protobuf.KVDATA(key=cid, value=state.best_times.get(cid, 0)))
        awards.append(protobuf.KVDATA(key=cid, value=1 if state.awarded.get(cid, False) else 0))

    pass_ids = sorted(cid for cid in state.pass_ids if cid in stage_set)

    response = protobuf.SC_24021(
        result=LIMIT_CHALLENGE_SUCCESS,
        times=times,
        awards=awards,
        pass_ids=pass_ids,
    )
    await client.send_message(PACKET_ID, response)


def handle_limit_challenge_info(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_24020()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, PACKET_ID, e
    asyncio.create_task(_do_limit_challenge_info(client, payload))
    return 0, PACKET_ID, None
