from datetime import datetime
from fastapi import Request
from src.api.response.response import ok as success, error
from src.api.types import *

from src.db.store import NotFoundError
from .players import parse_commander_id, parse_path_uint32, parse_pagination, write_commander_error
from src.orm import admin
from src.orm.chapter import (
    get_chapter_state,
    delete_chapter_state as chapter_delete_state,
    upsert_chapter_state,
    search_chapter_states,
)
from ..types.chapter_state import PlayerChapterStateListResponse


async def get_player_chapter_state(request: Request):
    try:
        commander_id = parse_commander_id(request)
    except ValueError:
        return error(code='400', message="invalid id", status_code=400)
    if not admin.commander_exists(commander_id):
        return write_commander_error(NotFoundError())
    state = get_chapter_state(commander_id)
    if state is None:
        return error(code='404', message="chapter state not found", status_code=404)
    try:
        current = _decode_chapter_state(state.state)
    except Exception:
        return error(code='500', message="failed to decode chapter state", status_code=500)
    payload = PlayerChapterStateResponse(
        chapter_id=state.chapter_id,
        updated_at=state.updated_at,
        state=current,
    )
    return success(data=payload)


async def search_player_chapter_states(request: Request):
    try:
        commander_id = parse_commander_id(request)
    except ValueError:
        return error(code='400', message="invalid id", status_code=400)
    if not admin.commander_exists(commander_id):
        return write_commander_error(NotFoundError())
    try:
        meta = parse_pagination(request)
    except ValueError as e:
        return error(code='400', message=str(e), status_code=400)
    chapter_id_param = request.query_params.get("chapter_id", "")
    chapter_id_filter = None
    if chapter_id_param:
        try:
            chapter_id_filter = parse_path_uint32(chapter_id_param, "chapter_id")
        except ValueError:
            return error(code='400', message="invalid chapter_id", status_code=400)
    updated_since = request.query_params.get("updated_since", "")
    updated_since_unix = None
    if updated_since:
        try:
            parsed = datetime.fromisoformat(updated_since)
            updated_since_unix = int(parsed.timestamp())
        except (ValueError, TypeError):
            return error(code='400', message="invalid updated_since", status_code=400)
    try:
        result = search_chapter_states(commander_id, chapter_id_filter, updated_since_unix, meta.offset, meta.limit)
    except Exception:
        return error(code='500', message="failed to load chapter states", status_code=500)
    meta.total = result['total']
    entries = []
    for state in result['states']:
        try:
            decoded = _decode_chapter_state(state.state)
        except Exception:
            return error(code='500', message="failed to decode chapter state", status_code=500)
        entries.append(PlayerChapterStateResponse(
            chapter_id=state.chapter_id,
            updated_at=state.updated_at,
            state=decoded,
        ))
    return success(data=PlayerChapterStateListResponse(states=entries, meta=meta))


async def create_player_chapter_state(request: Request):
    try:
        commander_id = parse_commander_id(request)
    except ValueError:
        return error(code='400', message="invalid id", status_code=400)
    if not admin.commander_exists(commander_id):
        return write_commander_error(NotFoundError())
    try:
        body = await request.json()
    except Exception:
        return error(code='400', message="invalid request", status_code=400)
    req = PlayerChapterStateCreateRequest(**body)
    if req.state.id == 0:
        return error(code='400', message="state id required", status_code=400)
    proto_state = _encode_chapter_state(req.state)
    import json
    state_bytes = json.dumps(proto_state).encode("utf-8")
    import time
    now = int(time.time())
    try:
        upsert_chapter_state(commander_id, req.state.id, state_bytes)
    except Exception:
        return error(code='500', message="failed to store chapter state", status_code=500)
    payload = PlayerChapterStateResponse(
        chapter_id=req.state.id,
        updated_at=now,
        state=req.state,
    )
    return success(data=payload)


