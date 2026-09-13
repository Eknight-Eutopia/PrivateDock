from fastapi import Request
from src.api.response.response import ok as success, error
from src.api.types import *
from src.orm.commander import commander_exists
from src.orm.remaster_state import (
    ensure_remaster_state,
    update_remaster_state_dynamic,
)
from src.orm.remaster_progress import (
    list_remaster_progress_rows,
    get_remaster_progress_row,
    upsert_remaster_progress_row,
    update_remaster_progress_row,
    delete_remaster_progress_row,
)
from .players import parse_commander_id, parse_path_uint32, fmt_val as _fmt_val


async def player_remaster_state(request: Request):
    try:
        commander_id = parse_commander_id(request)
    except ValueError:
        return error("bad_request", "invalid id", status_code=400)
    if not await commander_exists(commander_id):
        return error("not_found", "commander not found", status_code=404)
    state = await ensure_remaster_state(commander_id)
    return success(data=PlayerRemasterStateResponse(
        ticket_count=state["ticket_count"],
        daily_count=state["daily_count"],
        last_daily_reset_at=_fmt_val(state["last_daily_reset_at"]),
    ).dict())


async def update_player_remaster_state(request: Request):
    try:
        commander_id = parse_commander_id(request)
    except ValueError:
        return error("bad_request", "invalid id", status_code=400)
    if not await commander_exists(commander_id):
        return error("not_found", "commander not found", status_code=404)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = PlayerRemasterStateUpdateRequest(**body)
    if req.ticket_count is None and req.daily_count is None and req.last_daily_reset_at is None:
        return error("bad_request", "no updates provided", status_code=400)
    fields = {}
    if req.ticket_count is not None:
        fields["ticket_count"] = req.ticket_count
    if req.daily_count is not None:
        fields["daily_count"] = req.daily_count
    if req.last_daily_reset_at is not None:
        fields["last_daily_reset_at"] = req.last_daily_reset_at
    await update_remaster_state_dynamic(commander_id, **fields)
    return success(data=None)


async def player_remaster_progress(request: Request):
    try:
        commander_id = parse_commander_id(request)
    except ValueError:
        return error("bad_request", "invalid id", status_code=400)
    if not await commander_exists(commander_id):
        return error("not_found", "commander not found", status_code=404)
    chapter_id_param = request.query_params.get("chapter_id", "")
    received_param = request.query_params.get("received", "")
    rows = await list_remaster_progress_rows(commander_id)
    entries = []
    for r in rows:
        if chapter_id_param and r["chapter_id"] != int(chapter_id_param):
            continue
        if received_param:
            recv_val = received_param.lower() in ("1", "true", "yes")
            if r["received"] != recv_val:
                continue
        entries.append(PlayerRemasterProgressEntry(
            chapter_id=r["chapter_id"],
            pos=r["pos"],
            count=r["count"],
            received=r["received"],
            updated_at=_fmt_val(r["updated_at"]),
        ))
    return success(data=PlayerRemasterProgressResponse(progress=entries).dict())


async def upsert_player_remaster_progress(request: Request):
    try:
        commander_id = parse_commander_id(request)
    except ValueError:
        return error("bad_request", "invalid id", status_code=400)
    if not await commander_exists(commander_id):
        return error("not_found", "commander not found", status_code=404)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = PlayerRemasterProgressCreateRequest(**body)
    received = req.received if req.received is not None else False
    if req.received is None:
        existing = await get_remaster_progress_row(commander_id, req.chapter_id, req.pos)
        if existing:
            received = existing["received"]
    await upsert_remaster_progress_row(commander_id, req.chapter_id, req.pos, req.count, received)
    return success(data=None)


async def update_player_remaster_progress(request: Request):
    try:
        commander_id = parse_commander_id(request)
    except ValueError:
        return error("bad_request", "invalid id", status_code=400)
    if not await commander_exists(commander_id):
        return error("not_found", "commander not found", status_code=404)
    try:
        chapter_id = parse_path_uint32(request.path_params.get("chapter_id", ""), "chapter_id")
        pos = parse_path_uint32(request.path_params.get("pos", ""), "pos")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = PlayerRemasterProgressUpdateRequest(**body)
    if req.count is None and req.received is None:
        return error("bad_request", "no updates provided", status_code=400)
    existing = await get_remaster_progress_row(commander_id, chapter_id, pos)
    if existing is None:
        return error("not_found", "remaster progress not found", status_code=404)
    new_count = req.count if req.count is not None else existing["count"]
    new_received = req.received if req.received is not None else existing["received"]
    await update_remaster_progress_row(commander_id, chapter_id, pos, new_count, new_received)
    return success(data=None)


async def delete_player_remaster_progress(request: Request):
    try:
        commander_id = parse_commander_id(request)
    except ValueError:
        return error("bad_request", "invalid id", status_code=400)
    try:
        chapter_id = parse_path_uint32(request.path_params.get("chapter_id", ""), "chapter_id")
        pos = parse_path_uint32(request.path_params.get("pos", ""), "pos")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    await delete_remaster_progress_row(commander_id, chapter_id, pos)
    return success(data=None)

