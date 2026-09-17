import asyncio
import re
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

COMMANDER_RESULT_OK = 0
COMMANDER_RESULT_FAIL = 1

COMMANDER_NAME_MAX_LENGTH = 12
COMMANDER_PREFAB_MAX_ID = 5
COMMANDER_PREFAB_MAX_SLOTS = 2


def handle_fetch_commander_candidate_talents(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_25010()
    payload.ParseFromString(buffer)

    commander_id = payload.commanderid
    try:
        from src.orm.commander_packet import get_or_create_commander_packet_state
        state = get_or_create_commander_packet_state(
            client.commander.commander_id, commander_id,
        )
        candidates = _build_commander_talent_candidates(state)
        if not candidates:
            asyncio.create_task(client.send_message(25011, protobuf.SC_25011(result=COMMANDER_RESULT_FAIL)))
            return 0, 25011, None

        if isinstance(state, dict):
            state["pending_ability_ids"] = candidates
        else:
            state.pending_ability_ids = candidates

        from src.orm.commander_packet import save_commander_packet_state
        save_commander_packet_state(state)

        response = protobuf.SC_25011(result=COMMANDER_RESULT_OK)
        response.abilityid.extend(candidates)
    except (ImportError, AttributeError):
        asyncio.create_task(client.send_message(25011, protobuf.SC_25011(result=COMMANDER_RESULT_FAIL)))
        return 0, 25011, None

    asyncio.create_task(client.send_message(25011, response))
    return 0, 25011, None


def handle_learn_commander_talent(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_25012()
    payload.ParseFromString(buffer)

    asyncio.create_task(client.send_message(25013, protobuf.SC_25013(result=COMMANDER_RESULT_FAIL)))
    return 0, 25013, None


def handle_reset_commander_talents(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_25014()
    payload.ParseFromString(buffer)

    asyncio.create_task(client.send_message(25015, protobuf.SC_25015(result=COMMANDER_RESULT_FAIL)))
    return 0, 25015, None


def handle_set_commander_lock_state(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_25016()
    payload.ParseFromString(buffer)

    from src.orm.commander_meow import update_commander_meow_lock
    try:
        update_commander_meow_lock(client.commander.commander_id, payload.commanderid, payload.flag)
        res = COMMANDER_RESULT_OK
    except Exception:
        res = COMMANDER_RESULT_FAIL

    asyncio.create_task(client.send_message(25017, protobuf.SC_25017(result=res)))
    return 0, 25017, None


def handle_rename_commander(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_25020()
    payload.ParseFromString(buffer)

    import time
    from src.orm.commander_meow import update_commander_meow_name
    try:
        now = int(time.time())
        update_commander_meow_name(client.commander.commander_id, payload.commanderid, payload.name, now)
        res = COMMANDER_RESULT_OK
    except Exception:
        res = COMMANDER_RESULT_FAIL

    asyncio.create_task(client.send_message(25021, protobuf.SC_25021(result=res)))
    return 0, 25021, None


def handle_set_commander_prefab_fleet(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_25022()
    payload.ParseFromString(buffer)

    prefab_id = payload.id
    if not _is_valid_prefab_id(prefab_id):
        asyncio.create_task(client.send_message(25023, protobuf.SC_25023(result=COMMANDER_RESULT_FAIL)))
        return 0, 25023, None

    input_slots = payload.commandersid
    if not input_slots:
        asyncio.create_task(client.send_message(25023, protobuf.SC_25023(result=COMMANDER_RESULT_FAIL)))
        return 0, 25023, None

    from src.orm.commander_meow import get_commander_meow
    from src.orm.commander_prefab import save_commander_prefab_fleet

    slots_by_pos = {}
    non_zero_count = 0
    for slot in input_slots:
        pos = slot.pos
        if pos == 0 or pos > COMMANDER_PREFAB_MAX_SLOTS:
            asyncio.create_task(client.send_message(25023, protobuf.SC_25023(result=COMMANDER_RESULT_FAIL)))
            return 0, 25023, None
        if pos in slots_by_pos:
            asyncio.create_task(client.send_message(25023, protobuf.SC_25023(result=COMMANDER_RESULT_FAIL)))
            return 0, 25023, None

        cid = slot.id
        if cid != 0:
            meow = get_commander_meow(client.commander.commander_id, cid)
            if meow is None:
                asyncio.create_task(client.send_message(25023, protobuf.SC_25023(result=COMMANDER_RESULT_FAIL)))
                return 0, 25023, None
            non_zero_count += 1
        slots_by_pos[pos] = cid

    if non_zero_count == 0:
        asyncio.create_task(client.send_message(25023, protobuf.SC_25023(result=COMMANDER_RESULT_FAIL)))
        return 0, 25023, None

    sorted_slots = [
        {"pos": pos, "id": slots_by_pos[pos]}
        for pos in sorted(slots_by_pos.keys())
    ]
    try:
        save_commander_prefab_fleet(
            client.commander.commander_id,
            prefab_id,
            sorted_slots,
        )
        res = COMMANDER_RESULT_OK
    except Exception:
        res = COMMANDER_RESULT_FAIL

    asyncio.create_task(client.send_message(25023, protobuf.SC_25023(result=res)))
    return 0, 25023, None


def handle_rename_commander_prefab_fleet(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_25024()
    payload.ParseFromString(buffer)

    prefab_id = payload.id
    if not _is_valid_prefab_id(prefab_id):
        asyncio.create_task(client.send_message(25025, protobuf.SC_25025(result=COMMANDER_RESULT_FAIL)))
        return 0, 25025, None

    from src.orm.commander_prefab import get_commander_prefab_fleet, rename_commander_prefab_fleet

    prefab = get_commander_prefab_fleet(client.commander.commander_id, prefab_id)
    current_name = prefab.get("name", "") if prefab else ""
    name = str(payload.name).strip()

    if not _is_valid_commander_name(name, current_name, COMMANDER_NAME_MAX_LENGTH):
        asyncio.create_task(client.send_message(25025, protobuf.SC_25025(result=COMMANDER_RESULT_FAIL)))
        return 0, 25025, None

    try:
        success = rename_commander_prefab_fleet(
            client.commander.commander_id,
            prefab_id,
            name,
            cooldown_seconds=60,
        )
        res = COMMANDER_RESULT_OK if success else COMMANDER_RESULT_FAIL
    except Exception:
        res = COMMANDER_RESULT_FAIL

    asyncio.create_task(client.send_message(25025, protobuf.SC_25025(result=res)))
    return 0, 25025, None


def _build_commander_talent_candidates(state) -> list:
    pending = state.get("pending_ability_ids", []) if isinstance(state, dict) else getattr(state, "pending_ability_ids", [])
    if pending:
        return []

    ability_ids = state.get("ability_ids", []) if isinstance(state, dict) else getattr(state, "ability_ids", [])
    learned_set = set(ability_ids)

    candidate_set = set()
    for ability_id in ability_ids:
        try:
            from src.orm.commander_meow import get_commander_ability_template
            template = get_commander_ability_template()
            template_next = template.get("next", 0) if isinstance(template, dict) else getattr(template, "next", 0)
            if template_next and template_next not in learned_set:
                candidate_set.add(template_next)
        except (ImportError, AttributeError, Exception):
            pass

    if not candidate_set:
        try:
            from src.orm.commander_meow import list_commander_ability_groups
            groups = list_commander_ability_groups()
            learned_groups = set()
            for ability_id in ability_ids:
                try:
                    from src.orm.commander_meow import get_commander_ability_template
                    template = get_commander_ability_template()
                    gid = template.get("group_id", 0) if isinstance(template, dict) else getattr(template, "group_id", 0)
                    learned_groups.add(gid)
                except Exception:
                    pass
            for group in groups:
                gid = group.get("id", 0) if isinstance(group, dict) else getattr(group, "id", 0)
                if gid in learned_groups:
                    continue
                ability_list = group.get("ability_list", []) if isinstance(group, dict) else getattr(group, "ability_list", [])
                for aid in ability_list:
                    if aid not in learned_set:
                        candidate_set.add(aid)
                        break
        except (ImportError, AttributeError):
            pass

    candidates = sorted(candidate_set)
    return candidates[:3]


def _resolve_commander_reset_cost(costs: list, used_pt: int) -> int:
    if not costs:
        return 0
    if used_pt == 0:
        return 0
    idx = used_pt - 1
    if idx < 0:
        idx = 0
    if idx >= len(costs):
        idx = len(costs) - 1
    return costs[idx]


def _is_valid_commander_name(name: str, current_name: str, max_length: int) -> bool:
    if not name or name == current_name:
        return False
    if len(name) < 1 or len(name) > max_length:
        return False
    try:
        from src.config.config import current as get_config
        cfg = get_config()
        create_cfg = cfg.get("create_player", {}) if isinstance(cfg, dict) else getattr(cfg, "create_player", {})
        lower_name = name.lower()
        blacklist = create_cfg.get("name_blacklist", []) if isinstance(create_cfg, dict) else getattr(create_cfg, "name_blacklist", [])
        for blocked in blacklist:
            blocked = str(blocked).strip()
            if not blocked:
                continue
            if blocked.lower() in lower_name:
                return False
        illegal_pattern = create_cfg.get("name_illegal_pattern", "") if isinstance(create_cfg, dict) else getattr(create_cfg, "name_illegal_pattern", "")
        if illegal_pattern:
            if re.search(illegal_pattern, name):
                return False
    except Exception:
        pass
    return True


def _is_valid_prefab_id(prefab_id: int) -> bool:
    return 1 <= prefab_id <= COMMANDER_PREFAB_MAX_ID


def _contains_uint32_value(values: list, target: int) -> bool:
    return target in values


def _same_uint32_set(left: list, right: list) -> bool:
    if len(left) != len(right):
        return False
    if not left:
        return True
    counts = {}
    for v in left:
        counts[v] = counts.get(v, 0) + 1
    for v in right:
        counts[v] = counts.get(v, 0) - 1
        if counts[v] < 0:
            return False
    return all(c == 0 for c in counts.values())
