import asyncio
import json
from typing import Optional

from src.connection.client import Client
from src.connection.server import send_proto_message
from src.protobuf import protobuf
from src.answer.activity_templates import load_activity_template
from src.answer.activity_constants import ACTIVITY_TYPE_BOSS_BATTLE_MARK_2

ACTIVITY_EVENT_WORLD_BOSS_CATEGORY = "ShareCfg/activity_event_worldboss.json"


def _parse_uint32_raw_list(raw) -> list:
    if raw is None:
        return []
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return []
    if isinstance(data, list):
        if data and isinstance(data[0], list):
            flat = []
            for group in data:
                flat.extend(int(x) for x in group)
            return flat
        return [int(x) for x in data]
    return []


def _load_activity_boss_list(template) -> list:
    from src.orm.config_entry import get_config_entry
    try:
        raw = get_config_entry(ACTIVITY_EVENT_WORLD_BOSS_CATEGORY, str(template.config_id))
    except Exception:
        return []

    cfg = raw if isinstance(raw, dict) else None
    if not cfg:
        return []

    boss_ids = _parse_uint32_raw_list(cfg.get("boss_id"))
    stage_hp = _parse_uint32_raw_list(cfg.get("stage_hp"))

    bosses = []
    for idx, boss_id in enumerate(boss_ids):
        boss_hp = stage_hp[idx] if idx < len(stage_hp) else 0
        entry = protobuf.BOSS4TH()
        entry.id = boss_id
        entry.boss_hp = boss_hp
        entry.death = 0
        entry.hour_traffic = 0
        entry.hour_off = 0
        bosses.append(entry)
    return bosses


def handle_activity_boss_page_update(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_26031()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 26032, e

    act_id = payload.act_id
    response = protobuf.SC_26032(result=1, boss_hp=0, death=0)

    template = load_activity_template(act_id)
    if template is None or template.type != ACTIVITY_TYPE_BOSS_BATTLE_MARK_2:
        asyncio.create_task(send_proto_message(26032, client, response))
        return 0, 26032, None

    bosses = _load_activity_boss_list(template)

    response.result = 0
    if bosses:
        response.boss_hp = bosses[0].boss_hp
        response.death = bosses[0].death

    asyncio.create_task(send_proto_message(26032, client, response))
    return 0, 26032, None


def handle_get_boss_4th_info(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_26081()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 26082, e

    act_id = payload.act_id
    response = protobuf.SC_26082(result=1)

    template = load_activity_template(act_id)
    if template is None or template.type != ACTIVITY_TYPE_BOSS_BATTLE_MARK_2:
        asyncio.create_task(send_proto_message(26082, client, response))
        return 0, 26082, None

    bosses = _load_activity_boss_list(template)
    response.result = 0
    for b in bosses:
        response.boss_list.append(b)
    asyncio.create_task(send_proto_message(26082, client, response))
    return 0, 26082, None
