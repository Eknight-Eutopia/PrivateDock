from fastapi import Request
from src.api.response.response import ok as success, error
from src.api.types import *
from src.orm.commander_tb import (
    get_commander_tb_row,
    exists_commander_tb,
    insert_commander_tb,
    update_commander_tb,
    delete_commander_tb_row,
)
from .players import load_commander_detail


async def player_tb(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    row = await get_commander_tb_row(commander["commander_id"])
    if row is None:
        return error("not_found", "tb state not found", status_code=404)
    return success(data=CommanderTBPayload(
        commander_id=commander["commander_id"],
        tb=row["state"],
        permanent=row["permanent"],
    ).dict())


async def create_player_tb(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request payload", status_code=400)
    payload = CommanderTBRequest(**body)
    if not payload.tb or not payload.permanent:
        return error("bad_request", "tb and permanent payloads are required", status_code=400)
    if await exists_commander_tb(commander["commander_id"]):
        return error("conflict", "tb state already exists", status_code=409)
    await insert_commander_tb(commander["commander_id"], payload.tb, payload.permanent)
    return success(data=CommanderTBPayload(
        commander_id=commander["commander_id"],
        tb=payload.tb,
        permanent=payload.permanent,
    ).dict())


async def update_player_tb(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request payload", status_code=400)
    payload = CommanderTBRequest(**body)
    if not payload.tb or not payload.permanent:
        return error("bad_request", "tb and permanent payloads are required", status_code=400)
    if not await exists_commander_tb(commander["commander_id"]):
        return error("not_found", "tb state not found", status_code=404)
    await update_commander_tb(commander["commander_id"], payload.tb, payload.permanent)
    return success(data=CommanderTBPayload(
        commander_id=commander["commander_id"],
        tb=payload.tb,
        permanent=payload.permanent,
    ).dict())


async def delete_player_tb(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    deleted = await delete_commander_tb_row(commander["commander_id"])
    if not deleted:
        return error("not_found", "tb state not found", status_code=404)
    return success(data=None)
