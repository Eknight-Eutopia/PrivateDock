import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from src.orm import load_limit_challenge_state, save_limit_challenge_state

PACKET_ID = 24023
LIMIT_CHALLENGE_SUCCESS = 0
LIMIT_CHALLENGE_FAILURE = 1

CONSTELLATION_CHALLENGE_MONTH_CATEGORY = "ShareCfg/constellation_challenge_month.json"
CONSTELLATION_CHALLENGE_TEMPLATE_CATEGORY = "ShareCfg/expedition_constellation_challenge_template.json"


def _load_constellation_challenge_template(challenge_id: int) -> Optional[dict]:
    from src.orm.config_entry import fetch_config_entry_data
    raw = fetch_config_entry_data(CONSTELLATION_CHALLENGE_TEMPLATE_CATEGORY, str(challenge_id))
    if raw is None:
        return None
    return raw if isinstance(raw, dict) else json.loads(raw) if isinstance(raw, str) else raw


from .limit_challenge_info import _normalized_challenge_ids


async def _do_limit_challenge_award(client: Client, payload: protobuf.CS_24022):
    response = protobuf.SC_24023(result=LIMIT_CHALLENGE_FAILURE, drop_list=[])
    requested_ids = _normalized_challenge_ids(payload.challengeids)
    if not requested_ids:
        await client.send_message(PACKET_ID, response)
        return

    from src.orm.config_entry import fetch_config_entry_data
    month_id = datetime.now(timezone.utc).month
    raw_month = fetch_config_entry_data(CONSTELLATION_CHALLENGE_MONTH_CATEGORY, str(month_id))
    if raw_month is None:
        await client.send_message(PACKET_ID, response)
        return
    month_config = raw_month if isinstance(raw_month, dict) else json.loads(raw_month) if isinstance(raw_month, str) else raw_month
    allowed = set(month_config.get("stage", []) or [])

    drops = {}
    try:
        state = await load_limit_challenge_state(client.commander.commander_id)
        passed = set(state.pass_ids)

        for cid in requested_ids:
            if cid not in allowed:
                await client.send_message(PACKET_ID, response)
                return
            if state.awarded.get(cid, False):
                await client.send_message(PACKET_ID, response)
                return
            if cid not in passed:
                await client.send_message(PACKET_ID, response)
                return
            template = _load_constellation_challenge_template(cid)
            if template is None:
                await client.send_message(PACKET_ID, response)
                return
            for drop_entry in (template.get("award_display", []) or []):
                if len(drop_entry) < 3:
                    continue
                key = f"{drop_entry[0]}_{drop_entry[1]}"
                if key in drops:
                    drops[key].number += drop_entry[2]
                else:
                    d = protobuf.DROPINFO()
                    d.type = drop_entry[0]
                    d.id = drop_entry[1]
                    d.number = drop_entry[2]
                    drops[key] = d
            state.awarded[cid] = True

        from src.consts.drop_types import (DROP_TYPE_RESOURCE, DROP_TYPE_ITEM, DROP_TYPE_SHIP, DROP_TYPE_SKIN, DROP_TYPE_FURNITURE, DROP_TYPE_EQUIP, DROP_TYPE_LOVE_LETTER,
                                           DROP_TYPE_ICON_FRAME, DROP_TYPE_CHAT_FRAME, DROP_TYPE_COMBAT_UI_STYLE)
        from src.orm.item import add_item
        from src.orm.owned_equipment import add_owned_equipment
        from src.orm.owned_ship import add_ship
        from src.orm.owned_skin import give_skin
        from src.orm.resource import add_resource
        from src.orm.commander_furniture import add_commander_furniture
        for d in drops.values():
            cid = client.commander.commander_id
            if d.type in (DROP_TYPE_ICON_FRAME, DROP_TYPE_CHAT_FRAME, DROP_TYPE_COMBAT_UI_STYLE):
                from src.orm.commander_attire import grant_commander_attire_drop_sync
                grant_commander_attire_drop_sync(cid, d.type, d.id, d.number)
            elif d.type == DROP_TYPE_RESOURCE:
                await add_resource(cid, d.id, d.number)
            elif d.type in (DROP_TYPE_ITEM, DROP_TYPE_LOVE_LETTER):
                await add_item(cid, d.id, d.number)
            elif d.type == DROP_TYPE_EQUIP:
                add_owned_equipment(cid, d.id, d.number)
            elif d.type == DROP_TYPE_SHIP:
                for _ in range(d.number):
                    await add_ship(cid, d.id)
            elif d.type == DROP_TYPE_FURNITURE:
                await add_commander_furniture(cid, d.id, d.number)
            elif d.type == DROP_TYPE_SKIN:
                for _ in range(d.number):
                    await give_skin(cid, d.id)
        await save_limit_challenge_state(state)

    except Exception:
        await client.send_message(PACKET_ID, response)
        return

    sorted_drops = list(drops.values())
    sorted_drops.sort(key=lambda x: (x.type, x.id))

    response = protobuf.SC_24023(result=LIMIT_CHALLENGE_SUCCESS)
    for d in sorted_drops:
        entry = response.drop_list.add()
        entry.type = d.type
        entry.id = d.id
        entry.number = d.number
    await client.send_message(PACKET_ID, response)


def handle_limit_challenge_award(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_24022()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, PACKET_ID, e
    asyncio.create_task(_do_limit_challenge_award(client, payload))
    return 0, PACKET_ID, None
