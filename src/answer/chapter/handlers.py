import asyncio
import json
import math
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from src.logger.logger import log_event, LOG_LEVEL_INFO, LOG_LEVEL_ERROR
from src.orm.remaster import try_consume_remaster_tickets_sync
from .helpers import (
    CHAPTER_OP_RETREAT, CHAPTER_OP_MOVE, CHAPTER_OP_AMBUSH,
    CHAPTER_OP_SUPPLY, CHAPTER_OP_REPAIR, CHAPTER_OP_REQUEST, CHAPTER_OP_ENEMY_ROUND,
    CHAPTER_OP_SUB_STATE, CHAPTER_OP_SUB_TELEPORT,
    CHAPTER_OP_STRATEGY,
    CHAPTER_CHANCE_BASE, CHAPTER_ATTACH_AMBUSH, CHAPTER_CELL_ACTIVE,
    CHAPTER_CELL_AMBUSH, ELITE_FLEET_STATE_FIELD, ChapterPos,
    find_chapter_group, find_chapter_cell_at, upsert_chapter_cell,
    load_chapter_template, parse_chapter_grids, find_move_path,
    build_move_path, build_pos, collect_chapter_ships,
    maybe_trigger_chapter_ambush, calculate_ambush_dodge_threshold,
    ensure_ambush_cell_has_expedition, repair_invalid_ambush_cells,
    calculate_operation_item_cost_rate,
    find_operation_buff_id, build_current_chapter_info,
    get_chapter_state_by_commander,
    upsert_chapter_state, delete_chapter_state, ensure_chapter_progress,
    get_chapter_drops, chapter_ambush_rand, CHAPTER_ATTACH_BOX, select_box_attachment_id,
    resolve_ambush_expedition,
    BOX_DROP, BOX_STRATEGY, BOX_AIRSTRIKE, BOX_ENEMY, BOX_SUPPLY, BOX_TORPEDO,
)
from src.answer.battle_session import _resolve_chapter_award_drop, _apply_drop_list
from src.orm.resource import has_enough_resource, consume_resource
from src.orm.chapter_repair import get_daily_repair_count, increment_daily_repair_count, repair_limits
from src.orm import get_config_entry


