from fastapi import APIRouter, Query, Request

from fastapi import Request as FastAPIRequest
from src.api.response.response import ok as success
from fastapi import Request as FastAPIRequest
from src.api.response.response import ok as success
from src.api.handlers.players import (
    list_players as players_list,
    search_players,
    player_detail,
    create_player,
    update_player,
    delete_player,
    player_resources,
    player_resource,
    delete_player_resource,
    update_resources_bulk,
    player_ships,
    player_ship,
    create_player_ship,
    update_player_ship,
    delete_player_ship,
    player_secretaries,
    replace_player_secretaries,
    delete_player_secretaries,
    player_items,
    player_item,
    update_player_item_quantity,
    delete_player_item,
    player_equipment,
    player_equipment_entry,
    upsert_player_equipment,
    delete_player_equipment,
    player_ship_equipment,
    update_player_ship_equipment,
    player_misc_items,
    player_misc_item,
    update_player_misc_item,
    delete_player_misc_item,
    player_fleets,
    player_fleet,
    create_player_fleet,
    update_player_fleet,
    delete_player_fleet,
    player_skins,
    player_skin,
    update_player_skin,
    delete_player_skin,
    player_buffs,
    player_buff,
    add_player_buff,
    update_player_buff,
    delete_player_buff,
    player_flags,
    add_player_flag,
    delete_player_flag,
    player_likes,
    add_player_like,
    delete_player_like,
)
from src.api.handlers.love_letter import (
    player_love_letter_state,
    update_player_love_letter_state,
    delete_player_love_letter_state,
)
from src.api.handlers.chapter_state import (
    get_player_chapter_state,
    search_player_chapter_states,
    create_player_chapter_state,
    update_player_chapter_state,
    delete_player_chapter_state,
)
from src.api.handlers.chapter_progress import (
    get_player_chapter_progress,
    list_player_chapter_progress,
    search_player_chapter_progress,
    create_player_chapter_progress,
    update_player_chapter_progress,
    delete_player_chapter_progress,
)

router = APIRouter(prefix="/api/v1/players", tags=["players"])


