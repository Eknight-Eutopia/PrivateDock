from fastapi import Request

from src.api.response.response import ok as success, error
from src.api.types import *
from src.db.store import NotFoundError
from src.orm.build import (
    list_builds_for_builder,
    list_build_queue,
    get_build_by_id,
    create_build as orm_create_build,
    update_build_dynamic,
    delete_build_by_id,
)
from src.orm.commander import (
    commander_exists,
    get_commander,
    commander_name_exists,
    insert_commander,
    update_commanders_dynamic,
    delete_commander_by_id,
    count_commanders,
    list_commanders,
    count_search_commanders,
    search_commanders,
)
from src.orm.commander_attire import (
    list_commander_attires_rows,
    get_commander_attire,
    upsert_commander_attire,
    update_attire_expires,
    update_attire_is_new,
    delete_commander_attire,
)
from src.orm.commander_buff import (
    list_commander_buffs_row,
    get_commander_buff,
    insert_commander_buff,
    update_commander_buff_dynamic,
    delete_commander_buff,
)
from src.orm.commander_flag import (
    list_commander_flags,
    upsert_commander_flag,
    delete_commander_flag,
)
from src.orm.commander_like import (
    list_commander_likes,
    upsert_commander_like,
    delete_commander_like,
)
from src.orm.commander_living_area_cover import (
    list_commander_living_area_covers_rows,
    insert_living_area_cover,
    update_living_area_cover_is_new,
    update_commander_living_area_cover,
    has_living_area_cover,
    delete_living_area_cover_row,
)
from src.orm.commander_misc_item import (
    list_commander_misc_items,
    get_commander_misc_item,
    get_commander_misc_item_data,
    upsert_commander_misc_item,
    delete_commander_misc_item, list_commander_misc_items_with_name,
)
from src.orm.commander_story import (
    list_commander_stories_rows,
    upsert_commander_story,
)
from src.orm.compensation import (
    list_compensations as orm_list_compensations,
    list_compensation_attachments,
    create_compensation as orm_create_compensation,
    create_compensation_attachment,
)
from src.orm.equipment import list_ship_equipment, replace_ship_equipment
from src.orm.fleet import (
    list_fleets,
    list_fleet_ships,
    get_fleet,
    create_fleet_row,
    add_fleet_ship,
    update_fleet_name,
    clear_fleet_ships,
    delete_fleet,
)
from src.orm.item import (
    list_all_items,
    list_commander_items,
    get_commander_item,
    get_item_name,
    upsert_commander_item,
    delete_commander_item,
)
from src.orm.mail import (
    list_mails_for_commander,
    get_mail,
    update_mail_dynamic,
    create_mail,
    create_mail_attachment,
)
from src.orm.owned_equipment import (
    list_owned_equipment,
    get_owned_equipment,
    upsert_owned_equipment,
    delete_owned_equipment,
)
from src.orm.owned_ship import (
    list_owned_ships_by_owner,
    get_owned_ship,
    create_owned_ship,
    update_owned_ship_dynamic,
    delete_owned_ship,
    list_secretaries,
    clear_secretaries,
    set_secretary,
)
from src.orm.owned_skin import (
    list_owned_skins,
    get_owned_skin,
    update_owned_skin_expires,
    delete_owned_skin,
)
from src.orm.punishment import (
    get_punishment_for_commander,
    list_punishments_for_commander,
    insert_punishment,
    get_punishment_by_id,
    update_punishment_permanent,
    clear_punishment_lift,
    update_punishment_lift,
)
from src.orm.random_flag_ship import (
    list_random_flag_ship_rows,
    upsert_random_flag_ship,
    delete_random_flag_ship,
)
from src.orm.resource import (
    list_all_resource_types,
    list_owned_resources_by_commander,
    get_owned_resource,
    get_resource_name,
    delete_owned_resource,
    upsert_owned_resource,
)
from src.orm.ship_name import get_ship_name
from ..types.player import PlayerShipResponse, PlayerShipEntry, PlayerOwnedShipEntry


# ---- Shared utility functions (migrated from _shared.py) ----


def parse_commander_id(request: Request) -> int:
    raw = request.path_params.get("id")
    if raw is None:
        raise ValueError("invalid id")
    try:
        val = int(raw)
    except (ValueError, TypeError):
        raise ValueError("invalid id")
    if val <= 0:
        raise ValueError("invalid id")
    return val


def parse_path_uint32(value: str, name: str) -> int:
    if not value:
        raise ValueError(f"invalid {name}")
    try:
        val = int(value)
    except (ValueError, TypeError):
        raise ValueError(f"invalid {name}")
    if val <= 0:
        raise ValueError(f"invalid {name}")
    return val


def parse_path_uint64(value: str, name: str) -> int:
    if not value:
        raise ValueError(f"invalid {name}")
    try:
        val = int(value)
    except (ValueError, TypeError):
        raise ValueError(f"invalid {name}")
    if val <= 0:
        raise ValueError(f"invalid {name}")
    return val


def parse_optional_uint32(value: str | None, name: str):
    if not value or not value.strip():
        return None
    try:
        val = int(value)
    except (ValueError, TypeError):
        raise ValueError(f"invalid {name}")
    if val <= 0:
        raise ValueError(f"invalid {name}")
    return val


def parse_pagination(request: Request):
    try:
        offset_s = request.query_params.get("offset", "0")
        offset = int(offset_s) if offset_s else 0
    except (ValueError, TypeError):
        raise ValueError("invalid offset")
    try:
        limit_s = request.query_params.get("limit", "50")
        limit = int(limit_s) if limit_s else 50
    except (ValueError, TypeError):
        raise ValueError("invalid limit")
    if limit <= 0:
        limit = 50
    if limit > 200:
        limit = 200
    return PaginationMeta(offset=offset, limit=limit, total=0)


async def load_commander_detail(request: Request):
    try:
        commander_id = parse_commander_id(request)
    except ValueError:
        return None, error("bad_request", "invalid id", status_code=400)
    row = await get_commander(commander_id)
    if row is None:
        return None, error("not_found", "commander not found", status_code=404)
    return row, None


