from datetime import datetime
from fastapi import Request
from src.api.response.response import ok as success, error
from src.api.types import *

from src.db.store import NotFoundError
from .players import parse_commander_id, parse_path_uint32, parse_pagination, write_commander_error
from src.orm import admin
from src.orm.chapter import (
    get_chapter_progress,
    list_chapter_progress_page,
    search_chapter_progress,
    upsert_chapter_progress,
    delete_chapter_progress,
)
from src.orm.chapter_progress import ChapterProgress as SAChapterProgress
from ..types.chapter_progress import PlayerChapterProgressListResponse


async def get_player_chapter_progress(request: Request):
    try:
        commander_id = parse_commander_id(request)
    except ValueError:
        return error(code='400', message="invalid id", status_code=400)
    chapter_id = _parse_chapter_id(request)
    if chapter_id is None:
        return error(code='400', message="invalid chapter_id", status_code=400)
    if not admin.commander_exists(commander_id):
        return write_commander_error(NotFoundError())
    progress = get_chapter_progress(commander_id, chapter_id)
    if progress is None:
        return error(code='404', message="chapter progress not found", status_code=404)
    payload = PlayerChapterProgressResponse(progress=_build_progress_dto(progress))
    return success(data=payload)


async def list_player_chapter_progress(request: Request):
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
    try:
        result = list_chapter_progress_page(commander_id, meta.offset, meta.limit)
    except Exception:
        return error(code='500', message="failed to load chapter progress", status_code=500)
    meta.total = result['total']
    entries = [PlayerChapterProgressResponse(progress=_build_progress_dto(p)) for p in result['progress']]
    return success(data=PlayerChapterProgressListResponse(progress=entries, meta=meta))


async def search_player_chapter_progress(request: Request):
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
        result = search_chapter_progress(commander_id, chapter_id_filter, updated_since_unix, meta.offset, meta.limit)
    except Exception:
        return error(code='500', message="failed to load chapter progress", status_code=500)
    meta.total = result['total']
    entries = [PlayerChapterProgressResponse(progress=_build_progress_dto(p)) for p in result['progress']]
    return success(data=PlayerChapterProgressListResponse(progress=entries, meta=meta))


async def create_player_chapter_progress(request: Request):
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
    req = PlayerChapterProgressCreateRequest(**body)
    if req.chapter_id == 0:
        return error(code='400', message="chapter_id required", status_code=400)
    progress = _build_progress_model(commander_id, req.progress)
    try:
        upsert_chapter_progress(progress)
    except Exception:
        return error(code='500', message="failed to store chapter progress", status_code=500)
    payload = PlayerChapterProgressResponse(progress=req.progress)
    return success(data=payload)


async def update_player_chapter_progress(request: Request):
    try:
        commander_id = parse_commander_id(request)
    except ValueError:
        return error(code='400', message="invalid id", status_code=400)
    chapter_id = _parse_chapter_id(request)
    if chapter_id is None:
        return error(code='400', message="invalid chapter_id", status_code=400)
    if not admin.commander_exists(commander_id):
        return write_commander_error(NotFoundError())
    try:
        body = await request.json()
    except Exception:
        return error(code='400', message="invalid request", status_code=400)
    req = PlayerChapterProgressUpdateRequest(**body)
    if req.progress.chapter_id == 0:
        req.progress.chapter_id = chapter_id
    progress = _build_progress_model(commander_id, req.progress)
    try:
        upsert_chapter_progress(progress)
    except Exception:
        return error(code='500', message="failed to update chapter progress", status_code=500)
    payload = PlayerChapterProgressResponse(progress=req.progress)
    return success(data=payload)


async def delete_player_chapter_progress(request: Request):
    try:
        commander_id = parse_commander_id(request)
    except ValueError:
        return error(code='400', message="invalid id", status_code=400)
    chapter_id = _parse_chapter_id(request)
    if chapter_id is None:
        return error(code='400', message="invalid chapter_id", status_code=400)
    if not admin.commander_exists(commander_id):
        return write_commander_error(NotFoundError())
    try:
        delete_chapter_progress(commander_id, chapter_id)
    except Exception:
        return error(code='500', message="failed to delete chapter progress", status_code=500)
    return success(data=None)


def _parse_chapter_id(request: Request):
    try:
        return parse_path_uint32(request.path_params.get("chapter_id", ""), "chapter_id")
    except ValueError:
        return None


def _build_progress_dto(progress) -> ChapterProgress:
    return ChapterProgress(
        chapter_id=progress.chapter_id,
        progress=progress.progress,
        kill_boss_count=progress.kill_boss_count,
        kill_enemy_count=progress.kill_enemy_count,
        take_box_count=progress.take_box_count,
        defeat_count=progress.defeat_count,
        today_defeat_count=progress.today_defeat_count,
        pass_count=progress.pass_count,
        updated_at=progress.updated_at,
    )


def _build_progress_model(commander_id: int, p: ChapterProgress):
    return SAChapterProgress(
        commander_id=commander_id,
        chapter_id=p.chapter_id,
        progress=p.progress,
        kill_boss_count=p.kill_boss_count,
        kill_enemy_count=p.kill_enemy_count,
        take_box_count=p.take_box_count,
        defeat_count=p.defeat_count,
        today_defeat_count=p.today_defeat_count,
        pass_count=p.pass_count,
    )
