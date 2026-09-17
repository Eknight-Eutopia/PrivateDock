import asyncio
import time

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.protobuf import protobuf

from .helpers import (
    RESULT_FAILURE,
    RESULT_SUCCESS,
    load_fleet_tech_configs,
    fleet_tech_index_of_tech,
    fleet_tech_expected_next_tech,
    fleet_tech_has_active_study,
    fleet_tech_build_max_additions,
    fleet_tech_build_tech_set_list,
    fleet_tech_normalize_overrides,
    fleet_tech_claim_drops,
    fleet_tech_merge_drop_list,
    fleet_tech_drop_map_to_slice,
    get_or_create_commander_fleet_tech_state,
    save_commander_fleet_tech_state,
    fleet_tech_upsert_group,
    fleet_tech_get_group,
    fleet_tech_set_attr_overrides,
)


def handle_technology_nation_proxy(_buffer: bytes, client: Client) -> tuple:
    groups, templates, _err = _load_configs()
    if _err is not None:
        return 0, 64000, _err

    try:
        state = get_or_create_commander_fleet_tech_state(client.commander.commander_id)
    except Exception as e:
        return 0, 64000, e

    for group_id in groups:
        fleet_tech_upsert_group(state, group_id)

    try:
        save_commander_fleet_tech_state(client.commander.commander_id, state)
    except Exception as e:
        return 0, 64000, e

    response = protobuf.SC_64000()
    group_ids = sorted(groups.keys())
    for group_id in group_ids:
        gs, ok = fleet_tech_get_group(state, group_id)
        if not ok:
            continue
        ft = protobuf.FLEETTECH()
        ft.group_id = group_id
        ft.effect_tech_id = gs.get("effect_tech_id", 0)
        ft.study_tech_id = gs.get("study_tech_id", 0)
        ft.study_finish_time = gs.get("study_finish_time", 0)
        ft.rewarded_tech = gs.get("rewarded_tech_id", 0)
        response.tech_list.append(ft)

    tech_set_list = fleet_tech_build_tech_set_list(state)
    for ts in tech_set_list:
        response.techset_list.append(ts)

    data = response.SerializeToString()
    header = generate_packet_header(64000, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 64000, None


def handle_start_camp_tech(buffer: bytes, client: Client) -> tuple:
    try:
        payload = protobuf.CS_64001()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 64002, e

    response = protobuf.SC_64002()
    response.result = RESULT_FAILURE
    group_id = payload.tech_group_id
    tech_id = payload.tech_id
    if group_id == 0 or tech_id == 0:
        asyncio.create_task(client.send_message(64002, response))
        return 0, 64002, None

    groups, templates, _err = _load_configs()
    if _err is not None:
        return 0, 64002, _err

    group = groups.get(group_id)
    if group is None or fleet_tech_index_of_tech(group, tech_id) < 0:
        asyncio.create_task(client.send_message(64002, response))
        return 0, 64002, None

    template = templates.get(tech_id)
    if template is None or (template.get("groupid", 0) != 0 and template.get("groupid", 0) != group_id):
        asyncio.create_task(client.send_message(64002, response))
        return 0, 64002, None

    if not _has_enough_resource(client, 1, template.get("cost", 0)):
        asyncio.create_task(client.send_message(64002, response))
        return 0, 64002, None

    now_unix = int(time.time())
    try:
        state = get_or_create_commander_fleet_tech_state(client.commander.commander_id)
        if fleet_tech_has_active_study(state):
            asyncio.create_task(client.send_message(64002, response))
            return 0, 64002, None
        group_state = fleet_tech_upsert_group(state, group_id)
        expected_tech_id, ok = fleet_tech_expected_next_tech(group, group_state.get("effect_tech_id", 0))
        if not ok or expected_tech_id != tech_id:
            asyncio.create_task(client.send_message(64002, response))
            return 0, 64002, None
        if not _consume_resource(client, 1, template.get("cost", 0)):
            asyncio.create_task(client.send_message(64002, response))
            return 0, 64002, None
        group_state["study_tech_id"] = tech_id
        group_state["study_finish_time"] = now_unix + template.get("time", 0)
        save_commander_fleet_tech_state(client.commander.commander_id, state)
    except Exception as e:
        asyncio.create_task(client.send_message(64002, response))
        return 0, 64002, e

    response.result = RESULT_SUCCESS
    asyncio.create_task(client.send_message(64002, response))
    return 0, 64002, None


def handle_finish_camp_technology(buffer: bytes, client: Client) -> tuple:
    try:
        payload = protobuf.CS_64003()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 64004, e

    response = protobuf.SC_64004()
    response.result = RESULT_FAILURE
    group_id = payload.tech_group_id
    if group_id == 0:
        asyncio.create_task(client.send_message(64004, response))
        return 0, 64004, None

    groups, _, _err = _load_configs()
    if _err is not None:
        return 0, 64004, _err

    group = groups.get(group_id)
    if group is None:
        asyncio.create_task(client.send_message(64004, response))
        return 0, 64004, None

    now_unix = int(time.time())
    try:
        state = get_or_create_commander_fleet_tech_state(client.commander.commander_id)
        group_state, ok = fleet_tech_get_group(state, group_id)
        if not ok or group_state.get("study_tech_id", 0) == 0 or group_state.get("study_finish_time", 0) > now_unix:
            asyncio.create_task(client.send_message(64004, response))
            return 0, 64004, None
        expected_tech_id, exp_ok = fleet_tech_expected_next_tech(group, group_state.get("effect_tech_id", 0))
        if not exp_ok or expected_tech_id != group_state.get("study_tech_id", 0):
            asyncio.create_task(client.send_message(64004, response))
            return 0, 64004, None
        group_state["effect_tech_id"] = group_state["study_tech_id"]
        group_state["study_tech_id"] = 0
        group_state["study_finish_time"] = 0
        save_commander_fleet_tech_state(client.commander.commander_id, state)
    except Exception as e:
        asyncio.create_task(client.send_message(64004, response))
        return 0, 64004, e

    response.result = RESULT_SUCCESS
    asyncio.create_task(client.send_message(64004, response))
    return 0, 64004, None


def handle_claim_fleet_tech_camp_award(buffer: bytes, client: Client) -> tuple:
    try:
        payload = protobuf.CS_64005()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 64006, e

    response = protobuf.SC_64006()
    response.result = RESULT_FAILURE
    group_id = payload.group_id
    tech_id = payload.tech_id
    if group_id == 0 or tech_id == 0:
        asyncio.create_task(client.send_message(64006, response))
        return 0, 64006, None

    groups, templates, _err = _load_configs()
    if _err is not None:
        return 0, 64006, _err

    group = groups.get(group_id)
    if group is None:
        asyncio.create_task(client.send_message(64006, response))
        return 0, 64006, None

    technology_index = fleet_tech_index_of_tech(group, tech_id)
    if technology_index < 0:
        asyncio.create_task(client.send_message(64006, response))
        return 0, 64006, None

    template = templates.get(tech_id)
    if template is None:
        asyncio.create_task(client.send_message(64006, response))
        return 0, 64006, None

    rewards = fleet_tech_claim_drops(template)

    try:
        state = get_or_create_commander_fleet_tech_state(client.commander.commander_id)
        group_state, ok = fleet_tech_get_group(state, group_id)
        if not ok:
            asyncio.create_task(client.send_message(64006, response))
            return 0, 64006, None
        complete_index = fleet_tech_index_of_tech(group, group_state.get("effect_tech_id", 0))
        if complete_index < 0 or technology_index > complete_index:
            asyncio.create_task(client.send_message(64006, response))
            return 0, 64006, None
        rewarded_index = fleet_tech_index_of_tech(group, group_state.get("rewarded_tech_id", 0))
        if technology_index <= rewarded_index or technology_index != rewarded_index + 1:
            asyncio.create_task(client.send_message(64006, response))
            return 0, 64006, None
        _apply_drops(client, rewards)
        group_state["rewarded_tech_id"] = tech_id
        save_commander_fleet_tech_state(client.commander.commander_id, state)
    except Exception as e:
        asyncio.create_task(client.send_message(64006, response))
        return 0, 64006, e

    response.result = RESULT_SUCCESS
    for r in rewards:
        response.rewards.append(r)
    asyncio.create_task(client.send_message(64006, response))
    return 0, 64006, None


def handle_claim_technology_camp_awards_one_step(buffer: bytes, client: Client) -> tuple:
    try:
        payload = protobuf.CS_64007()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 64008, e

    response = protobuf.SC_64008()
    response.result = RESULT_FAILURE
    if payload.type != 1:
        asyncio.create_task(client.send_message(64008, response))
        return 0, 64008, None

    groups, templates, _err = _load_configs()
    if _err is not None:
        return 0, 64008, _err

    try:
        state = get_or_create_commander_fleet_tech_state(client.commander.commander_id)
        merged_rewards = {}
        for group_state in state.get("groups", []):
            gs = group_state
            group = groups.get(gs.get("group_id", 0))
            if group is None:
                continue
            complete_index = fleet_tech_index_of_tech(group, gs.get("effect_tech_id", 0))
            if complete_index < 0:
                continue
            rewarded_index = fleet_tech_index_of_tech(group, gs.get("rewarded_tech_id", 0))
            if rewarded_index >= complete_index:
                continue
            techs = group.get("techs", [])
            for idx in range(rewarded_index + 1, complete_index + 1):
                tech_id = techs[idx]
                template = templates.get(tech_id)
                if template is None:
                    asyncio.create_task(client.send_message(64008, response))
                    return 0, 64008, None
                fleet_tech_merge_drop_list(merged_rewards, fleet_tech_claim_drops(template))
            gs["rewarded_tech_id"] = gs.get("effect_tech_id", 0)

        rewards = fleet_tech_drop_map_to_slice(merged_rewards)
        if rewards:
            _apply_drops(client, rewards)
        save_commander_fleet_tech_state(client.commander.commander_id, state)
    except Exception as e:
        asyncio.create_task(client.send_message(64008, response))
        return 0, 64008, e

    response.result = RESULT_SUCCESS
    for r in rewards:
        response.rewards.append(r)
    asyncio.create_task(client.send_message(64008, response))
    return 0, 64008, None


def handle_set_fleet_tech_attr_addition(buffer: bytes, client: Client) -> tuple:
    try:
        payload = protobuf.CS_64009()
        if buffer and buffer != b"\x00":
            payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 64010, e

    response = protobuf.SC_64010()
    response.result = RESULT_FAILURE

    try:
        state = get_or_create_commander_fleet_tech_state(client.commander.commander_id)
        techset_list = list(payload.techset_list)
        normalized, ok = fleet_tech_normalize_overrides(techset_list)
        if not ok:
            asyncio.create_task(client.send_message(64010, response))
            return 0, 64010, None
        fleet_tech_set_attr_overrides(state, normalized)
        save_commander_fleet_tech_state(client.commander.commander_id, state)
    except Exception as e:
        asyncio.create_task(client.send_message(64010, response))
        return 0, 64010, e

    response.result = RESULT_SUCCESS
    asyncio.create_task(client.send_message(64010, response))
    return 0, 64010, None


def _load_configs():
    try:
        groups, templates = load_fleet_tech_configs()
        return groups, templates, None
    except Exception as e:
        return None, None, e


def _has_enough_resource(client: Client, resource_type: int, amount: int) -> bool:
    from src.orm.resource import has_enough_resource
    return has_enough_resource(client.commander.commander_id, resource_type, amount)


def _consume_resource(client: Client, resource_type: int, amount: int) -> bool:
    from src.orm.resource import consume_resource
    try:
        consume_resource(client.commander.commander_id, resource_type, amount)
        res_map = getattr(client.commander, "owned_resources_map", None)
        if res_map is not None:
            entry = res_map.get(resource_type)
            if entry is not None:
                entry["amount"] = max(0, entry.get("amount", 0) - amount)
        return True
    except Exception:
        return False


def _apply_drops(client: Client, drops: list):
    for drop in drops:
        if drop is None:
            continue
        _apply_drop(client, drop.type, drop.id, drop.number)


def _apply_drop(client: Client, drop_type: int, drop_id: int, count: int):
    if drop_type == 1:
        from src.orm.resource import add_resource
        add_resource(client.commander.commander_id, drop_id, count)
    elif drop_type == 2:
        from src.orm.item import add_item
        add_item(client.commander.commander_id, drop_id, count)