@router.get("")
async def list_players(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    scope = {
        "type": "http",
        "query_string": f"offset={offset}&limit={limit}".encode(),
        "headers": [],
        "method": "GET",
        "path": "",
        "scheme": "http",
        "server": ("localhost", 80),
    }
    req = FastAPIRequest(scope, receive=lambda: None)
    return await players_list(req)


@router.get("/search")
async def search_players_route(
    q: str = Query(""),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    scope = {
        "type": "http",
        "query_string": f"q={q}&offset={offset}&limit={limit}".encode(),
        "headers": [],
        "method": "GET",
        "path": "",
        "scheme": "http",
        "server": ("localhost", 80),
    }
    req = FastAPIRequest(scope, receive=lambda: None)
    return await search_players(req)


@router.get("/{player_id}")
async def get_player(player_id: int):
    from fastapi import Request as FastAPIRequest
    scope = {
        "type": "http",
        "query_string": b"",
        "headers": [],
        "path_params": {"player_id": str(player_id)},
        "method": "GET",
        "path": "",
        "scheme": "http",
        "server": ("localhost", 80),
    }
    req = FastAPIRequest(scope, receive=lambda: None)
    from src.api.response.response import ok as success
    return await player_detail(req)


@router.post("")
async def create_player_route(req: Request):
    return await create_player(req)


@router.patch("/{player_id}")
async def update_player_route(req: Request):
    return await update_player(req)


@router.delete("/{player_id}")
async def delete_player_route(req: Request):
    return await delete_player(req)


@router.get("/{player_id}/resources")
async def get_player_resources(req: Request):
    return await player_resources(req)


@router.get("/{player_id}/resources/{resource_id}")
async def get_player_resource(req: Request):
    return await player_resource(req)


@router.delete("/{player_id}/resources/{resource_id}")
async def delete_player_resource_route(req: Request):
    return await delete_player_resource(req)


@router.put("/{player_id}/resources")
async def update_resources_bulk_route(req: Request):
    return await update_resources_bulk(req)


@router.get("/{player_id}/ships")
async def get_player_ships_route(req: Request):
    return await player_ships(req)


@router.get("/{player_id}/ships/{owned_id}")
async def get_player_ship_route(req: Request):
    return await player_ship(req)


@router.post("/{player_id}/ships")
async def create_player_ship_route(req: Request):
    return await create_player_ship(req)


@router.patch("/{player_id}/ships/{owned_id}")
async def update_player_ship_route(req: Request):
    return await update_player_ship(req)


@router.delete("/{player_id}/ships/{owned_id}")
async def delete_player_ship_route(req: Request):
    return await delete_player_ship(req)


@router.get("/{player_id}/secretaries")
async def get_secretaries_route(req: Request):
    return await player_secretaries(req)


@router.put("/{player_id}/secretaries")
async def replace_secretaries_route(req: Request):
    return await replace_player_secretaries(req)


@router.delete("/{player_id}/secretaries")
async def delete_secretaries_route(req: Request):
    return await delete_player_secretaries(req)


@router.get("/{player_id}/items")
async def get_player_items_route(req: Request):
    return await player_items(req)


@router.get("/{player_id}/items/{item_id}")
async def get_player_item_route(req: Request):
    return await player_item(req)


@router.put("/{player_id}/items/{item_id}")
async def upsert_player_item_route(req: Request):
    return await update_player_item_quantity(req)


@router.get("/{player_id}/equipment")
async def get_player_equipment_route(req: Request):
    return await player_equipment(req)


@router.get("/{player_id}/equipment/{equipment_id}")
async def get_player_equipment_entry_route(req: Request):
    return await player_equipment_entry(req)


@router.put("/{player_id}/equipment")
async def upsert_player_equipment_route(req: Request):
    return await upsert_player_equipment(req)


@router.delete("/{player_id}/equipment/{equipment_id}")
async def delete_player_equipment_route(req: Request):
    return await delete_player_equipment(req)


@router.get("/{player_id}/ships/{owned_id}/equipment")
async def get_player_ship_equipment_route(req: Request):
    return await player_ship_equipment(req)


@router.put("/{player_id}/ships/{owned_id}/equipment")
async def update_player_ship_equipment_route(req: Request):
    return await update_player_ship_equipment(req)


@router.get("/{player_id}/misc-items")
async def get_player_misc_items_route(req: Request):
    return await player_misc_items(req)


@router.get("/{player_id}/misc-items/{item_id}")
async def get_player_misc_item_route(req: Request):
    return await player_misc_item(req)


@router.put("/{player_id}/misc-items/{item_id}")
async def update_player_misc_item_route(req: Request):
    return await update_player_misc_item(req)


@router.delete("/{player_id}/misc-items/{item_id}")
async def delete_player_misc_item_route(req: Request):
    return await delete_player_misc_item(req)


@router.get("/{player_id}/love-letter")
async def get_love_letter_state_route(req: Request):
    return await player_love_letter_state(req)


@router.put("/{player_id}/love-letter")
async def update_love_letter_state_route(req: Request):
    return await update_player_love_letter_state(req)


@router.delete("/{player_id}/love-letter")
async def delete_love_letter_state_route(req: Request):
    return await delete_player_love_letter_state(req)


# ── Chapter State ──────────────────────────────────────────────────────────


@router.get("/{player_id}/chapter-state")
async def get_chapter_state_route(req: Request):
    return await get_player_chapter_state(req)


@router.get("/{player_id}/chapter-state/search")
async def search_chapter_states_route(req: Request):
    return await search_player_chapter_states(req)


@router.post("/{player_id}/chapter-state")
async def create_chapter_state_route(req: Request):
    return await create_player_chapter_state(req)


@router.patch("/{player_id}/chapter-state")
async def update_chapter_state_route(req: Request):
    return await update_player_chapter_state(req)


@router.delete("/{player_id}/chapter-state")
async def delete_chapter_state_route(req: Request):
    return await delete_player_chapter_state(req)


# ── Chapter Progress ───────────────────────────────────────────────────────


@router.get("/{player_id}/chapter-progress")
async def list_chapter_progress_route(req: Request):
    return await list_player_chapter_progress(req)


@router.get("/{player_id}/chapter-progress/search")
async def search_chapter_progress_route(req: Request):
    return await search_player_chapter_progress(req)


@router.get("/{player_id}/chapter-progress/{chapter_id}")
async def get_chapter_progress_route(req: Request):
    return await get_player_chapter_progress(req)


@router.post("/{player_id}/chapter-progress")
async def create_chapter_progress_route(req: Request):
    return await create_player_chapter_progress(req)


@router.patch("/{player_id}/chapter-progress/{chapter_id}")
async def update_chapter_progress_route(req: Request):
    return await update_player_chapter_progress(req)


@router.delete("/{player_id}/chapter-progress/{chapter_id}")
async def delete_chapter_progress_route(req: Request):
    return await delete_player_chapter_progress(req)


@router.get("/{player_id}/fleets")
async def get_player_fleets_route(req: Request):
    return await player_fleets(req)


@router.get("/{player_id}/fleets/{fleet_id}")
async def get_player_fleet_route(req: Request):
    return await player_fleet(req)


@router.post("/{player_id}/fleets")
async def create_player_fleet_route(req: Request):
    return await create_player_fleet(req)


@router.patch("/{player_id}/fleets/{fleet_id}")
async def update_player_fleet_route(req: Request):
    return await update_player_fleet(req)


@router.delete("/{player_id}/fleets/{fleet_id}")
async def delete_player_fleet_route(req: Request):
    return await delete_player_fleet(req)


@router.get("/{player_id}/skins")
async def get_player_skins_route(req: Request):
    return await player_skins(req)


@router.get("/{player_id}/skins/{skin_id}")
async def get_player_skin_route(req: Request):
    return await player_skin(req)


@router.put("/{player_id}/skins/{skin_id}")
async def update_player_skin_route(req: Request):
    return await update_player_skin(req)


@router.delete("/{player_id}/skins/{skin_id}")
async def delete_player_skin_route(req: Request):
    return await delete_player_skin(req)


@router.get("/{player_id}/buffs")
async def get_player_buffs_route(req: Request):
    return await player_buffs(req)


@router.get("/{player_id}/buffs/{buff_id}")
async def get_player_buff_route(req: Request):
    return await player_buff(req)


@router.post("/{player_id}/buffs")
async def add_player_buff_route(req: Request):
    return await add_player_buff(req)


@router.patch("/{player_id}/buffs/{buff_id}")
async def update_player_buff_route(req: Request):
    return await update_player_buff(req)


@router.delete("/{player_id}/buffs/{buff_id}")
async def delete_player_buff_route(req: Request):
    return await delete_player_buff(req)


@router.get("/{player_id}/flags")
async def get_player_flags_route(req: Request):
    return await player_flags(req)


@router.post("/{player_id}/flags")
async def add_player_flag_route(req: Request):
    return await add_player_flag(req)


@router.delete("/{player_id}/flags/{flag_id}")
async def delete_player_flag_route(req: Request):
    return await delete_player_flag(req)


@router.get("/{player_id}/likes")
async def get_player_likes_route(req: Request):
    return await player_likes(req)


@router.post("/{player_id}/likes")
async def add_player_like_route(req: Request):
    return await add_player_like(req)


@router.delete("/{player_id}/likes/{group_id}")
async def delete_player_like_route(req: Request):
    return await delete_player_like(req)


@router.get("/{player_id}/guide")
async def get_player_guide_route(req: Request):
    from src.api.handlers.players import guide_list
    return await guide_list(req)


@router.patch("/{player_id}/guide")
async def update_player_guide_route(req: Request):
    from src.api.handlers.players import update_guide
    return await update_guide(req)


@router.get("/{player_id}/stories")
async def get_player_stories_route(req: Request):
    from src.api.handlers.players import list_stories
    return await list_stories(req)


@router.post("/{player_id}/stories")
async def add_player_story_route(req: Request):
    from src.api.handlers.players import add_story
    return await add_story(req)


@router.get("/{player_id}/attire")
async def get_player_attire_route(req: Request):
    from src.api.handlers.players import list_attire
    return await list_attire(req)


@router.post("/{player_id}/attire")
async def create_player_attire_route(req: Request):
    from src.api.handlers.players import create_attire
    return await create_attire(req)


@router.patch("/{player_id}/attire/{attire_type}/{attire_id}")
async def update_player_attire_route(req: Request):
    from src.api.handlers.players import update_attire
    return await update_attire(req)


@router.delete("/{player_id}/attire/{attire_type}/{attire_id}")
async def delete_player_attire_route(req: Request):
    from src.api.handlers.players import delete_attire
    return await delete_attire(req)


@router.put("/{player_id}/attire/selection")
async def update_attire_selection_route(req: Request):
    from src.api.handlers.players import update_attire_selection
    return await update_attire_selection(req)


@router.get("/{player_id}/attire/selection")
async def get_attire_selection_route(req: Request):
    from src.api.handlers.players import get_attire_selection
    return await get_attire_selection(req)


@router.get("/{player_id}/random-flag-ship")
async def get_random_flag_ship_route(req: Request):
    from src.api.handlers.players import get_random_flag_ship
    return await get_random_flag_ship(req)


@router.put("/{player_id}/random-flag-ship")
async def update_random_flag_ship_route(req: Request):
    from src.api.handlers.players import update_random_flag_ship
    return await update_random_flag_ship(req)


@router.get("/{player_id}/random-flag-ship/entries")
async def list_random_flag_ship_entries_route(req: Request):
    from src.api.handlers.players import list_random_flag_ship_entries
    return await list_random_flag_ship_entries(req)


@router.post("/{player_id}/random-flag-ship/entries")
async def upsert_random_flag_ship_entry_route(req: Request):
    from src.api.handlers.players import upsert_random_flag_ship_entry
    return await upsert_random_flag_ship_entry(req)


@router.delete("/{player_id}/random-flag-ship/entries/{ship_id}")
async def delete_random_flag_ship_entry_route(req: Request):
    from src.api.handlers.players import delete_random_flag_ship_entry
    return await delete_random_flag_ship_entry(req)


@router.get("/{player_id}/living-area-cover")
async def get_living_area_cover_route(req: Request):
    from src.api.handlers.players import get_living_area_cover
    return await get_living_area_cover(req)


@router.put("/{player_id}/living-area-cover")
async def update_living_area_cover_route(req: Request):
    from src.api.handlers.players import update_living_area_cover
    return await update_living_area_cover(req)


@router.post("/{player_id}/living-area-cover")
async def add_living_area_cover_route(req: Request):
    from src.api.handlers.players import add_living_area_cover
    return await add_living_area_cover(req)


@router.patch("/{player_id}/living-area-cover/{cover_id}")
async def patch_living_area_cover_route(req: Request):
    from src.api.handlers.players import patch_living_area_cover
    return await patch_living_area_cover(req)


@router.delete("/{player_id}/living-area-cover/{cover_id}")
async def delete_living_area_cover_route(req: Request):
    from src.api.handlers.players import delete_living_area_cover
    return await delete_living_area_cover(req)


@router.get("/{player_id}/mails")
async def get_player_mails_route(req: Request):
    from src.api.handlers.players import list_mails
    return await list_mails(req)


@router.patch("/{player_id}/mails/{mail_id}")
async def update_player_mail_route(req: Request):
    from src.api.handlers.players import update_mail
    return await update_mail(req)


@router.post("/{player_id}/mails")
async def send_player_mail_route(req: Request):
    from src.api.handlers.players import send_mail
    return await send_mail(req)


@router.get("/{player_id}/compensations")
async def get_player_compensations_route(req: Request):
    from src.api.handlers.players import list_compensations
    return await list_compensations(req)


@router.post("/{player_id}/compensations")
async def create_player_compensation_route(req: Request):
    from src.api.handlers.players import create_compensation
    return await create_compensation(req)


@router.get("/{player_id}/builds")
async def get_player_builds_route(req: Request):
    from src.api.handlers.players import list_builds
    return await list_builds(req)


@router.post("/{player_id}/builds")
async def create_player_build_route(req: Request):
    from src.api.handlers.players import create_build
    return await create_build(req)


@router.patch("/{player_id}/builds/{build_id}")
async def update_player_build_route(req: Request):
    from src.api.handlers.players import update_build
    return await update_build(req)


@router.delete("/{player_id}/builds/{build_id}")
async def delete_player_build_route(req: Request):
    from src.api.handlers.players import delete_build
    return await delete_build(req)


@router.get("/{player_id}/build-queue")
async def get_player_build_queue_route(req: Request):
    from src.api.handlers.players import get_build_queue
    return await get_build_queue(req)


@router.put("/{player_id}/build-counters")
async def update_player_build_counters_route(req: Request):
    from src.api.handlers.players import update_build_counters
    return await update_build_counters(req)


@router.get("/{player_id}/punishments")
async def get_player_punishments_route(req: Request):
    from src.api.handlers.players import list_punishments
    return await list_punishments(req)


@router.post("/{player_id}/ban")
async def ban_player_route(req: Request):
    from src.api.handlers.players import ban_player
    return await ban_player(req)


@router.patch("/{player_id}/punishments/{punishment_id}")
async def update_player_punishment_route(req: Request):
    from src.api.handlers.players import update_punishment
    return await update_punishment(req)


@router.post("/{player_id}/kick")
async def kick_player_route(req: Request):
    from src.api.handlers.players import kick_player
    return await kick_player(req)


@router.post("/{player_id}/support-requisition")
async def support_requisition_route(req: Request):
    from src.api.handlers.players import support_requisition
    return await support_requisition(req)


@router.get("/{player_id}/support-requisition")
async def get_support_requisition_route(req: Request):
    from src.api.handlers.players import get_support_requisition
    return await get_support_requisition(req)