async def update_player_chapter_state(request: Request):
    try:
        commander_id = parse_commander_id(request)
    except ValueError:
        return error(code='400', message="invalid id", status_code=400)
    if not admin.commander_exists(commander_id):
        return write_commander_error(NotFoundError())
    try:
        body = await request.json()
    except Exception:
        return error(code='400', message="invalid request", status_code=400)
    req = PlayerChapterStateUpdateRequest(**body)
    if req.state.id == 0:
        return error(code='400', message="state id required", status_code=400)
    proto_state = _encode_chapter_state(req.state)
    import json
    state_bytes = json.dumps(proto_state).encode("utf-8")
    import time
    now = int(time.time())
    try:
        upsert_chapter_state(commander_id, req.state.id, state_bytes)
    except Exception:
        return error(code='500', message="failed to store chapter state", status_code=500)
    payload = PlayerChapterStateResponse(
        chapter_id=req.state.id,
        updated_at=now,
        state=req.state,
    )
    return success(data=payload)


async def delete_player_chapter_state(request: Request):
    try:
        commander_id = parse_commander_id(request)
    except ValueError:
        return error(code='400', message="invalid id", status_code=400)
    if not admin.commander_exists(commander_id):
        return write_commander_error(NotFoundError())
    try:
        chapter_delete_state(commander_id)
    except Exception:
        return error(code='500', message="failed to delete chapter state", status_code=500)
    return success(data=None)


def _decode_chapter_state(raw: bytes):
    import json
    data = json.loads(raw.decode("utf-8"))
    return ChapterState(
        id=data.get("id", 0),
        time=data.get("time", 0),
        cell_list=_build_cells_dto(data.get("cell_list", [])),
        main_group_list=_build_groups_dto(data.get("main_group_list", [])),
        ai_list=_build_cells_dto(data.get("ai_list", [])),
        escort_list=_build_cells_dto(data.get("escort_list", [])),
        round=data.get("round", 0),
        is_submarine_auto_attack=data.get("is_submarine_auto_attack", 0),
        operation_buff=data.get("operation_buff", 0),
        model_act_count=data.get("model_act_count", 0),
        buff_list=data.get("buff_list", []),
        loop_flag=data.get("loop_flag", 0),
        extra_flag_list=data.get("extra_flag_list", []),
        cell_flag_list=_build_cell_flags_dto(data.get("cell_flag_list", [])),
        chapter_hp=data.get("chapter_hp", 0),
        chapter_strategy_list=_build_strategies_dto(data.get("chapter_strategy_list", [])),
        kill_count=data.get("kill_count", 0),
        init_ship_count=data.get("init_ship_count", 0),
        continuous_kill_count=data.get("continuous_kill_count", 0),
        battle_statistics=_build_strategies_dto(data.get("battle_statistics", [])),
        fleet_duties=_build_fleet_duties_dto(data.get("fleet_duties", [])),
        move_step_count=data.get("move_step_count", 0),
        submarine_group_list=_build_groups_dto(data.get("submarine_group_list", [])),
        support_group_list=_build_groups_dto(data.get("support_group_list", [])),
    )


def _encode_chapter_state(state: ChapterState) -> dict:
    return {
        "id": state.id,
        "time": state.time,
        "cell_list": _build_cells_proto(state.cell_list),
        "main_group_list": _build_groups_proto(state.main_group_list),
        "ai_list": _build_cells_proto(state.ai_list),
        "escort_list": _build_cells_proto(state.escort_list),
        "round": state.round,
        "is_submarine_auto_attack": state.is_submarine_auto_attack,
        "operation_buff": state.operation_buff,
        "model_act_count": state.model_act_count,
        "buff_list": state.buff_list,
        "loop_flag": state.loop_flag,
        "extra_flag_list": state.extra_flag_list,
        "cell_flag_list": _build_cell_flags_proto(state.cell_flag_list),
        "chapter_hp": state.chapter_hp,
        "chapter_strategy_list": _build_strategies_proto(state.chapter_strategy_list),
        "kill_count": state.kill_count,
        "init_ship_count": state.init_ship_count,
        "continuous_kill_count": state.continuous_kill_count,
        "battle_statistics": _build_strategies_proto(state.battle_statistics),
        "fleet_duties": _build_fleet_duties_proto(state.fleet_duties),
        "move_step_count": state.move_step_count,
        "submarine_group_list": _build_groups_proto(state.submarine_group_list),
        "support_group_list": _build_groups_proto(state.support_group_list),
    }


def _build_cells_dto(cells):
    result = []
    for cell in cells:
        entry = ChapterCellInfo(
            pos=_build_pos_dto(cell.get("pos")),
            item_type=cell.get("item_type", 0),
            extra_id=cell.get("extra_id", 0),
        )
        if cell.get("item_id") is not None:
            entry.item_id = cell["item_id"]
        if cell.get("item_flag") is not None:
            entry.item_flag = cell["item_flag"]
        if cell.get("item_data") is not None:
            entry.item_data = cell["item_data"]
        result.append(entry)
    return result


