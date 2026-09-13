import asyncio
import json
import time
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from src.orm.config_entry import list_config_entries_sync
from src.orm.city_rebuild_state import (
    get_or_create_city_rebuild_state,
    save_city_rebuild_state,
    CityRebuildState,
    CityRebuildRecruit,
)
from src.answer.activity_templates import load_activity_template


CITY_REBUILD_RESULT_SUCCESS = 0
CITY_REBUILD_RESULT_FAILED = 1

CITY_REBUILD_BUILDING_CATEGORY = "ShareCfg/activity_ninja_building.json"
CITY_REBUILD_BUFF_CATEGORY = "ShareCfg/activity_ninja_buff.json"

CITY_REBUILD_BUILDING_TYPE_REBUILD = 1


def _is_active_activity(raw) -> bool:
    if isinstance(raw, str):
        try:
            return json.loads(raw) != "stop"
        except (json.JSONDecodeError, TypeError):
            return True
    if isinstance(raw, dict):
        return raw.get("status", "") != "stop"
    return True


def _load_city_rebuild_state_for_request(client, act_id: int) -> Optional[CityRebuildState]:
    if act_id == 0:
        return None
    template = load_activity_template(act_id)
    if template is None:
        return None
    if not _is_active_activity(template.time):
        return None
    return get_or_create_city_rebuild_state(client.commander.commander_id, act_id)


def _load_city_rebuild_building_configs() -> dict:
    configs = {}
    for entry in list_config_entries_sync(CITY_REBUILD_BUILDING_CATEGORY):
        data = entry.data if hasattr(entry, "data") else entry
        if not isinstance(data, dict):
            continue
        cfg_id = data.get("id", 0)
        if cfg_id == 0:
            continue
        configs[cfg_id] = data
    return configs


def _load_city_rebuild_buff_upgrade_costs() -> tuple:
    costs = {}
    max_levels = {}
    for entry in list_config_entries_sync(CITY_REBUILD_BUFF_CATEGORY):
        data = entry.data if hasattr(entry, "data") else entry
        if not isinstance(data, dict):
            continue
        group = data.get("group", 0)
        level = data.get("level", 0)
        basic_cost = data.get("basic_cost", 0)
        if group == 0 or level == 0:
            continue
        if group not in costs:
            costs[group] = {}
        costs[group][level] = basic_cost
        if level > max_levels.get(group, 0):
            max_levels[group] = level
    return costs, max_levels


def _city_rebuild_pt_cost(values) -> int:
    if not isinstance(values, (list, tuple)) or len(values) < 3:
        return 0
    return int(values[2])


def _dedupe_uint32(values: list) -> list:
    seen = set()
    result = []
    for v in values:
        if v not in seen:
            seen.add(v)
            result.append(v)
    return result


def _contains_uint32(values: list, value: int) -> bool:
    return value in values


def _contains_recruit(recruits: list, role_id: int) -> bool:
    for r in recruits:
        if r.id == role_id:
            return True
    return False


def _build_ninja_pt(value: int):
    return protobuf.NINJA_PT(b=value, m=0, k=0)


def _build_city_rebuild_adjust(state: Optional[CityRebuildState]):
    time_value = 0
    left_hp = 0
    max_level = 1
    if state is not None:
        time_value = state.adjust_time
        left_hp = state.adjust_left_hp
        max_level = state.adjust_max_level
        if max_level == 0:
            max_level = state.max_level
        if max_level == 0:
            max_level = 1
    return protobuf.NINJA_ADJUST(
        time=time_value,
        left_hp=_build_ninja_pt(left_hp),
        max_level=max_level,
    )


def _build_city_rebuild_info(state: CityRebuildState):
    recruits = []
    for r in state.recruits:
        recruits.append(protobuf.NINJA_ROLE_RECRUIT(id=r.id, start_time=r.start_time))
    buffs = []
    for group, level in state.buffs.items():
        if level == 0:
            continue
        buffs.append(group * 1000 + level)
    buffs.sort()
    return protobuf.NINJA_INFO(
        pt=_build_ninja_pt(state.pt),
        builds=list(state.builds),
        roles=list(state.roles),
        recruits=recruits,
        buffs=buffs,
        max_level=state.max_level,
        cur_level=state.cur_level,
        max_display=state.max_display,
        adjust=_build_city_rebuild_adjust(state),
        summary_pt=_build_ninja_pt(state.summary_pt),
    )