def write_commander_error(err=None):
    if isinstance(err, NotFoundError):
        return error(code="not_found", message="commander not found", status_code=404)
    return error(code="internal_error", message="internal error", status_code=500)


async def list_players(request: Request):
    try:
        pagination = parse_pagination(request)
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    sort = request.query_params.get("sort", "")
    min_level_s = request.query_params.get("min_level", "0")
    try:
        min_level = int(min_level_s) if min_level_s else 0
    except ValueError:
        min_level = 0
    where_parts = []
    params = {}
    if min_level > 0:
        where_parts.append("c.level >= :min_lvl")
        params["min_lvl"] = min_level
    where_clause = "WHERE " + " AND ".join(where_parts) if where_parts else ""
    order_clause = "ORDER BY c.commander_id"
    if sort == "last_login":
        order_clause = "ORDER BY c.last_login DESC NULLS LAST"
    total = await count_commanders(where_clause, params)
    rows = await list_commanders(
        "c.commander_id, c.name, c.level, c.account_id, c.last_login",
        where_clause, order_clause, params, pagination.offset, pagination.limit,
    )
    players = [PlayerListItem(
        commander_id=r["commander_id"], name=r.get("name", "") or "",
        level=r.get("level", 0), account_id=r.get("account_id", 0),
        online=False, banned=False,
        last_login=_fmt_val(r.get("last_login")),
    ) for r in rows]
    return success(data=ListPlayersResponse(players=players, meta=PaginationMeta(offset=pagination.offset, limit=pagination.limit, total=total)).dict())


async def search_players(request: Request):
    try:
        pagination = parse_pagination(request)
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    q = request.query_params.get("q", "").strip()
    if not q:
        return error("bad_request", "search query is required", status_code=400)
    pattern = f"%{q}%"
    total = await count_search_commanders(pattern)
    rows = await search_commanders(pattern, pagination.offset, pagination.limit)
    players = [PlayerListItem(
        commander_id=r["commander_id"], name=r.get("name", "") or "",
        level=r.get("level", 0), account_id=r.get("account_id", 0),
    ) for r in rows]
    return success(data=ListPlayersResponse(players=players, meta=PaginationMeta(offset=pagination.offset, limit=pagination.limit, total=total)).dict())