def handle_chapter_base_sync(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    response = protobuf.SC_13000()
    response.daily_repair_count = get_daily_repair_count(client.commander.commander_id)
    from src.connection.server import generate_packet_header

    row = get_chapter_state_by_commander(client.commander.commander_id)
    if row is None:
        data = response.SerializeToString()
        header = generate_packet_header(13000, data, client.packet_index)
        client.write_to_buffer(header + data)
        return 0, 13000, None

    state_bytes = row.state
    if not state_bytes:
        data = response.SerializeToString()
        header = generate_packet_header(13000, data, client.packet_index)
        client.write_to_buffer(header + data)
        return 0, 13000, None

    try:
        current = protobuf.CURRENTCHAPTERINFO()
        current.ParseFromString(bytes(state_bytes))
    except Exception as e:
        return 0, 13000, e

    template = load_chapter_template(current.id, current.loop_flag)
    if repair_invalid_ambush_cells(current, template):
        state_bytes = current.SerializeToString()
        upsert_chapter_state(client.commander.commander_id, current.id, state_bytes)

    response.current_chapter.CopyFrom(current)
    data = response.SerializeToString()
    header = generate_packet_header(13000, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 13000, None


def handle_chapter_tracking(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    log_event("Chapter/Tracking", "RawDebug", f"buffer={buffer.hex()}", LOG_LEVEL_INFO)
    try:
        payload = protobuf.CS_13101()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 13102, e

    if payload.fleet is None:
        response = protobuf.SC_13102()
        response.result = 1
        asyncio.create_task(client.send_message(13102, response))
        return 0, 13102, None

    if client.commander.owned_ships_map is None and client.commander.items_map is None:
        client.commander.load()

    template = load_chapter_template(payload.id, payload.loop_flag)
    if template is None:
        response = protobuf.SC_13102()
        response.result = 1
        asyncio.create_task(client.send_message(13102, response))
        return 0, 13102, None

    try:
        fleet = payload.fleet
        _teams = []
        for _tag, _tlist in (("main", fleet.main_team), ("sub", fleet.submarine_team), ("sup", fleet.support_team)):
            _ts = []
            for _t in _tlist:
                _ts.append({"fidx": _t.id, "ships": list(_t.ship_list), "cm": _t.commander_main, "cs": _t.commander_sub})
            _teams.append((_tag, _ts))
        log_event("Chapter/Tracking", "FleetDebug", f"chapter_id={payload.id} loop_flag={payload.loop_flag} operation_item={payload.operation_item} fleet_id={fleet.id} buffer={buffer.hex()} teams={_teams}", LOG_LEVEL_INFO)
    except Exception as _e:
        log_event("Chapter/Tracking", "FleetDebug", f"parse error: {_e} buffer={buffer.hex()}", LOG_LEVEL_INFO)

    rate = calculate_operation_item_cost_rate(payload.operation_item)
    oil_cost = int(float(template.oil) * rate)
    if not client.commander.has_enough_resource(2, oil_cost):
        response = protobuf.SC_13102()
        response.result = 1
        asyncio.create_task(client.send_message(13102, response))
        return 0, 13102, None

    if payload.operation_item != 0 and not client.commander.has_enough_item(payload.operation_item, 1):
        response = protobuf.SC_13102()
        response.result = 1
        asyncio.create_task(client.send_message(13102, response))
        return 0, 13102, None

    if oil_cost > 0:
        client.commander.consume_resource(2, oil_cost)
    if payload.operation_item != 0:
        client.commander.consume_item(payload.operation_item, 1)

    from src.answer.remaster_config import is_remaster_chapter
    is_remaster = is_remaster_chapter(payload.id)
    log_event("Chapter/Tracking", "RemasterCheck", f"chapter_id={payload.id} is_remaster={is_remaster}", LOG_LEVEL_INFO)
    if is_remaster:
        if not try_consume_remaster_tickets_sync(client.commander.commander_id, 5):
            log_event("Chapter/Tracking", "RemasterDeduct", "not enough tickets (need=5)", LOG_LEVEL_INFO)
            response = protobuf.SC_13102()
            response.result = 1
            asyncio.create_task(client.send_message(13102, response))
            return 0, 13102, None
        log_event("Chapter/Tracking", "RemasterDeduct", "deducted 5 tickets", LOG_LEVEL_INFO)

    operation_buff_id = find_operation_buff_id(payload.operation_item)
    owned_ships_map = getattr(client.commander, "owned_ships_map", None)
    if owned_ships_map is None and hasattr(client.commander, "load"):
        try:
            client.commander.load()
            owned_ships_map = getattr(client.commander, "owned_ships_map", None)
        except Exception:
            owned_ships_map = None
    try:
        current, _ = build_current_chapter_info(template, payload, operation_buff_id, owned_ships_map)
    except Exception as e:
        return 0, 13102, e

    state_bytes = current.SerializeToString()
    upsert_chapter_state(client.commander.commander_id, payload.id, state_bytes)
    ensure_chapter_progress(client.commander.commander_id, payload.id)

    try:
        from src.orm.daily_expedition import (
            get_chapter_map_type,
            increment_escort_expedition_count,
            MAP_TYPE_ESCORT,
        )
        if get_chapter_map_type(payload.id, payload.loop_flag) == MAP_TYPE_ESCORT:
            increment_escort_expedition_count(client.commander.commander_id)
    except Exception:
        pass

    response = protobuf.SC_13102()
    response.result = 0
    response.current_chapter.CopyFrom(current)
    try:
        _dump = []
        for _tag, _gl in (("main", current.main_group_list), ("sub", current.submarine_group_list), ("sup", current.support_group_list)):
            for _g in _gl:
                _dump.append({"tag": _tag, "gid": _g.id, "ships": [s.id for s in _g.ship_list], "pos": [int(_g.pos.row), int(_g.pos.column)]})
        log_event("Chapter/Tracking", "ResponseDebug", f"groups={_dump} time={current.time}", LOG_LEVEL_INFO)
    except Exception as _e:
        log_event("Chapter/Tracking", "ResponseDebug", f"err={_e}", LOG_LEVEL_INFO)
    asyncio.create_task(client.send_message(13102, response))
    return 0, 13102, None


def _load_box_config(box_id: int) -> Optional[dict]:
    from src.orm.config_entry import get_config_entry
    try:
        entry = get_config_entry("ShareCfg/box_data_template.json", str(box_id))
        if entry is None:
            return None
        data = entry.data
        if isinstance(data, str):
            import json
            data = json.loads(data)
        if isinstance(data, dict):
            return data
    except Exception as e:
        log_event("Chapter", "BoxConfig", f"box_id={box_id} load failed: {e}", LOG_LEVEL_ERROR)
    return None


def _process_box_effect(client: Client, current, group, pos, template, box_id: int, response=None):
    config = _load_box_config(box_id)
    if config is None:
        return None
    box_type = config.get('type', 0)
    effect_id = config.get('effect_id', 0)
    effect_arg = config.get('effect_arg', 0)
    if box_type == BOX_DROP:
        resolved = _resolve_chapter_award_drop(2, effect_id)
        if resolved is not None:
            rtype, rid, rcount = resolved
            _apply_drop_list(client, {f"{rtype}_{rid}": {"type": rtype, "id": rid, "number": rcount}})
            if response is not None:
                entry = protobuf.DROPINFO()
                entry.type = rtype
                entry.id = rid
                entry.number = rcount
                response.drop_list.append(entry)
        return None
    elif box_type == BOX_STRATEGY:
        # Grant a strategy to the fleet (beneficial). This is the client's
        # BoxStrategy box ("Event"): achievedStrategy(effect_id, effect_arg).
        # It must NOT spawn an enemy ambush.
        si = group.box_strategy_list.add()
        si.id = effect_id
        si.count = effect_arg if effect_arg else 1
        return None
    elif box_type in (BOX_AIRSTRIKE, BOX_ENEMY, BOX_TORPEDO):
        # These box types spawn an enemy fleet the player must fight.
        expedition_id = effect_id
        if expedition_id == 0 or _expedition_exists(expedition_id) is False:
            expedition_id = resolve_ambush_expedition(template)
        if expedition_id == 0:
            return None
        event_cell = protobuf.CHAPTERCELLINFO_P13()
        event_cell.pos.CopyFrom(build_pos(pos))
        event_cell.item_type = CHAPTER_ATTACH_AMBUSH
        event_cell.item_id = expedition_id
        event_cell.item_flag = CHAPTER_CELL_AMBUSH
        event_cell.item_data = effect_arg
        upsert_chapter_cell(current, event_cell)
        return event_cell
    elif box_type == BOX_SUPPLY:
        if group.bullet is not None and group.bullet < 5:
            group.bullet = min(5, group.bullet + effect_id)
        return None
    # BOX_BARRIER (0) and any unknown type: no enemy, no reward.
    return None


def _resolve_box_event_expedition_id(template, effect_id: int) -> int:
    expedition_id = resolve_ambush_expedition(template)
    if expedition_id != 0:
        return expedition_id
    if effect_id != 0:
        from src.orm.config_entry import get_config_entry
        if get_config_entry("sharecfgdata/expedition_data_template.json", str(effect_id)) is not None:
            return effect_id
    return 0


def _expedition_exists(expedition_id: int) -> bool:
    from src.orm.config_entry import get_config_entry
    return get_config_entry("sharecfgdata/expedition_data_template.json", str(expedition_id)) is not None


def handle_chapter_action(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_13103()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 13104, e

    row = get_chapter_state_by_commander(client.commander.commander_id)
    if row is None:
        log_event("Chapter/Action", "NoState", f"act={payload.act} group_id={payload.group_id} no chapter state row", LOG_LEVEL_INFO)
        response = protobuf.SC_13104()
        response.result = 1
        asyncio.create_task(client.send_message(13104, response))
        return 0, 13104, None

    try:
        current = protobuf.CURRENTCHAPTERINFO()
        current.ParseFromString(bytes(row.state))
    except Exception as e:
        return 0, 13104, e

    template_repair = load_chapter_template(current.id, current.loop_flag)
    if repair_invalid_ambush_cells(current, template_repair):
        state_bytes = current.SerializeToString()
        upsert_chapter_state(client.commander.commander_id, current.id, state_bytes)

    act = payload.act
    log_event("Chapter/Action", "OpDebug", f"act={act} group_id={payload.group_id} arg1={payload.act_arg_1} arg2={payload.act_arg_2} arg3={payload.act_arg_3} arg4={payload.act_arg_4} arg5={payload.act_arg_5} buffer={buffer.hex()}", LOG_LEVEL_INFO)

    if act == CHAPTER_OP_MOVE:
        group = find_chapter_group(current, payload.group_id)
        if group is None:
            response = protobuf.SC_13104()
            response.result = 1
            asyncio.create_task(client.send_message(13104, response))
            return 0, 13104, None

        template = load_chapter_template(current.id, current.loop_flag)
        if template is None:
            response = protobuf.SC_13104()
            response.result = 1
            asyncio.create_task(client.send_message(13104, response))
            return 0, 13104, None

        grids = parse_chapter_grids(template.grids)
        start = ChapterPos(row=group.pos.row, column=group.pos.column)
        end = ChapterPos(row=payload.act_arg_1, column=payload.act_arg_2)
        path = find_move_path(grids, start, end)
        if not path:
            response = protobuf.SC_13104()
            response.result = 1
            asyncio.create_task(client.send_message(13104, response))
            return 0, 13104, None

        map_update = []
        entered = []
        for step in path[1:]:
            group.pos.CopyFrom(build_pos(step))
            group.step_count = group.step_count + 1
            current.move_step_count = current.move_step_count + 1
            entered.append(step)
            ambush_cell = maybe_trigger_chapter_ambush(template, current, group, step, client)
            if ambush_cell is not None:
                map_update.append(ambush_cell)
                break

        # move_path holds the cells the fleet ENTERS, excluding the cell it
        # started from.  The client animates the whole list and derives the new
        # position from its last element (chapteroproutine.lua: doMove uses
        # fullpath = _.rest(move_path, 1), and this underscore's rest(t, 1)
        # returns every element from index 1 on; doRequest takes
        # move_path[#move_path]).  Including the start cell was off by one.
        move_path = build_move_path(entered)

        state_bytes = current.SerializeToString()
        upsert_chapter_state(client.commander.commander_id, current.id, state_bytes)

        response = protobuf.SC_13104()
        response.result = 0
        response.move_path.extend(move_path)
        response.map_update.extend(map_update)
        asyncio.create_task(client.send_message(13104, response))
        return 0, 13104, None

    elif act == CHAPTER_OP_AMBUSH:
        group = find_chapter_group(current, payload.group_id)
        if group is None:
            response = protobuf.SC_13104()
            response.result = 1
            asyncio.create_task(client.send_message(13104, response))
            return 0, 13104, None

        template = load_chapter_template(current.id, current.loop_flag)
        if template is None:
            response = protobuf.SC_13104()
            response.result = 1
            asyncio.create_task(client.send_message(13104, response))
            return 0, 13104, None

        pos = ChapterPos(row=group.pos.row, column=group.pos.column)
        idx, cell = find_chapter_cell_at(current, pos)
        if cell is None or cell.item_type != CHAPTER_ATTACH_AMBUSH:
            response = protobuf.SC_13104()
            response.result = 1
            asyncio.create_task(client.send_message(13104, response))
            return 0, 13104, None

        map_update = []
        arg = payload.act_arg_1
        if arg == 1:
            threshold = calculate_ambush_dodge_threshold(template, group, pos, client)
            if threshold > 0 and chapter_ambush_rand.randint(0, CHAPTER_CHANCE_BASE - 1) < threshold:
                current.cell_list.pop(idx)
            else:
                ensure_ambush_cell_has_expedition(cell, template)
                cell.item_flag = CHAPTER_CELL_ACTIVE
                map_update.append(cell)
        else:
            ensure_ambush_cell_has_expedition(cell, template)
            cell.item_flag = CHAPTER_CELL_ACTIVE
            map_update.append(cell)

        state_bytes = current.SerializeToString()
        upsert_chapter_state(client.commander.commander_id, current.id, state_bytes)

        response = protobuf.SC_13104()
        response.result = 0
        response.map_update.extend(map_update)
        response.ship_update.extend(collect_chapter_ships(current))
        response.ai_list.extend(current.ai_list)
        response.buff_list.extend(current.buff_list)
        response.cell_flag_list.extend(current.cell_flag_list)
        asyncio.create_task(client.send_message(13104, response))
        return 0, 13104, None

    elif act == CHAPTER_OP_SUPPLY:
        group = find_chapter_group(current, payload.group_id)
        if group is None:
            response = protobuf.SC_13104()
            response.result = 1
            asyncio.create_task(client.send_message(13104, response))
            return 0, 13104, None

        template = load_chapter_template(current.id, current.loop_flag)
        if template is None:
            response = protobuf.SC_13104()
            response.result = 1
            asyncio.create_task(client.send_message(13104, response))
            return 0, 13104, None

        _, cell = find_chapter_cell_at(current, ChapterPos(row=group.pos.row, column=group.pos.column))
        if cell is None or cell.item_type != 3 or cell.item_id == 0:
            response = protobuf.SC_13104()
            response.result = 1
            asyncio.create_task(client.send_message(13104, response))
            return 0, 13104, None

        max_ammo = template.ammo_total
        if max_ammo > group.bullet:
            refill = max_ammo - group.bullet
            if refill > cell.item_id:
                refill = cell.item_id
            group.bullet = group.bullet + refill
            cell.item_id = cell.item_id - refill

        state_bytes = current.SerializeToString()
        upsert_chapter_state(client.commander.commander_id, current.id, state_bytes)

        response = protobuf.SC_13104()
        response.result = 0
        asyncio.create_task(client.send_message(13104, response))
        return 0, 13104, None

    elif act == CHAPTER_OP_REQUEST:
        response = protobuf.SC_13104()
        response.result = 0
        response.map_update.extend(current.cell_list)
        response.ship_update.extend(collect_chapter_ships(current))
        response.ai_list.extend(current.ai_list)
        response.buff_list.extend(current.buff_list)
        response.cell_flag_list.extend(current.cell_flag_list)
        asyncio.create_task(client.send_message(13104, response))
        return 0, 13104, None

    elif act == 2:
        group = find_chapter_group(current, payload.group_id)
        if group is None:
            response = protobuf.SC_13104()
            response.result = 1
            asyncio.create_task(client.send_message(13104, response))
            return 0, 13104, None
        pos = ChapterPos(row=group.pos.row, column=group.pos.column)
        idx, cell = find_chapter_cell_at(current, pos)
        if cell is None or cell.item_type != CHAPTER_ATTACH_BOX or cell.item_flag == 1:
            response = protobuf.SC_13104()
            response.result = 1
            asyncio.create_task(client.send_message(13104, response))
            return 0, 13104, None
        template = load_chapter_template(current.id, current.loop_flag)
        cell.item_flag = 1
        map_update = [cell]
        response = protobuf.SC_13104()
        response.result = 0
        if template is not None:
            box_id = cell.item_id if cell.item_id != 0 else select_box_attachment_id(pos, template)
            if box_id != 0:
                extra = _process_box_effect(client, current, group, pos, template, box_id, response)
                if extra is not None:
                    map_update.append(extra)
        state_bytes = current.SerializeToString()
        upsert_chapter_state(client.commander.commander_id, current.id, state_bytes)
        response.map_update.extend(map_update)
        asyncio.create_task(client.send_message(13104, response))
        return 0, 13104, None

    elif act == CHAPTER_OP_ENEMY_ROUND:
        current.round = current.round + 1
        state_bytes = current.SerializeToString()
        upsert_chapter_state(client.commander.commander_id, current.id, state_bytes)

        response = protobuf.SC_13104()
        response.result = 0
        response.auto_battle_time_update = 0
        asyncio.create_task(client.send_message(13104, response))
        return 0, 13104, None

    elif act == CHAPTER_OP_SUB_STATE:
        current.is_submarine_auto_attack = payload.act_arg_1
        state_bytes = current.SerializeToString()
        upsert_chapter_state(client.commander.commander_id, current.id, state_bytes)

        response = protobuf.SC_13104()
        response.result = 0
        asyncio.create_task(client.send_message(13104, response))
        return 0, 13104, None

    elif act == CHAPTER_OP_SUB_TELEPORT:
        group = find_chapter_group(current, payload.group_id)
        if group is None:
            response = protobuf.SC_13104()
            response.result = 1
            asyncio.create_task(client.send_message(13104, response))
            return 0, 13104, None

        target = ChapterPos(row=payload.act_arg_1, column=payload.act_arg_2)
        template = load_chapter_template(current.id, current.loop_flag)
        if template is not None:
            grids = parse_chapter_grids(template.grids)
            start = ChapterPos(row=group.pos.row, column=group.pos.column)
            path = find_move_path(grids, start, target)
            if path is None:
                response = protobuf.SC_13104()
                response.result = 1
                asyncio.create_task(client.send_message(13104, response))
                return 0, 13104, None
            cost = max(0, math.ceil(1.1 * len(group.ship_list) * len(path) - 1e-05))
            if cost > 0:
                _cid = client.commander.commander_id
                if has_enough_resource(_cid, 2, cost):
                    consume_resource(_cid, 2, cost)

        group.pos.CopyFrom(build_pos(target))
        state_bytes = current.SerializeToString()
        upsert_chapter_state(client.commander.commander_id, current.id, state_bytes)

        response = protobuf.SC_13104()
        response.result = 0
        asyncio.create_task(client.send_message(13104, response))
        return 0, 13104, None

    elif act == CHAPTER_OP_RETREAT:
        try:
            _dump = []
            for _tag, _gl in (("main", current.main_group_list), ("sub", current.submarine_group_list), ("sup", current.support_group_list)):
                for _g in _gl:
                    _dump.append({"tag": _tag, "gid": _g.id, "ships": [s.id for s in _g.ship_list]})
            log_event("Chapter/Action", "RetreatDebug", f"groups={_dump} round={current.round} time={current.time} group_id={payload.group_id}", LOG_LEVEL_INFO)
        except Exception as _e:
            log_event("Chapter/Action", "RetreatDebug", f"err={_e}", LOG_LEVEL_INFO)

        if payload.group_id == 0:
            delete_chapter_state(client.commander.commander_id)
        else:
            _recalled = False
            for _gl in (current.main_group_list, current.submarine_group_list, current.support_group_list):
                for _i in range(len(_gl) - 1, -1, -1):
                    if _gl[_i].id == payload.group_id:
                        del _gl[_i]
                        _recalled = True
            if not _recalled:
                log_event("Chapter/Action", "RetreatUnknownGroup", f"group_id={payload.group_id} not present in chapter state", LOG_LEVEL_INFO)
            _remaining = len(current.main_group_list) + len(current.submarine_group_list) + len(current.support_group_list)
            if _remaining == 0:
                delete_chapter_state(client.commander.commander_id)
            else:
                _state_bytes = current.SerializeToString()
                upsert_chapter_state(client.commander.commander_id, current.id, _state_bytes)

        response = protobuf.SC_13104()
        response.result = 0

        if payload.group_id == 0 and getattr(payload, "act_arg_1", 0) == 1:
            try:
                import time as _time
                from src.orm.chapter_auto import upsert_chapter_auto_record
                duration = max(1, int(_time.time()) - getattr(current, "time", 0))
                best = upsert_chapter_auto_record(client.commander.commander_id, 1, current.id, duration)
                response.auto_battle_time_update = best
            except Exception as _e:
                log_event("Chapter/AutoRecord", "Failed to record auto battle time", f"err={_e}", LOG_LEVEL_ERROR)

        asyncio.create_task(client.send_message(13104, response))
        return 0, 13104, None

    elif act == CHAPTER_OP_REPAIR:
        _ship_id = payload.act_arg_1
        _target = None
        for _gl in (current.main_group_list, current.submarine_group_list, current.support_group_list):
            for _group in _gl:
                for _ship in _group.ship_list:
                    if _ship.id == _ship_id:
                        _target = _ship
                        break
                if _target is not None:
                    break
            if _target is not None:
                break
        if _target is None:
            response = protobuf.SC_13104()
            response.result = 1
            asyncio.create_task(client.send_message(13104, response))
            return 0, 13104, None

        _free, _charge, _total, _gem = repair_limits()
        _cid = client.commander.commander_id
        _count = get_daily_repair_count(_cid)
        if _count >= _total:
            response = protobuf.SC_13104()
            response.result = 1
            asyncio.create_task(client.send_message(13104, response))
            return 0, 13104, None
        if _count >= _free:
            if not has_enough_resource(_cid, 4, _gem):
                response = protobuf.SC_13104()
                response.result = 1
                asyncio.create_task(client.send_message(13104, response))
                return 0, 13104, None
            consume_resource(_cid, 4, _gem)

        _target.hp_rant = 10000
        increment_daily_repair_count(_cid)
        _state_bytes = current.SerializeToString()
        upsert_chapter_state(_cid, current.id, _state_bytes)

        response = protobuf.SC_13104()
        response.result = 0
        response.ship_update.extend(collect_chapter_ships(current))
        asyncio.create_task(client.send_message(13104, response))
        return 0, 13104, None

    elif act == CHAPTER_OP_STRATEGY:
        _strategy_id = payload.act_arg_1
        _cfg = None
        _entry = get_config_entry("ShareCfg/strategy_data_template.json", str(_strategy_id))
        if _entry is not None:
            _data = _entry.data
            if isinstance(_data, str):
                try:
                    _data = json.loads(_data)
                except (ValueError, TypeError):
                    _data = None
            _cfg = _data

        if not isinstance(_cfg, dict):
            response = protobuf.SC_13104()
            response.result = 1
            asyncio.create_task(client.send_message(13104, response))
            return 0, 13104, None

        _stype = _cfg.get("type", 0)

        _strat = None
        for _s in current.chapter_strategy_list:
            if _s.id == _strategy_id:
                _strat = _s
                break

        if _stype == 2:  # active/consume strategy (repair, exchange, ...)
            if _strategy_id == 4:  # Emergency Repair
                _pct = 10
                try:
                    _arg = _cfg.get("arg", [None, 10])
                    _pct = int(_arg[1]) if len(_arg) > 1 else 10
                except (ValueError, TypeError, IndexError):
                    _pct = 10
                _heal = _pct * 100  # hp_rant 0..10000 == percent*100
                for _gl in (current.main_group_list, current.submarine_group_list, current.support_group_list):
                    for _group in _gl:
                        for _ship in _group.ship_list:
                            if _ship.hp_rant < 10000:
                                _ship.hp_rant = min(10000, _ship.hp_rant + _heal)
            # exchange (id=9) is applied entirely client-side via a fleet-line swap
            if _strat is not None:
                _strat.count = max(0, _strat.count - 1)
        elif _stype in (1, 3, 4, 5):
            # formation / submarine / support / sonar: client applies locally;
            # consume the tracked server-side use if present.
            if _strat is not None:
                _strat.count = max(0, _strat.count - 1)
        # unknown type: succeed without effect

        _state_bytes = current.SerializeToString()
        upsert_chapter_state(client.commander.commander_id, current.id, _state_bytes)

        response = protobuf.SC_13104()
        response.result = 0
        response.ship_update.extend(collect_chapter_ships(current))
        asyncio.create_task(client.send_message(13104, response))
        return 0, 13104, None

    else:
        log_event("Chapter/Action", "UnknownAct", f"unhandled act={act} payload={payload}", LOG_LEVEL_INFO)
        response = protobuf.SC_13104()
        response.result = 1
        asyncio.create_task(client.send_message(13104, response))
        return 0, 13104, None


def handle_chapter_battle_result(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_13106()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 13105, e

    row = get_chapter_state_by_commander(client.commander.commander_id)
    if row is None:
        response = protobuf.SC_13105()
        response.map_update.extend([])
        response.ai_list.extend([])
        response.add_flag_list.extend([])
        response.del_flag_list.extend([])
        response.buff_list.extend([])
        response.cell_flag_list.extend([])
        asyncio.create_task(client.send_message(13105, response))
        return 0, 13105, None

    try:
        current = protobuf.CURRENTCHAPTERINFO()
        current.ParseFromString(bytes(row.state))
    except Exception as e:
        return 0, 13105, e

    response = protobuf.SC_13105()
    response.map_update.extend(current.cell_list)
    response.ai_list.extend(current.ai_list)
    response.add_flag_list.extend([])
    response.del_flag_list.extend([])
    response.buff_list.extend(current.buff_list)
    response.cell_flag_list.extend(current.cell_flag_list)
    asyncio.create_task(client.send_message(13105, response))
    return 0, 13105, None


def handle_get_chapter_drop_ship_list(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_13109()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 13110, e

    chapter_id = payload.id
    if chapter_id == 0:
        return 0, 13110, Exception("missing chapter id")

    template = load_chapter_template(chapter_id, 0)
    if template is None:
        return 0, 13110, Exception("chapter not found")

    drops = get_chapter_drops(client.commander.commander_id, chapter_id)
    unique = sorted(set(drops))

    response = protobuf.SC_13110()
    response.drop_ship_list.extend(unique)
    asyncio.create_task(client.send_message(13110, response))
    return 0, 13110, None


def handle_remove_elite_target_ship(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_13111()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 13112, e

    ship_id = payload.ship_id
    if client.commander.owned_ships_map is None:
        client.commander.load()
    if ship_id not in client.commander.owned_ships_map:
        return 0, 13112, Exception(f"ship not owned: {ship_id}")

    row = get_chapter_state_by_commander(client.commander.commander_id)
    if row is None:
        response = _build_chapter_elite_fleet_response([])
        asyncio.create_task(client.send_message(13112, response))
        return 0, 13112, None

    state_bytes = bytes(row["state"])
    if not state_bytes:
        response = _build_chapter_elite_fleet_response([])
        asyncio.create_task(client.send_message(13112, response))
        return 0, 13112, None

    try:
        fleets = _parse_elite_fleet_from_state(state_bytes)
    except Exception as e:
        return 0, 13112, e

    updated = _remove_ship_from_fleets(fleets, ship_id)
    try:
        updated_state = _set_elite_fleet_in_state(state_bytes, updated)
    except Exception as e:
        return 0, 13112, e

    upsert_chapter_state(client.commander.commander_id, row["chapter_id"], updated_state)

    response = _build_chapter_elite_fleet_response(updated)
    asyncio.create_task(client.send_message(13112, response))
    return 0, 13112, None


# ── Elite fleet helpers ──


def _build_chapter_elite_fleet_response(fleets: list):
    response = protobuf.SC_13112()
    for f in fleets:
        response.fleet_list.append(f)
    return response


def _parse_elite_fleet_from_state(state: bytes) -> list:
    if not state:
        return []
    current = protobuf.CURRENTCHAPTERINFO()
    current.ParseFromString(state)
    fleets = []
    idx = 0
    data = current.SerializeToString()
    while idx < len(data):
        tag, idx = read_varint(data, idx)
        field_num = tag >> 3
        wire_type = tag & 7
        if wire_type == 2:
            length, idx = read_varint(data, idx)
            field_data = data[idx:idx + length]
            idx += length
            if field_num == ELITE_FLEET_STATE_FIELD:
                fleet = protobuf.FLEET_INFO()
                fleet.ParseFromString(field_data)
                fleets.append(fleet)
        elif wire_type == 0:
            _, idx = read_varint(data, idx)
        elif wire_type == 1:
            idx += 8
        elif wire_type == 5:
            idx += 4
        else:
            break
    return fleets


def _set_elite_fleet_in_state(state: bytes, fleets: list) -> bytes:
    current = protobuf.CURRENTCHAPTERINFO()
    current.ParseFromString(state)
    known_fields = set(f.number for f in current.DESCRIPTOR.fields)
    data = state
    idx = 0
    out = bytearray()
    while idx < len(data):
        tag, idx = read_varint(data, idx)
        field_num = tag >> 3
        wire_type = tag & 7
        tag_bytes = encode_varint(tag)
        if wire_type == 2:
            length, idx = read_varint(data, idx)
            field_data = data[idx:idx + length]
            idx += length
            if field_num not in known_fields:
                if field_num != ELITE_FLEET_STATE_FIELD:
                    out.extend(tag_bytes)
                    out.extend(encode_varint(length))
                    out.extend(field_data)
        elif wire_type == 0:
            val, idx = read_varint(data, idx)
            if field_num not in known_fields:
                out.extend(tag_bytes)
                out.extend(encode_varint(val))
        elif wire_type == 1:
            val = data[idx:idx + 8]
            idx += 8
            if field_num not in known_fields:
                out.extend(tag_bytes)
                out.extend(val)
        elif wire_type == 5:
            val = data[idx:idx + 4]
            idx += 4
            if field_num not in known_fields:
                out.extend(tag_bytes)
                out.extend(val)
        else:
            break

    for fleet in fleets:
        fleet_data = fleet.SerializeToString()
        tag = (ELITE_FLEET_STATE_FIELD << 3) | 2
        out.extend(encode_varint(tag))
        out.extend(encode_varint(len(fleet_data)))
        out.extend(fleet_data)

    result = bytes(out)
    current2 = protobuf.CURRENTCHAPTERINFO()
    current2.ParseFromString(result)
    return current2.SerializeToString()


def _remove_ship_from_fleets(fleets: list, ship_id: int) -> list:
    for fleet in fleets:
        _remove_ship_from_teams(fleet.main_team, ship_id)
        _remove_ship_from_teams(fleet.submarine_team, ship_id)
        _remove_ship_from_teams(fleet.support_team, ship_id)
    return fleets


def _remove_ship_from_teams(teams: list, ship_id: int):
    for team in teams:
        ships = list(team.ship_list)
        filtered = [sid for sid in ships if sid != ship_id]
        team.ship_list[:] = filtered

from src.protobuf.varint import read_varint, encode_varint