def _build_city_rebuild_adjust_response_26063(result: int, state: Optional[CityRebuildState]):
    return protobuf.SC_26063(result=result, adjust=_build_city_rebuild_adjust(state))


def _build_city_rebuild_adjust_response_26065(result: int, state: Optional[CityRebuildState]):
    return protobuf.SC_26065(result=result, adjust=_build_city_rebuild_adjust(state))


def _build_city_rebuild_adjust_response_26067(result: int, state: Optional[CityRebuildState]):
    return protobuf.SC_26067(result=result, adjust=_build_city_rebuild_adjust(state))


def _build_city_rebuild_adjust_response_26071(result: int, state: Optional[CityRebuildState]):
    return protobuf.SC_26071(result=result, adjust=_build_city_rebuild_adjust(state))


def _build_city_rebuild_summary_response(result: int, state: Optional[CityRebuildState]):
    summary_pt = 0
    if state is not None:
        summary_pt = state.summary_pt
    return protobuf.SC_26069(
        result=result,
        summary=protobuf.NINJA_SUMMARY(
            summary_pt=_build_ninja_pt(summary_pt),
            award_list=[],
            adjust=_build_city_rebuild_adjust(state),
        ),
    )


def handle_city_rebuild_get_data(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_26060()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 26061, e

    state = _load_city_rebuild_state_for_request(client, payload.act_id)
    if state is None:
        asyncio.create_task(client.send_message(26061, protobuf.SC_26061(result=CITY_REBUILD_RESULT_FAILED)))
        return 0, 26061, None

    response = protobuf.SC_26061(result=CITY_REBUILD_RESULT_SUCCESS, info=_build_city_rebuild_info(state))
    asyncio.create_task(client.send_message(26061, response))
    return 0, 26061, None


def handle_city_rebuild_end_recruit(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_26062()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 26063, e

    state = _load_city_rebuild_state_for_request(client, payload.act_id)
    if state is None:
        asyncio.create_task(client.send_message(26063, _build_city_rebuild_adjust_response_26063(CITY_REBUILD_RESULT_FAILED, None)))
        return 0, 26063, None

    roles = _dedupe_uint32(list(payload.roles))
    if not roles:
        asyncio.create_task(client.send_message(26063, _build_city_rebuild_adjust_response_26063(CITY_REBUILD_RESULT_FAILED, None)))
        return 0, 26063, None

    recruit_by_id = {r.id: r for r in state.recruits}
    for role_id in roles:
        if role_id not in recruit_by_id:
            asyncio.create_task(client.send_message(26063, _build_city_rebuild_adjust_response_26063(CITY_REBUILD_RESULT_FAILED, None)))
            return 0, 26063, None

    role_set = set(roles)
    state.recruits = [r for r in state.recruits if r.id not in role_set]
    state.roles = list(state.roles) + roles
    state.summary_ready = True
    if state.summary_pt == 0:
        state.summary_pt = state.pt // 10
    try:
        save_city_rebuild_state(state)
    except Exception:
        asyncio.create_task(client.send_message(26063, _build_city_rebuild_adjust_response_26063(CITY_REBUILD_RESULT_FAILED, None)))
        return 0, 26063, None

    asyncio.create_task(client.send_message(26063, _build_city_rebuild_adjust_response_26063(CITY_REBUILD_RESULT_SUCCESS, state)))
    return 0, 26063, None


def handle_city_rebuild_building_action(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_26064()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 26065, e

    state = _load_city_rebuild_state_for_request(client, payload.act_id)
    if state is None:
        asyncio.create_task(client.send_message(26065, _build_city_rebuild_adjust_response_26065(CITY_REBUILD_RESULT_FAILED, None)))
        return 0, 26065, None

    buildings = _load_city_rebuild_building_configs()
    building = buildings.get(payload.building_id)
    if building is None:
        asyncio.create_task(client.send_message(26065, _build_city_rebuild_adjust_response_26065(CITY_REBUILD_RESULT_FAILED, None)))
        return 0, 26065, None

    need_level = building.get("need_level", 0)
    if need_level > 0 and state.cur_level < need_level:
        asyncio.create_task(client.send_message(26065, _build_city_rebuild_adjust_response_26065(CITY_REBUILD_RESULT_FAILED, None)))
        return 0, 26065, None

    cost = _city_rebuild_pt_cost(building.get("pt_cost", []))
    if state.pt < cost:
        asyncio.create_task(client.send_message(26065, _build_city_rebuild_adjust_response_26065(CITY_REBUILD_RESULT_FAILED, None)))
        return 0, 26065, None

    btype = building.get("type", 0)
    if btype == CITY_REBUILD_BUILDING_TYPE_REBUILD:
        if _contains_uint32(state.builds, payload.building_id):
            asyncio.create_task(client.send_message(26065, _build_city_rebuild_adjust_response_26065(CITY_REBUILD_RESULT_FAILED, None)))
            return 0, 26065, None
        state.builds = list(state.builds) + [payload.building_id]
    else:
        role_id = building.get("role_id", 0)
        if role_id == 0:
            role_id = building.get("id", 0)
        if _contains_uint32(state.roles, role_id) or _contains_recruit(state.recruits, role_id):
            asyncio.create_task(client.send_message(26065, _build_city_rebuild_adjust_response_26065(CITY_REBUILD_RESULT_FAILED, None)))
            return 0, 26065, None
        state.recruits = list(state.recruits) + [CityRebuildRecruit(id=role_id, start_time=int(time.time()))]

    state.pt -= cost
    state.summary_ready = True
    if state.summary_pt == 0:
        state.summary_pt = state.pt // 10
    try:
        save_city_rebuild_state(state)
    except Exception:
        asyncio.create_task(client.send_message(26065, _build_city_rebuild_adjust_response_26065(CITY_REBUILD_RESULT_FAILED, None)))
        return 0, 26065, None

    asyncio.create_task(client.send_message(26065, _build_city_rebuild_adjust_response_26065(CITY_REBUILD_RESULT_SUCCESS, state)))
    return 0, 26065, None


def handle_city_rebuild_upgrade_buff(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_26066()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 26067, e

    state = _load_city_rebuild_state_for_request(client, payload.act_id)
    if state is None:
        asyncio.create_task(client.send_message(26067, _build_city_rebuild_adjust_response_26067(CITY_REBUILD_RESULT_FAILED, None)))
        return 0, 26067, None

    if payload.group == 0 or payload.count == 0:
        asyncio.create_task(client.send_message(26067, _build_city_rebuild_adjust_response_26067(CITY_REBUILD_RESULT_FAILED, None)))
        return 0, 26067, None

    costs, max_levels = _load_city_rebuild_buff_upgrade_costs()
    group_costs = costs.get(payload.group, {})
    max_level = max_levels.get(payload.group, 0)
    if not group_costs or max_level == 0:
        asyncio.create_task(client.send_message(26067, _build_city_rebuild_adjust_response_26067(CITY_REBUILD_RESULT_FAILED, None)))
        return 0, 26067, None

    current_level = state.buffs.get(payload.group, 0)
    target_level = current_level + payload.count
    if target_level > max_level:
        asyncio.create_task(client.send_message(26067, _build_city_rebuild_adjust_response_26067(CITY_REBUILD_RESULT_FAILED, None)))
        return 0, 26067, None

    total_cost = 0
    for level in range(current_level + 1, target_level + 1):
        cost = group_costs.get(level)
        if cost is None:
            asyncio.create_task(client.send_message(26067, _build_city_rebuild_adjust_response_26067(CITY_REBUILD_RESULT_FAILED, None)))
            return 0, 26067, None
        total_cost += cost

    if state.pt < total_cost:
        asyncio.create_task(client.send_message(26067, _build_city_rebuild_adjust_response_26067(CITY_REBUILD_RESULT_FAILED, None)))
        return 0, 26067, None

    state.pt -= total_cost
    state.buffs[payload.group] = target_level
    state.summary_ready = True
    if state.summary_pt == 0:
        state.summary_pt = state.pt // 10
    try:
        save_city_rebuild_state(state)
    except Exception:
        asyncio.create_task(client.send_message(26067, _build_city_rebuild_adjust_response_26067(CITY_REBUILD_RESULT_FAILED, None)))
        return 0, 26067, None

    asyncio.create_task(client.send_message(26067, _build_city_rebuild_adjust_response_26067(CITY_REBUILD_RESULT_SUCCESS, state)))
    return 0, 26067, None


def handle_city_rebuild_result_summary(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_26068()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 26069, e

    state = _load_city_rebuild_state_for_request(client, payload.act_id)
    if state is None:
        asyncio.create_task(client.send_message(26069, _build_city_rebuild_summary_response(CITY_REBUILD_RESULT_FAILED, None)))
        return 0, 26069, None

    if not state.summary_ready:
        asyncio.create_task(client.send_message(26069, _build_city_rebuild_summary_response(CITY_REBUILD_RESULT_FAILED, state)))
        return 0, 26069, None

    state.summary_ready = False
    state.summary_pt = 0
    try:
        save_city_rebuild_state(state)
    except Exception:
        asyncio.create_task(client.send_message(26069, _build_city_rebuild_summary_response(CITY_REBUILD_RESULT_FAILED, state)))
        return 0, 26069, None

    response = protobuf.SC_26069(
        result=CITY_REBUILD_RESULT_SUCCESS,
        summary=protobuf.NINJA_SUMMARY(
            summary_pt=_build_ninja_pt(state.summary_pt),
            award_list=[],
            adjust=_build_city_rebuild_adjust(state),
        ),
    )
    asyncio.create_task(client.send_message(26069, response))
    return 0, 26069, None


def handle_city_rebuild_choose_level(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_26070()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 26071, e

    state = _load_city_rebuild_state_for_request(client, payload.act_id)
    if state is None:
        asyncio.create_task(client.send_message(26071, _build_city_rebuild_adjust_response_26071(CITY_REBUILD_RESULT_FAILED, None)))
        return 0, 26071, None

    if payload.level == 0 or payload.level > state.max_level:
        asyncio.create_task(client.send_message(26071, _build_city_rebuild_adjust_response_26071(CITY_REBUILD_RESULT_FAILED, None)))
        return 0, 26071, None

    state.cur_level = payload.level
    state.summary_ready = True
    try:
        save_city_rebuild_state(state)
    except Exception:
        asyncio.create_task(client.send_message(26071, _build_city_rebuild_adjust_response_26071(CITY_REBUILD_RESULT_FAILED, None)))
        return 0, 26071, None

    asyncio.create_task(client.send_message(26071, _build_city_rebuild_adjust_response_26071(CITY_REBUILD_RESULT_SUCCESS, state)))
    return 0, 26071, None


def handle_city_rebuild_init_time(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_26072()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 26073, e

    state = _load_city_rebuild_state_for_request(client, payload.act_id)
    if state is None:
        asyncio.create_task(client.send_message(26073, protobuf.SC_26073(result=CITY_REBUILD_RESULT_FAILED)))
        return 0, 26073, None

    state.adjust_time = int(time.time())
    if state.adjust_left_hp == 0:
        state.adjust_left_hp = 100
    state.adjust_max_level = state.max_level
    try:
        save_city_rebuild_state(state)
    except Exception:
        asyncio.create_task(client.send_message(26073, protobuf.SC_26073(result=CITY_REBUILD_RESULT_FAILED)))
        return 0, 26073, None

    response = protobuf.SC_26073(
        result=CITY_REBUILD_RESULT_SUCCESS,
        adjust=_build_city_rebuild_adjust(state),
    )
    asyncio.create_task(client.send_message(26073, response))
    return 0, 26073, None
