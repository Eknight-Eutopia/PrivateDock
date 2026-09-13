from fastapi import Request

from src.api.response.response import ok as success, error
from src.api.types.love_letter import PlayerLoveLetterStateResponse, PlayerLoveLetterStateUpdateRequest
from src.db.store import NotFoundError
from src.orm import admin
from src.orm import get_or_create_commander_love_letter_state, save_commander_love_letter_state, \
    delete_commander_love_letter_state
from .players import parse_commander_id, write_commander_error


async def player_love_letter_state(request: Request):
    try:
        commander_id = parse_commander_id(request)
    except ValueError:
        return error(code='400', message="invalid id", status_code=400)
    if not admin.commander_exists(commander_id):
        return write_commander_error(NotFoundError())
    try:
        state = get_or_create_commander_love_letter_state(commander_id)
    except Exception:
        return error(code='500', message="failed to load love letter state", status_code=500)
    payload = PlayerLoveLetterStateResponse(
        medals=state.medals,
        manual_letters=state.manual_letters,
        converted_items=state.converted_items,
        rewarded_ids=state.rewarded_ids,
        letter_contents=state.letter_contents,
    )
    return success(data=payload)


async def update_player_love_letter_state(request: Request):
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
    req = PlayerLoveLetterStateUpdateRequest(**body)
    if (req.medals is None and req.manual_letters is None and
            req.converted_items is None and req.rewarded_ids is None and
            req.letter_contents is None):
        return error(code='400', message="no updates provided", status_code=400)
    try:
        state = get_or_create_commander_love_letter_state(commander_id)
    except Exception:
        return error(code='500', message="failed to load love letter state", status_code=500)
    if req.medals is not None:
        state.medals = req.medals
    if req.manual_letters is not None:
        state.manual_letters = req.manual_letters
    if req.converted_items is not None:
        state.converted_items = req.converted_items
    if req.rewarded_ids is not None:
        state.rewarded_ids = req.rewarded_ids
    if req.letter_contents is not None:
        state.letter_contents = req.letter_contents
    try:
        save_commander_love_letter_state(state)
    except Exception:
        return error(code='500', message="failed to update love letter state", status_code=500)
    payload = PlayerLoveLetterStateResponse(
        medals=state.medals,
        manual_letters=state.manual_letters,
        converted_items=state.converted_items,
        rewarded_ids=state.rewarded_ids,
        letter_contents=state.letter_contents,
    )
    return success(data=payload)


async def delete_player_love_letter_state(request: Request):
    try:
        commander_id = parse_commander_id(request)
    except ValueError:
        return error(code='400', message="invalid id", status_code=400)
    if not admin.commander_exists(commander_id):
        return write_commander_error(NotFoundError())
    try:
        delete_commander_love_letter_state(commander_id)
    except Exception:
        return error(code='500', message="failed to delete love letter state", status_code=500)
    return success(data=None)