async def player_detail(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    ban = await get_punishment_for_commander(commander["commander_id"])
    return success(data=PlayerDetailResponse(
        commander_id=commander["commander_id"],
        account_id=commander.get("account_id", 0),
        name=commander.get("name", ""),
        level=commander.get("level", 0),
        exp=commander.get("exp", 0),
        last_login=_fmt_val(commander.get("last_login")),
        banned=ban is not None,
        online=False,
    ).dict())


async def create_player(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = PlayerCreateRequest(**body)
    name = req.name.strip()
    if not name:
        return error("bad_request", "name is required", status_code=400)
    if await commander_exists(req.commander_id):
        return error("conflict", "commander already exists", status_code=409)
    if await commander_name_exists(name):
        return error("conflict", "name already exists", status_code=409)
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    await insert_commander(
        req.commander_id, req.account_id or 0, name, req.level or 1, req.exp or 0,
        last_login=now, guide_index=req.guide_index or 0, new_guide_index=req.new_guide_index or 0,
        name_change_cooldown=datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc),
        room_id=req.room_id or 0, exchange_count=req.exchange_count or 0,
        draw_count1=req.draw_count1 or 0, draw_count10=req.draw_count10 or 0,
        support_requisition_count=req.support_requisition_count or 0,
        support_requisition_month=req.support_requisition_month or 0, collect_attack_count=0,
        acc_pay_lv=req.acc_pay_lv or 0, living_area_cover_id=req.living_area_cover_id or 0,
        selected_icon_frame_id=req.selected_icon_frame_id or 0,
        selected_chat_frame_id=req.selected_chat_frame_id or 0,
        selected_battle_ui_id=req.selected_battle_ui_id or 0,
        display_icon_id=req.display_icon_id or 0, display_skin_id=req.display_skin_id or 0,
        display_icon_theme_id=req.display_icon_theme_id or 0,
        manifesto=req.manifesto or "", dorm_name=req.dorm_name or "",
        random_ship_mode=req.random_ship_mode or 0,
        random_flag_ship_enabled=req.random_flag_ship_enabled or False,
    )
    return success(data=PlayerMutationResponse(
        commander_id=req.commander_id, account_id=req.account_id or 0, name=name,
        level=req.level or 1, exp=req.exp or 0, last_login=now.isoformat(),
        banned=False, online=False,
    ).dict())


async def update_player(request: Request):
    try:
        commander_id = parse_commander_id(request)
    except ValueError:
        return error("bad_request", "invalid id", status_code=400)
    row = await get_commander(commander_id)
    if row is None:
        return error("not_found", "commander not found", status_code=404)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = PlayerUpdateRequest(**body)
    fields = {}
    if req.account_id is not None:
        fields["account_id"] = req.account_id
    if req.name is not None:
        name = req.name.strip()
        if not name:
            return error("bad_request", "name is required", status_code=400)
        if await commander_name_exists(name, exclude_id=commander_id):
            return error("conflict", "name already exists", status_code=409)
        fields["name"] = name
    for field in ("level", "exp", "guide_index", "new_guide_index", "room_id", "exchange_count",
                  "draw_count1", "draw_count10", "support_requisition_count", "support_requisition_month",
                  "acc_pay_lv", "living_area_cover_id", "selected_icon_frame_id", "selected_chat_frame_id",
                  "selected_battle_ui_id", "display_icon_id", "display_skin_id", "display_icon_theme_id",
                  "random_ship_mode"):
        val = getattr(req, field, None)
        if val is not None:
            fields[field] = val
    if req.random_flag_ship_enabled is not None:
        fields["random_flag_ship_enabled"] = req.random_flag_ship_enabled
    if req.last_login is not None:
        fields["last_login"] = req.last_login
    if req.name_change_cooldown is not None:
        fields["name_change_cooldown"] = req.name_change_cooldown
    if not fields:
        return error("bad_request", "no updates provided", status_code=400)
    await update_commanders_dynamic(commander_id, **fields)
    updated_row = await get_commander(commander_id)
    return success(data=PlayerMutationResponse(
        commander_id=updated_row["commander_id"],
        account_id=updated_row.get("account_id", 0),
        name=updated_row.get("name", ""),
        level=updated_row.get("level", 0),
        exp=updated_row.get("exp", 0),
        last_login=_fmt_val(updated_row.get("last_login")),
    ).dict())


async def delete_player(request: Request):
    try:
        commander_id = parse_commander_id(request)
    except ValueError:
        return error("bad_request", "invalid id", status_code=400)
    await delete_commander_by_id(commander_id)
    return success(data=None)


async def player_resources(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    all_resources = await list_all_resource_types()
    owned = await list_owned_resources_by_commander(commander["commander_id"])
    resource_map = {r["resource_id"]: r["amount"] for r in owned}
    entries = [PlayerResourceEntry(resource_id=r["id"], amount=resource_map.get(r["id"], 0), name=r["name"]) for r in all_resources]
    return success(data=PlayerResourceResponse(resources=entries).dict())


async def player_resource(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        resource_id = parse_path_uint32(request.path_params.get("resource_id", ""), "resource id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    r = await get_owned_resource(commander["commander_id"], resource_id)
    if r is None:
        return error("not_found", "resource not owned", status_code=404)
    name = await get_resource_name(resource_id)
    return success(data=PlayerResourceEntry(resource_id=r["resource_id"], amount=r["amount"], name=name or "").dict())


async def delete_player_resource(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        resource_id = parse_path_uint32(request.path_params.get("resource_id", ""), "resource id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    result = await delete_owned_resource(commander["commander_id"], resource_id)
    if result == "DELETE 0":
        return error("not_found", "resource not owned", status_code=404)
    return success(data=None)


async def update_resources_bulk(request: Request):
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
    req = ResourceUpdateRequest(**body)
    seen = set()
    for r in req.resources:
        if r.resource_id in seen:
            return error("bad_request", "duplicate resource_id values", status_code=400)
        seen.add(r.resource_id)
    for entry in req.resources:
        await upsert_owned_resource(commander_id, entry.resource_id, entry.amount)
    return success(data=None)

async def player_ships(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    rows = await list_owned_ships_by_owner(commander["commander_id"])
    ships = [PlayerShipEntry(owned_id=r["owned_id"], ship_id=r["ship_id"], level=r["level"], rarity=r["rarity"],
                              name=r["name"], skin_id=r["skin_id"]) for r in rows]
    return success(data=PlayerShipResponse(ships=ships).dict())


async def player_ship(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        owned_id = parse_path_uint32(request.path_params.get("owned_id", ""), "owned id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    r = await get_owned_ship(commander["commander_id"], owned_id)
    if r is None:
        return error("not_found", "ship not owned", status_code=404)
    return success(data=PlayerOwnedShipEntry(
        owned_id=r["id"], ship_id=r["ship_id"], level=r["level"],
        exp=r.get("exp", 0), intimacy=r.get("intimacy", 0),
        skin_id=r.get("skin_id", 0), is_locked=r.get("is_locked", False),
        propose=r.get("propose", False), energy=r.get("energy", 0),
        create_time=str(r["create_time"]) if r.get("create_time") else None,
        change_name_timestamp=str(r["change_name_timestamp"]) if r.get("change_name_timestamp") else None,
        custom_name=r.get("custom_name", ""),
        surplus_exp=r.get("surplus_exp", 0), max_level=r.get("max_level", 70),
        common_flag=r.get("common_flag", False), blueprint_flag=r.get("blueprint_flag", False),
        proficiency=r.get("proficiency", False), activity_npc=r.get("activity_npc", 0),
        is_secretary=r.get("is_secretary", False), secretary_position=r.get("secretary_position"),
        secretary_phantom_id=r.get("secretary_phantom_id", 0),
        deleted_at=str(r["deleted_at"]) if r.get("deleted_at") else None,
    ).dict())


async def create_player_ship(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = PlayerShipCreateRequest(**body)
    new_id = await create_owned_ship(
        commander["commander_id"], req.ship_id, req.level, req.intimacy, req.exp,
    )
    return success(data=PlayerOwnedShipEntry(
        owned_id=new_id, ship_id=req.ship_id, level=req.level,
        intimacy=req.intimacy, exp=req.exp,
    ).dict())


async def update_player_ship(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        owned_id = parse_path_uint32(request.path_params.get("owned_id", ""), "owned id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    existing = await get_owned_ship(commander["commander_id"], owned_id)
    if existing is None:
        return error("not_found", "ship not owned", status_code=404)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = PlayerShipUpdateRequest(**body)
    fields = {}
    for field in ("level", "intimacy", "exp", "book_exp", "likes"):
        val = getattr(req, field, None)
        if val is not None:
            fields[field] = val
    if not fields:
        return error("bad_request", "no updates provided", status_code=400)
    await update_owned_ship_dynamic(commander["commander_id"], owned_id, **fields)
    return success(data=None)


async def delete_player_ship(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        owned_id = parse_path_uint32(request.path_params.get("owned_id", ""), "owned id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    result = await delete_owned_ship(commander["commander_id"], owned_id)
    if result == "DELETE 0":
        return error("not_found", "ship not owned", status_code=404)
    return success(data=None)


async def player_secretaries(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    rows = await list_secretaries(commander["commander_id"])
    secretaries = [r["id"] for r in rows]
    return success(data=PlayerSecretaries(secretaries=secretaries).dict())


async def replace_player_secretaries(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = PlayerSecretaries(**body)
    await clear_secretaries(commander["commander_id"])
    for ship_id in req.secretaries:
        await set_secretary(commander["commander_id"], ship_id)
    return success(data=None)


async def delete_player_secretaries(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    await clear_secretaries(commander["commander_id"])
    return success(data=None)


async def player_items(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    all_items = await list_all_items()
    item_rows = await list_commander_items(commander["commander_id"])
    misc_rows = await list_commander_misc_items(commander["commander_id"])
    # misc_rows has item_id, data (no JOIN needed)
    item_map = {r["item_id"]: r["count"] for r in item_rows}
    for r in misc_rows:
        item_map[r["item_id"]] = item_map.get(r["item_id"], 0) + r["data"]
    entries = [PlayerItemEntry(item_id=it["id"], count=item_map.get(it["id"], 0), name=it["name"]) for it in all_items]
    return success(data=PlayerItemResponse(items=entries).dict())


async def player_item(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        item_id = parse_path_uint32(request.path_params.get("item_id", ""), "item id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    ci = await get_commander_item(commander["commander_id"], item_id)
    mi = await get_commander_misc_item_data(commander["commander_id"], item_id)
    if ci is None and mi is None:
        return error("not_found", "item not owned", status_code=404)
    count = (ci["count"] if ci else 0) + (mi if mi else 0)
    name = await get_item_name(item_id)
    return success(data=PlayerItemEntry(item_id=item_id, count=count, name=name or "").dict())


async def update_player_item_quantity(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        item_id = parse_path_uint32(request.path_params.get("item_id", ""), "item id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = PlayerItemQuantityUpdateRequest(**body)
    await upsert_commander_item(commander["commander_id"], item_id, req.quantity)
    return success(data=None)


async def delete_player_item(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        item_id = parse_path_uint32(request.path_params.get("item_id", ""), "item id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    await delete_commander_item(commander["commander_id"], item_id)
    await delete_commander_misc_item(commander["commander_id"], item_id)
    return success(data=None)


async def player_equipment(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    rows = await list_owned_equipment(commander["commander_id"])
    entries = [PlayerEquipmentEntry(equipment_id=r["equipment_id"], count=r["count"]) for r in rows]
    return success(data=PlayerEquipmentResponse(equipment=entries).dict())


async def player_equipment_entry(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        equipment_id = parse_path_uint32(request.path_params.get("equipment_id", ""), "equipment id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    r = await get_owned_equipment(commander["commander_id"], equipment_id)
    if r is None:
        return error("not_found", "equipment not owned", status_code=404)
    return success(data=PlayerEquipmentEntry(equipment_id=r["equipment_id"], count=r["count"]).dict())


async def upsert_player_equipment(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = PlayerEquipmentUpsertRequest(**body)
    await upsert_owned_equipment(commander["commander_id"], req.equipment_id, req.count)
    return success(data=None)


async def delete_player_equipment(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        equipment_id = parse_path_uint32(request.path_params.get("equipment_id", ""), "equipment id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    await delete_owned_equipment(commander["commander_id"], equipment_id)
    return success(data=None)


async def player_ship_equipment(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        owned_id = parse_path_uint32(request.path_params.get("owned_id", ""), "owned id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    ship = await get_owned_ship(commander["commander_id"], owned_id)
    if ship is None:
        return error("not_found", "ship not owned", status_code=404)
    rows = await list_ship_equipment(commander["commander_id"], owned_id)
    entries = [PlayerShipEquipmentEntry(pos=r["pos"], equip_id=r["equip_id"], skin_id=r.get("skin_id", 0)) for r in rows]
    return success(data=PlayerShipEquipmentResponse(equipment=entries).dict())


async def update_player_ship_equipment(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        owned_id = parse_path_uint32(request.path_params.get("owned_id", ""), "owned id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    ship = await get_owned_ship(commander["commander_id"], owned_id)
    if ship is None:
        return error("not_found", "ship not owned", status_code=404)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = PlayerShipEquipmentUpdateRequest(**body)
    await replace_ship_equipment(
        commander["commander_id"], owned_id,
        [{"pos": e.pos, "equip_id": e.equip_id, "skin_id": e.skin_id} for e in req.equipment],
    )
    return success(data=None)


async def player_misc_items(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    rows = await list_commander_misc_items_with_name(commander["commander_id"])
    entries = [PlayerMiscItemEntry(item_id=r["item_id"], data=r["data"], name=r["name"]) for r in rows]
    return success(data=PlayerMiscItemResponse(items=entries).dict())


async def player_misc_item(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        item_id = parse_path_uint32(request.path_params.get("item_id", ""), "item id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    r = await get_commander_misc_item(commander["commander_id"], item_id)
    if r is None:
        return error("not_found", "misc item not owned", status_code=404)
    return success(data=PlayerMiscItemEntry(item_id=r["item_id"], data=r["data"], name=r["name"]).dict())


async def update_player_misc_item(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        item_id = parse_path_uint32(request.path_params.get("item_id", ""), "item id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = PlayerMiscItemUpdateRequest(**body)
    await upsert_commander_misc_item(commander["commander_id"], item_id, req.data)
    return success(data=None)


async def delete_player_misc_item(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        item_id = parse_path_uint32(request.path_params.get("item_id", ""), "item id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    await delete_commander_misc_item(commander["commander_id"], item_id)
    return success(data=None)


async def player_fleets(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    rows = await list_fleets(commander["commander_id"])
    entries = []
    for r in rows:
        ship_ids = await list_fleet_ships(r["id"])
        entries.append(PlayerFleetEntry(
            fleet_id=r["id"],
            name=r.get("name", "") or "",
            ships=ship_ids,
        ))
    return success(data=PlayerFleetResponse(fleets=entries).dict())


async def player_fleet(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        fleet_id = parse_path_uint32(request.path_params.get("fleet_id", ""), "fleet id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    r = await get_fleet(commander["commander_id"], fleet_id)
    if r is None:
        return error("not_found", "fleet not found", status_code=404)
    ship_ids = await list_fleet_ships(r["id"])
    return success(data=PlayerFleetEntry(fleet_id=r["id"], name=r.get("name", "") or "",
                                          ships=ship_ids).dict())


async def create_player_fleet(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = PlayerFleetCreateRequest(**body)
    await create_fleet_row(req.fleet_id, commander["commander_id"], req.name)
    for ship_id in req.ships:
        await add_fleet_ship(req.fleet_id, ship_id)
    return success(data=None)


async def update_player_fleet(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        fleet_id = parse_path_uint32(request.path_params.get("fleet_id", ""), "fleet id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    existing = await get_fleet(commander["commander_id"], fleet_id)
    if existing is None:
        return error("not_found", "fleet not found", status_code=404)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = PlayerFleetUpdateRequest(**body)
    if req.name is not None:
        await update_fleet_name(fleet_id, req.name)
    if req.ships is not None:
        await clear_fleet_ships(fleet_id)
        for ship_id in req.ships:
            await add_fleet_ship(fleet_id, ship_id)
    return success(data=None)


async def delete_player_fleet(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        fleet_id = parse_path_uint32(request.path_params.get("fleet_id", ""), "fleet id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    await delete_fleet(commander["commander_id"], fleet_id)
    return success(data=None)


async def player_skins(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    rows = await list_owned_skins(commander["commander_id"])
    entries = [PlayerSkinEntry(skin_id=r["skin_id"], expires_at=_fmt_val(r.get("expires_at"))) for r in rows]
    return success(data=PlayerSkinResponse(skins=entries).dict())


async def player_skin(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        skin_id = parse_path_uint32(request.path_params.get("skin_id", ""), "skin id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    r = await get_owned_skin(commander["commander_id"], skin_id)
    if r is None:
        return error("not_found", "skin not owned", status_code=404)
    return success(data=PlayerSkinEntry(skin_id=r["skin_id"], expires_at=_fmt_val(r.get("expires_at"))).dict())


async def update_player_skin(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        skin_id = parse_path_uint32(request.path_params.get("skin_id", ""), "skin id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = PlayerSkinUpdateRequest(**body)
    existing = await get_owned_skin(commander["commander_id"], skin_id)
    if existing is None:
        return error("not_found", "skin not owned", status_code=404)
    if req.expires_at is not None:
        await update_owned_skin_expires(commander["commander_id"], skin_id, req.expires_at)
    return success(data=None)


async def delete_player_skin(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        skin_id = parse_path_uint32(request.path_params.get("skin_id", ""), "skin id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    await delete_owned_skin(commander["commander_id"], skin_id)
    return success(data=None)


async def player_buffs(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    rows = await list_commander_buffs_row(commander["commander_id"])
    entries = [PlayerBuffEntry(buff_id=r["buff_id"], timestamp=r.get("timestamp", 0), instigator=r.get("instigator", 0))
               for r in rows]
    return success(data=PlayerBuffsResponse(buffs=entries).dict())


async def player_buff(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        buff_id = parse_path_uint32(request.path_params.get("buff_id", ""), "buff id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    r = await get_commander_buff(commander["commander_id"], buff_id)
    if r is None:
        return error("not_found", "buff not found", status_code=404)
    return success(data=PlayerBuffEntry(buff_id=r["buff_id"], timestamp=r.get("timestamp", 0),
                                         instigator=r.get("instigator", 0)).dict())


async def add_player_buff(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = PlayerBuffEntry(**body)
    await insert_commander_buff(commander["commander_id"], req.buff_id, req.timestamp, req.instigator)
    return success(data=None)


async def update_player_buff(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        buff_id = parse_path_uint32(request.path_params.get("buff_id", ""), "buff id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = PlayerBuffUpdateRequest(**body)
    fields = {}
    if req.timestamp is not None:
        fields["timestamp"] = req.timestamp
    if req.instigator is not None:
        fields["instigator"] = req.instigator
    if not fields:
        return error("bad_request", "no updates provided", status_code=400)
    await update_commander_buff_dynamic(commander["commander_id"], buff_id, **fields)
    return success(data=None)


async def delete_player_buff(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        buff_id = parse_path_uint32(request.path_params.get("buff_id", ""), "buff id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    await delete_commander_buff(commander["commander_id"], buff_id)
    return success(data=None)


async def player_flags(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    rows = await list_commander_flags(commander["commander_id"])
    entries = [PlayerFlagEntry(flag_id=r["flag_id"], value=r["value"], updated_at=_fmt_val(r.get("updated_at")))
               for r in rows]
    return success(data=PlayerFlagsResponse(flags=entries).dict())


async def add_player_flag(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = PlayerFlagCreateRequest(**body)
    import datetime
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    await upsert_commander_flag(commander["commander_id"], req.flag_id, req.value, now_iso)
    return success(data=None)


async def delete_player_flag(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        flag_id = parse_path_uint32(request.path_params.get("flag_id", ""), "flag id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    await delete_commander_flag(commander["commander_id"], flag_id)
    return success(data=None)


async def player_likes(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    rows = await list_commander_likes(commander["commander_id"])
    entries = [PlayerLikeEntry(group_id=r["group_id"], like_id=r.get("like_id", 0), timestamp=r.get("timestamp", 0))
               for r in rows]
    return success(data=PlayerLikesResponse(likes=entries).dict())


async def add_player_like(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = PlayerLikeCreateRequest(**body)
    import time
    await upsert_commander_like(commander["commander_id"], req.group_id, req.like_id, int(time.time()))
    return success(data=None)


async def delete_player_like(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        group_id = parse_path_uint32(request.path_params.get("group_id", ""), "group id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    await delete_commander_like(commander["commander_id"], group_id)
    return success(data=None)


def fmt_val(value):
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


_fmt_val = fmt_val


async def guide_list(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    return success(data={"guide_index": commander.get("guide_index", 0), "new_guide_index": commander.get("new_guide_index", 0)})


async def update_guide(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    fields = {}
    gi = body.get("guide_index")
    if gi is not None:
        fields["guide_index"] = int(gi)
    ngi = body.get("new_guide_index")
    if ngi is not None:
        fields["new_guide_index"] = int(ngi)
    if not fields:
        return error("bad_request", "no updates provided", status_code=400)
    await update_commanders_dynamic(commander["commander_id"], **fields)
    return success(data=None)


async def list_stories(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    rows = await list_commander_stories_rows(commander["commander_id"])
    stories = [{"story_id": str(r["story_id"]), "timestamp": int(r["created_at"].timestamp()) if r.get("created_at") else 0} for r in rows]
    return success(data={"stories": stories})


async def add_story(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    story_id = body.get("story_id", "")
    if not story_id:
        return error("bad_request", "story_id required", status_code=400)
    await upsert_commander_story(commander["commander_id"], str(story_id))
    return success(data=None)


async def list_attire(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    rows = await list_commander_attires_rows(commander["commander_id"])
    attires = []
    for r in rows:
        entry = {"type": r["type"], "attire_id": r["attire_id"]}
        if r.get("expires_at"):
            entry["expires_at"] = r["expires_at"].isoformat() if hasattr(r["expires_at"], "isoformat") else r["expires_at"]
        if r.get("is_new"):
            entry["is_new"] = r["is_new"]
        attires.append(entry)
    return success(data={"attires": attires})


async def create_attire(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    attire_type = body.get("type")
    attire_id = body.get("attire_id")
    if attire_type is None or attire_id is None:
        return error("bad_request", "type and attire_id required", status_code=400)
    expires_at = body.get("expires_at")
    is_new = body.get("is_new", False)
    await upsert_commander_attire(commander["commander_id"], int(attire_type), int(attire_id), expires_at, bool(is_new))
    return success(data=None)


async def update_attire(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        attire_type = parse_path_uint32(request.path_params.get("attire_type", ""), "attire type")
        attire_id = parse_path_uint32(request.path_params.get("attire_id", ""), "attire id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    existing = await get_commander_attire(commander["commander_id"], attire_type, attire_id)
    if existing is None:
        return error("not_found", "attire not owned", status_code=404)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    expires_at = body.get("expires_at")
    is_new = body.get("is_new")
    if expires_at is None and is_new is None:
        return error("bad_request", "no updates provided", status_code=400)
    if expires_at is not None:
        await update_attire_expires(commander["commander_id"], attire_type, attire_id, expires_at)
    if is_new is not None:
        await update_attire_is_new(commander["commander_id"], attire_type, attire_id, bool(is_new))
    return success(data=None)


async def delete_attire(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        attire_type = parse_path_uint32(request.path_params.get("attire_type", ""), "attire type")
        attire_id = parse_path_uint32(request.path_params.get("attire_id", ""), "attire id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    tag = await delete_commander_attire(commander["commander_id"], attire_type, attire_id)
    if tag == "DELETE 0":
        return error("not_found", "attire not owned", status_code=404)
    return success(data=None)


async def update_attire_selection(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    fields = {}
    for field in ("selected_icon_frame_id", "selected_chat_frame_id", "selected_battle_ui_id", "display_icon_id", "display_skin_id", "display_icon_theme_id"):
        val = body.get(field)
        if val is not None:
            fields[field] = int(val)
    if not fields:
        return error("bad_request", "no updates provided", status_code=400)
    await update_commanders_dynamic(commander["commander_id"], **fields)
    return success(data=None)


async def get_attire_selection(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    return success(data={
        "selected_icon_frame_id": commander.get("selected_icon_frame_id", 0),
        "selected_chat_frame_id": commander.get("selected_chat_frame_id", 0),
        "selected_battle_ui_id": commander.get("selected_battle_ui_id", 0),
        "display_icon_id": commander.get("display_icon_id", 0),
        "display_skin_id": commander.get("display_skin_id", 0),
        "display_icon_theme_id": commander.get("display_icon_theme_id", 0),
    })


async def get_random_flag_ship(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    return success(data={"enabled": commander.get("random_flag_ship_enabled", False)})


async def update_random_flag_ship(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    enabled = body.get("enabled")
    if enabled is None:
        return error("bad_request", "enabled required", status_code=400)
    await update_commanders_dynamic(commander["commander_id"], random_flag_ship_enabled=bool(enabled))
    return success(data=None)


async def list_random_flag_ship_entries(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    rows = await list_random_flag_ship_rows(commander["commander_id"])
    entries = [{"ship_id": r["ship_id"], "phantom_id": r["phantom_id"], "enabled": r["enabled"]} for r in rows]
    return success(data={"entries": entries})


async def upsert_random_flag_ship_entry(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    ship_id = body.get("ship_id")
    phantom_id = body.get("phantom_id", 0)
    enabled = body.get("enabled", False)
    if ship_id is None:
        return error("bad_request", "ship_id required", status_code=400)
    await upsert_random_flag_ship(commander["commander_id"], int(ship_id), int(phantom_id), bool(enabled))
    return success(data=None)


async def delete_random_flag_ship_entry(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    ship_id = request.path_params.get("ship_id")
    if not ship_id:
        return error("bad_request", "ship_id required", status_code=400)
    try:
        ship_id = int(ship_id)
    except (ValueError, TypeError):
        return error("bad_request", "invalid ship_id", status_code=400)
    tag = await delete_random_flag_ship(commander["commander_id"], ship_id)
    if tag == "DELETE 0":
        return error("not_found", "entry not found", status_code=404)
    return success(data=None)


async def get_living_area_cover(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    rows = await list_commander_living_area_covers_rows(commander["commander_id"])
    owned = [r["cover_id"] for r in rows]
    selected = commander.get("living_area_cover_id", 0)
    if selected and selected not in owned:
        owned.append(selected)
    return success(data={"selected": selected, "owned": owned})


async def update_living_area_cover(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    cover_id = body.get("cover_id")
    if cover_id is None:
        return error("bad_request", "cover_id required", status_code=400)
    await update_commander_living_area_cover(commander["commander_id"], int(cover_id))
    return success(data=None)


async def add_living_area_cover(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    cover_id = body.get("cover_id")
    if cover_id is None:
        return error("bad_request", "cover_id required", status_code=400)
    await insert_living_area_cover(commander["commander_id"], int(cover_id))
    return success(data=None)


async def patch_living_area_cover(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        cover_id = parse_path_uint32(request.path_params.get("cover_id", ""), "cover id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    if not await has_living_area_cover(commander["commander_id"], cover_id):
        return error("not_found", "cover not owned", status_code=404)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    is_new = body.get("is_new")
    if is_new is None:
        return error("bad_request", "is_new required", status_code=400)
    await update_living_area_cover_is_new(commander["commander_id"], cover_id, bool(is_new))
    return success(data=None)


async def delete_living_area_cover(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        cover_id = parse_path_uint32(request.path_params.get("cover_id", ""), "cover id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    if not await delete_living_area_cover_row(commander["commander_id"], cover_id):
        return error("not_found", "cover not owned", status_code=404)
    return success(data=None)


async def list_mails(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    rows = await list_mails_for_commander(commander["commander_id"])
    mails = [{
        "mail_id": r["id"], "read": r["read"],
        "date": r["date"].isoformat() if r.get("date") else "",
        "title": r["title"] or "", "body": r["body"] or "",
        "attachments_collected": r["attachments_collected"],
        "is_important": r["is_important"],
        "custom_sender": r["custom_sender"] or "",
        "is_archived": r["is_archived"],
        "created_at": r["created_at"].isoformat() if r.get("created_at") else "",
    } for r in rows]
    return success(data={"mails": mails})


async def update_mail(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        mail_id = parse_path_uint32(request.path_params.get("mail_id", ""), "mail id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    mail = await get_mail(mail_id, commander["commander_id"])
    if mail is None:
        return error("not_found", "mail not found", status_code=404)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    fields = {}
    if "read" in body:
        fields["read"] = bool(body["read"])
    if "important" in body:
        fields["is_important"] = bool(body["important"])
    if "archived" in body:
        fields["is_archived"] = bool(body["archived"])
    if "attachments_collected" in body and body["attachments_collected"]:
        if not mail["attachments_collected"]:
            fields["attachments_collected"] = True
    if not fields:
        return error("bad_request", "no updates provided", status_code=400)
    await update_mail_dynamic(mail_id, **fields)
    return success(data=None)


async def send_mail(request: Request):
    try:
        commander_id = parse_commander_id(request)
    except ValueError:
        return error("bad_request", "invalid id", status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    title = body.get("title", "")
    mail_body = body.get("body", "")
    custom_sender = body.get("custom_sender")
    attachments = body.get("attachments", [])
    if not title and not mail_body:
        return error("bad_request", "title or body required", status_code=400)
    mail_id = await create_mail(commander_id, title, mail_body, custom_sender)
    for att in attachments:
        await create_mail_attachment(mail_id, int(att.get("type", 0)), int(att.get("item_id", 0)), int(att.get("quantity", 0)))
    return success(data=None)


async def list_compensations(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    rows = await orm_list_compensations(commander["commander_id"])
    compensations = []
    for r in rows:
        att_rows = await list_compensation_attachments(r["id"])
        compensations.append({
            "compensation_id": r["id"],
            "title": r["title"] or "",
            "text": r["text"] or "",
            "send_time": r["send_time"].isoformat() if r.get("send_time") else "",
            "expires_at": r["expires_at"].isoformat() if r.get("expires_at") else "",
            "attach_flag": r["attach_flag"],
            "created_at": r["created_at"].isoformat() if r.get("created_at") else "",
            "attachments": [{"type": a["type"], "item_id": a["item_id"], "quantity": a["quantity"]} for a in att_rows],
        })
    return success(data={"compensations": compensations})


async def create_compensation(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    title = body.get("title", "")
    text_body = body.get("text", "")
    expires_at = body.get("expires_at")
    send_time = body.get("send_time")
    attachments = body.get("attachments", [])
    if not expires_at:
        return error("bad_request", "expires_at required", status_code=400)
    import datetime
    if not send_time:
        send_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
    comp_id = await orm_create_compensation(commander["commander_id"], title, text_body, send_time, expires_at)
    for att in attachments:
        await create_compensation_attachment(comp_id, int(att.get("type", 0)), int(att.get("item_id", 0)), int(att.get("quantity", 0)))
    return success(data=None)


async def list_builds(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    rows = await list_builds_for_builder(commander["commander_id"])
    builds = []
    for r in rows:
        ship_name = await get_ship_name(r["ship_id"])
        builds.append({
            "build_id": r["id"],
            "ship_id": r["ship_id"],
            "ship_name": ship_name or "",
            "pool_id": r["pool_id"],
            "finishes_at": r["finishes_at"].isoformat() if r.get("finishes_at") else "",
        })
    return success(data={"builds": builds})


async def create_build(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    ship_id = body.get("ship_id")
    pool_id = body.get("pool_id", 0)
    finishes_at_raw = body.get("finishes_at")
    if ship_id is None or not finishes_at_raw:
        return error("bad_request", "ship_id and finishes_at required", status_code=400)
    try:
        # store a real timestamptz, not a text cast at the driver's mercy
        finishes_at = datetime.datetime.fromisoformat(str(finishes_at_raw))
        if finishes_at.tzinfo is None:
            finishes_at = finishes_at.replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        return error("bad_request", "finishes_at must be an ISO-8601 timestamp", status_code=400)
    build_id = await orm_create_build(commander["commander_id"], int(ship_id), int(pool_id), finishes_at)
    ship_name = await get_ship_name(int(ship_id))
    return success(data={
        "build_id": build_id,
        "ship_id": int(ship_id),
        "ship_name": ship_name or "",
        "pool_id": int(pool_id),
        "finishes_at": finishes_at.isoformat(),
    })


async def update_build(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        build_id = parse_path_uint32(request.path_params.get("build_id", ""), "build id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    build = await get_build_by_id(build_id)
    if build is None:
        return error("not_found", "build not found", status_code=404)
    if build["builder_id"] != commander["commander_id"]:
        return error("not_found", "build not found", status_code=404)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    fields = {}
    if "ship_id" in body:
        fields["ship_id"] = int(body["ship_id"])
    if "finishes_at" in body:
        try:
            parsed = datetime.datetime.fromisoformat(str(body["finishes_at"]))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            return error("bad_request", "finishes_at must be an ISO-8601 timestamp", status_code=400)
        fields["finishes_at"] = parsed
    if not fields:
        return error("bad_request", "no updates provided", status_code=400)
    await update_build_dynamic(build_id, **fields)
    return success(data=None)


async def delete_build(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        build_id = parse_path_uint32(request.path_params.get("build_id", ""), "build id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    build = await get_build_by_id(build_id)
    if build is None:
        return error("not_found", "build not found", status_code=404)
    if build["builder_id"] != commander["commander_id"]:
        return error("not_found", "build not found", status_code=404)
    await delete_build_by_id(build_id)
    return success(data=None)


async def get_build_queue(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    rows = await list_build_queue(commander["commander_id"])
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    queue = []
    for i, r in enumerate(rows):
        remaining = 0
        finish_time = 0
        if r.get("finishes_at"):
            ft = r["finishes_at"]
            if hasattr(ft, "tzinfo") and ft.tzinfo is None:
                ft = ft.replace(tzinfo=datetime.timezone.utc)
            remaining = max(0, int((ft - now).total_seconds())) if hasattr(ft, "timestamp") else 0
            finish_time = int(ft.timestamp()) if hasattr(ft, "timestamp") else 0
        queue.append({"slot": i + 1, "pool_id": r["pool_id"], "remaining_seconds": remaining, "finish_time": finish_time})
    from src.answer.shipbuild.helpers import _current_dock_slots
    return success(data={
        "worklist_count": _current_dock_slots(),
        "worklist_list": queue,
        "draw_count1": commander.get("draw_count1", 0),
        "draw_count10": commander.get("draw_count10", 0),
        "exchange_count": commander.get("exchange_count", 0),
    })


async def update_build_counters(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    fields = {}
    for field in ("draw_count1", "draw_count10", "exchange_count"):
        val = body.get(field)
        if val is not None:
            fields[field] = int(val)
    if not fields:
        return error("bad_request", "no updates provided", status_code=400)
    await update_commanders_dynamic(commander["commander_id"], **fields)
    return success(data=None)


async def list_punishments(request: Request):
    try:
        commander_id = parse_commander_id(request)
    except ValueError:
        return error("bad_request", "invalid id", status_code=400)
    if not await commander_exists(commander_id):
        return error("not_found", "commander not found", status_code=404)
    rows = await list_punishments_for_commander(commander_id)
    punishments = [{
        "punishment_id": r["id"], "punished_id": r["punished_id"],
        "lift_timestamp": r["lift_timestamp"].isoformat() if r.get("lift_timestamp") else "",
        "is_permanent": r["is_permanent"],
    } for r in rows]
    return success(data={"punishments": punishments})


async def ban_player(request: Request):
    try:
        commander_id = parse_commander_id(request)
    except ValueError:
        return error("bad_request", "invalid id", status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    permanent = body.get("permanent", False)
    lift_timestamp = body.get("lift_timestamp")
    duration_sec = body.get("duration_sec")
    if permanent and (lift_timestamp or duration_sec is not None):
        return error("bad_request", "permanent cannot be combined with lift_timestamp or duration_sec", status_code=400)
    if lift_timestamp and duration_sec is not None:
        return error("bad_request", "lift_timestamp and duration_sec cannot both be set", status_code=400)
    if not permanent and not lift_timestamp and duration_sec is None:
        return error("bad_request", "ban requires duration_sec, lift_timestamp, or permanent=true", status_code=400)
    if not await commander_exists(commander_id):
        return error("not_found", "commander not found", status_code=404)
    lift_ts = None
    if lift_timestamp:
        lift_ts = lift_timestamp
    if duration_sec is not None:
        import datetime
        lift_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    await insert_punishment(commander_id, lift_ts, bool(permanent))
    return success(data=None)


async def update_punishment(request: Request):
    try:
        commander_id = parse_commander_id(request)
    except ValueError:
        return error("bad_request", "invalid id", status_code=400)
    try:
        punishment_id = parse_path_uint32(request.path_params.get("punishment_id", ""), "punishment id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    if not await commander_exists(commander_id):
        return error("not_found", "commander not found", status_code=404)
    punishment = await get_punishment_by_id(punishment_id, commander_id)
    if punishment is None:
        return error("not_found", "punishment not found", status_code=404)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    permanent = body.get("permanent")
    lift_timestamp = body.get("lift_timestamp")
    if permanent is None and lift_timestamp is None:
        return error("bad_request", "no updates provided", status_code=400)
    if permanent is not None:
        await update_punishment_permanent(punishment_id, bool(permanent))
        if permanent:
            await clear_punishment_lift(punishment_id)
    if lift_timestamp is not None:
        lt = lift_timestamp if lift_timestamp.strip() else None
        await update_punishment_lift(punishment_id, lt)
    return success(data=None)


async def kick_player(request: Request):
    try:
        commander_id = parse_commander_id(request)
    except ValueError:
        return error("bad_request", "invalid id", status_code=400)
    try:
        body = await request.json()
    except Exception:
        body = {}
    reason = body.get("reason", 0)
    try:
        reason_code = int(reason)
    except (ValueError, TypeError):
        reason_code = 0

    from src.connection.server import get_instance
    server = get_instance()
    disconnected = False
    if server is not None:
        disconnected = await server.disconnect_commander(commander_id, reason_code)

    return success(data={"disconnected": disconnected})


async def support_requisition(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    month = now.year * 100 + now.month
    await update_commanders_dynamic(commander["commander_id"],
                                    support_requisition_month=month, support_requisition_count=0)
    return success(data={"month": month, "count": 0, "cap": 30})


async def get_support_requisition(request: Request):
    commander, err_resp = await load_commander_detail(request)
    if err_resp:
        return err_resp
    return success(data={
        "month": commander.get("support_requisition_month", 0),
        "count": commander.get("support_requisition_count", 0),
    })