def _build_groups_dto(groups):
    result = []
    for g in groups:
        result.append(ChapterGroup(
            id=g.get("id", 0),
            ship_list=_build_ships_dto(g.get("ship_list", [])),
            pos=_build_pos_dto(g.get("pos")),
            step_count=g.get("step_count", 0),
            box_strategy_list=_build_strategies_dto(g.get("box_strategy_list", [])),
            ship_strategy_list=_build_strategies_dto(g.get("ship_strategy_list", [])),
            strategy_ids=g.get("strategy_ids", []),
            bullet=g.get("bullet", 0),
            start_pos=_build_pos_dto(g.get("start_pos")),
            commander_list=_build_commanders_dto(g.get("commander_list", [])),
            move_step_down=g.get("move_step_down", 0),
            kill_count=g.get("kill_count", 0),
            fleet_id=g.get("fleet_id", 0),
            vision_lv=g.get("vision_lv", 0),
        ))
    return result


def _build_ships_dto(ships):
    return [ChapterShip(id=s.get("id", 0), hp_rant=s.get("hp_rant", 0)) for s in ships]


def _build_commanders_dto(commanders):
    return [ChapterCommander(pos=c.get("pos", 0), id=c.get("id", 0)) for c in commanders]


def _build_strategies_dto(strategies):
    return [ChapterStrategy(id=s.get("id", 0), count=s.get("count", 0)) for s in strategies]


def _build_cell_flags_dto(flags):
    return [ChapterCellFlag(pos=_build_pos_dto(f.get("pos")), flag_list=f.get("flag_list", [])) for f in flags]


def _build_fleet_duties_dto(duties):
    return [ChapterFleetDuty(key=d.get("key", 0), value=d.get("value", 0)) for d in duties]


def _build_pos_dto(pos):
    if not pos:
        return ChapterCellPos(row=0, column=0)
    return ChapterCellPos(row=pos.get("row", 0), column=pos.get("column", 0))


def _build_cells_proto(cells):
    return [_build_cell_proto(c) for c in cells]


def _build_cell_proto(cell: ChapterCellInfo) -> dict:
    d = {
        "pos": _build_pos_proto(cell.pos),
        "item_type": cell.item_type,
        "extra_id": cell.extra_id,
    }
    if cell.item_id is not None:
        d["item_id"] = cell.item_id
    if cell.item_flag is not None:
        d["item_flag"] = cell.item_flag
    if cell.item_data is not None:
        d["item_data"] = cell.item_data
    return d


def _build_groups_proto(groups):
    return [_build_group_proto(g) for g in groups]


def _build_group_proto(g: ChapterGroup) -> dict:
    return {
        "id": g.id,
        "ship_list": _build_ships_proto(g.ship_list),
        "pos": _build_pos_proto(g.pos),
        "step_count": g.step_count,
        "box_strategy_list": _build_strategies_proto(g.box_strategy_list),
        "ship_strategy_list": _build_strategies_proto(g.ship_strategy_list),
        "strategy_ids": g.strategy_ids,
        "bullet": g.bullet,
        "start_pos": _build_pos_proto(g.start_pos),
        "commander_list": _build_commanders_proto(g.commander_list),
        "move_step_down": g.move_step_down,
        "kill_count": g.kill_count,
        "fleet_id": g.fleet_id,
        "vision_lv": g.vision_lv,
    }


def _build_ships_proto(ships):
    return [{"id": s.id, "hp_rant": s.hp_rant} for s in ships]


def _build_commanders_proto(commanders):
    return [{"pos": c.pos, "id": c.id} for c in commanders]


def _build_strategies_proto(strategies):
    return [{"id": s.id, "count": s.count} for s in strategies]


def _build_cell_flags_proto(flags):
    return [{"pos": _build_pos_proto(f.pos), "flag_list": f.flag_list} for f in flags]


def _build_fleet_duties_proto(duties):
    return [{"key": d.key, "value": d.value} for d in duties]


def _build_pos_proto(pos: ChapterCellPos) -> dict:
    return {"row": pos.row, "column": pos.column}
