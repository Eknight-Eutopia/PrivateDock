import asyncio
import json
import time
from typing import Any, Optional

from src.connection.client import Client
from src.db.store import NotFoundError
from src.logger.logger import log_event, LOG_LEVEL_ERROR
from src.orm.config_entry import get_config_entry
from src.orm.guild_core import get_guild_by_id, get_commander_guild_membership
from src.orm.guild_office import get_guild_office_state, get_guild_weekly_task_state

GUILD_RESULT_SUCCESS = 0
GUILD_RESULT_FAILURE = 1
GUILD_RESULT_NAME_INVALID = 2015

GUILD_MIN_NAME_LENGTH = 1
GUILD_MAX_NAME_LENGTH = 20


def build_guild_chat_player(sender: dict) -> dict:
    if isinstance(sender, dict):
        return {
            "id": sender.get("commander_id", 0),
            "name": sender.get("name", ""),
            "level": sender.get("level", 0),
            "display": {
                "icon": sender.get("display_icon_id", 0),
                "skin": sender.get("display_skin_id", 0),
                "icon_frame": sender.get("icon_frame_id", 0),
                "chat_frame": sender.get("chat_frame_id", 0),
                "icon_theme": sender.get("icon_theme_id", 0),
                "marry_flag": 0,
                "transform_flag": 0,
            },
            "online": 0,
            "pre_online_time": sender.get("pre_online_time", 0),
        }
    return {
        "id": getattr(sender, "commander_id", 0),
        "name": getattr(sender, "name", ""),
        "level": getattr(sender, "level", 0),
        "display": {
            "icon": getattr(sender, "display_icon_id", 0),
            "skin": getattr(sender, "display_skin_id", 0),
            "icon_frame": getattr(sender, "icon_frame_id", 0),
            "chat_frame": getattr(sender, "chat_frame_id", 0),
            "icon_theme": getattr(sender, "icon_theme_id", 0),
            "marry_flag": 0,
            "transform_flag": 0,
        },
        "online": 0,
        "pre_online_time": getattr(sender, "pre_online_time", 0),
    }


def parse_config_uint(value: Any) -> tuple[int, bool]:
    if isinstance(value, (int, float)):
        if value < 0:
            return 0, False
        return int(value), True
    return 0, False

'''
def load_game_set_uint(key: str) -> int:
    entry = get_config_entry("ShareCfg/gameset.json", key)
    import json
    payload = json.loads(entry["data"]) if isinstance(entry["data"], str) else entry["data"]
    value, ok = _parse_config_uint(payload.get("key_value", 0))
    if not ok:
        raise ValueError(f"invalid key_value for {key}")
    return value
'''
def load_game_set_uint(key: str) -> int:
    entry = get_config_entry("ShareCfg/gameset.json", key)
    raw = entry.data if hasattr(entry, "data") else (entry.get("data") if isinstance(entry, dict) else entry)
    if isinstance(raw, str):
        raw = json.loads(raw)
    payload = raw
    value, ok = parse_config_uint(payload.get("key_value", 0))
    if not ok:
        raise ValueError(f"invalid key_value for {key}")
    return value


def normalize_guild_text(value: str) -> str:
    return value.strip()


from src.answer.guild.helpers import (
    is_valid_guild_name,
    is_valid_guild_faction,
    is_valid_guild_policy,
)


def build_guild_base_info(guild: Optional[dict]) -> dict:
    if guild is None:
        return {
            "id": 0, "policy": 0, "faction": 0, "name": "",
            "level": 0, "announce": "", "manifesto": "",
            "exp": 0, "member_count": 0,
            "change_faction_cd": 0, "kick_leader_cd": 0,
        }
    return {
        "id": guild.get("id", 0),
        "policy": guild.get("policy", 0),
        "faction": guild.get("faction", 0),
        "name": guild.get("name", ""),
        "level": guild.get("level", 0),
        "announce": guild.get("announce", ""),
        "manifesto": guild.get("manifesto", ""),
        "exp": guild.get("exp", 0),
        "member_count": guild.get("member_count", 0),
        "change_faction_cd": guild.get("change_faction_cd", 0),
        "kick_leader_cd": guild.get("kick_leader_cd", 0),
    }


def build_guild_expansion_info(guild: Optional[dict]) -> dict:
    capital = 0
    benefit_finish_time = 0
    last_benefit_finish_time = 0
    tech_cancel_cnt = 0
    weekly_task = {"id": 0, "progress": 0, "monday_0_clock": 0}

    if guild is not None:
        guild_id = guild.get("id", 0)
        capital = guild.get("capital", 0)
        try:
            office_state = get_guild_office_state(guild_id)
            benefit_finish_time = office_state.get("benefit_finish_time", 0)
            last_benefit_finish_time = office_state.get("last_benefit_finish_time", 0)
            tech_cancel_cnt = office_state.get("tech_cancel_cnt", 0)
        except NotFoundError as e:
            log_event("Answer", "guild_core_helpers", f"build_guild_expansion_info Error: {e}", LOG_LEVEL_ERROR)
        try:
            wts = get_guild_weekly_task_state(guild_id)
            weekly_task = {
                "id": wts.get("task_id", 0),
                "progress": wts.get("progress", 0),
                "monday_0_clock": wts.get("monday_0_clock", 0),
            }
        except NotFoundError as e:
            log_event("Answer", "guild_core_helpers", f"build_guild_expansion_info Error: {e}", LOG_LEVEL_ERROR)

    return {
        "capital": capital,
        "this_weekly_tasks": weekly_task,
        "benefit_finish_time": benefit_finish_time,
        "retreat_cnt": 0,
        "tech_cancel_cnt": tech_cancel_cnt,
        "last_benefit_finish_time": last_benefit_finish_time,
        "active_event_cnt": 0,
    }


def build_guild_member_info(member: dict) -> dict:
    pre_online = member.get("pre_online_time", 0)
    if pre_online == 0:
        #last_login = member.get("last_login", None)
        #if last_login is not None:
        #    pre_online = int(last_login.timestamp())
        pre_online = int(member.get("last_login", time.time()))
    return {
        "liveness": member.get("liveness", 0),
        "duty": member.get("duty", 0),
        "id": member.get("commander_id", 0),
        "name": member.get("commander_name", ""),
        "lv": member.get("commander_level", 0),
        "adv": member.get("manifesto", ""),
        "online": 0,
        "pre_online_time": pre_online,
        "display": {
            "icon": member.get("display_icon_id", 0),
            "skin": member.get("display_skin_id", 0),
            "icon_frame": member.get("icon_frame_id", 0),
            "chat_frame": member.get("chat_frame_id", 0),
            "icon_theme": member.get("icon_theme_id", 0),
            "marry_flag": 0,
            "transform_flag": 0,
        },
        "join_time": member.get("join_time", 0),
    }


def broadcast_guild_base_update(client: Client, guild_id: int):
    if client is None or client.server is None:
        return
    try:
        guild = get_guild_by_id(guild_id)
    except NotFoundError:
        return
    packet = {"guild": build_guild_base_info(guild)}
    for connected in client.server.list_clients():
        if connected is None or connected.commander is None:
            continue
        try:
            membership = get_commander_guild_membership(connected.commander.commander_id)
        except NotFoundError:
            continue
        if membership.get("guild_id", 0) != guild_id:
            continue
        asyncio.create_task(connected.send_message(60030, packet))
