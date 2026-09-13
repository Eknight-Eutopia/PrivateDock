from fastapi import Request
from src.api.response.response import ok as success, error
from src.api.types import *
from src.db.store import NotFoundError
from src.orm import admin
from .players import parse_path_uint32, parse_path_uint64, parse_optional_uint32, parse_pagination


def write_game_data_error(err, item: str):
    if isinstance(err, NotFoundError):
        return error(code="not_found", message=f"{item} not found", status_code=404)
    return error(code="internal_error", message=f"failed to load {item}", status_code=500)


# ---- Ships ----

async def list_ships(request: Request):
    try:
        meta = parse_pagination(request)
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    name = (request.query_params.get("name") or "").strip()
    kwargs = dict(offset=meta.offset, limit=meta.limit, name=name)
    for qp, field in [("rarity", "rarity_id"), ("type", "type_id"), ("nationality", "nationality_id")]:
        raw = request.query_params.get(qp)
        try:
            val = parse_optional_uint32(raw, qp)
        except ValueError as e:
            return error(code=400, message=str(e), status_code=400)
        if val is not None:
            kwargs[field] = val
    try:
        ships_page, total = admin.list_ships_page(**kwargs)
    except Exception:
        return error(code=500, message="failed to list ships", status_code=500)
    ships = [ShipSummary(
        id=s['template_id'],
        name=s['name'],
        english_name=s['english_name'],
        rarity_id=s['rarity_id'],
        star=s['star'],
        type=s['type'],
        nationality=s['nationality'],
        build_time=s['build_time'],
        pools=s['pools'],
    ) for s in ships_page]
    payload = ShipListResponse(ships=ships, meta=PaginationMeta(offset=meta.offset, limit=meta.limit, total=total))
    return success(data=payload)


async def ship_detail(request: Request):
    try:
        ship_id = parse_path_uint32(request.path_params.get("id", ""), "ship id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    ship = admin.get_ship_by_template_id(ship_id)
    if ship is None:
        return write_game_data_error(Exception("not found"), "ship")
    payload = ShipSummary(
        id=ship['template_id'],
        name=ship['name'],
        english_name=ship['english_name'],
        rarity_id=ship['rarity_id'],
        star=ship['star'],
        type=ship['type'],
        nationality=ship['nationality'],
        build_time=ship['build_time'],
        pools=ship['pools'],
    )
    return success(data=payload)


async def create_ship(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = ShipSummary(**body)
    name = (req.name or "").strip()
    english_name = (req.english_name or "").strip()
    if req.id == 0:
        return error(code=400, message="id is required", status_code=400)
    if not name:
        return error(code=400, message="name is required", status_code=400)
    if not english_name:
        return error(code=400, message="english_name is required", status_code=400)
    data = dict(
        template_id=req.id,
        name=name,
        english_name=english_name,
        rarity_id=req.rarity_id,
        star=req.star,
        type=req.type,
        nationality=req.nationality,
        build_time=req.build_time,
        pools=list(req.pools),
    )
    try:
        admin.insert_ship(data)
    except Exception:
        return error(code=500, message="failed to create ship", status_code=500)
    return success(data=None)


async def update_ship(request: Request):
    try:
        ship_id = parse_path_uint32(request.path_params.get("id", ""), "ship id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = ShipSummary(**body)
    name = (req.name or "").strip()
    english_name = (req.english_name or "").strip()
    if not name:
        return error(code=400, message="name is required", status_code=400)
    if not english_name:
        return error(code=400, message="english_name is required", status_code=400)
    ship = admin.get_ship_by_template_id(ship_id)
    if ship is None:
        return write_game_data_error(Exception("not found"), "ship")
    data = dict(
        name=name,
        english_name=english_name,
        rarity_id=req.rarity_id,
        star=req.star,
        type=req.type,
        nationality=req.nationality,
        build_time=req.build_time,
        pools=list(req.pools),
    )
    try:
        admin.update_ship_record(ship_id, data)
    except Exception:
        return error(code=500, message="failed to update ship", status_code=500)
    return success(data=None)


async def delete_ship(request: Request):
    try:
        ship_id = parse_path_uint32(request.path_params.get("id", ""), "ship id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        admin.delete_ship_record(ship_id)
    except Exception:
        return write_game_data_error(Exception("not found"), "ship")
    return success(data=None)


async def ship_skins(request: Request):
    try:
        ship_id = parse_path_uint32(request.path_params.get("id", ""), "ship id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        meta = parse_pagination(request)
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        skins_page, total = admin.list_skins_by_ship_group_page(ship_id, meta.offset, meta.limit)
    except Exception:
        return error(code=500, message="failed to list ship skins", status_code=500)
    skins = [SkinSummary(id=s['id'], name=s['name'], ship_group=s['ship_group']) for s in skins_page]
    payload = SkinListResponse(skins=skins, meta=PaginationMeta(offset=meta.offset, limit=meta.limit, total=total))
    return success(data=payload)


# ---- Requisition Ships ----

async def list_requisition_ships():
    try:
        ids = admin.list_requisition_ship_ids()
    except Exception:
        return error(code=500, message="failed to list requisition ships", status_code=500)
    payload = RequisitionShipListResponse(ship_ids=ids)
    return success(data=payload)


async def create_requisition_ship(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = RequisitionShipRequest(**body)
    if req.ship_id == 0:
        return error(code=400, message="ship_id is required", status_code=400)
    try:
        admin.create_requisition_ship(req.ship_id)
    except Exception:
        return error(code=500, message="failed to create requisition ship", status_code=500)
    return success(data=None)


async def delete_requisition_ship(request: Request):
    try:
        ship_id = parse_path_uint32(request.path_params.get("ship_id", ""), "ship id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        ok = admin.delete_requisition_ship(ship_id)
        if not ok:
            return error(code=404, message="requisition ship not found", status_code=404)
    except Exception:
        return error(code=500, message="failed to delete requisition ship", status_code=500)
    return success(data=None)


# ---- Ship Types ----

async def list_ship_types(request: Request):
    try:
        meta = parse_pagination(request)
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        ship_types, total = admin.list_ship_types(meta.offset, meta.limit)
    except Exception:
        return error(code=500, message="failed to list ship types", status_code=500)
    results = [ShipTypeSummary(id=st['id'], name=st['name']) for st in ship_types]
    payload = ShipTypeListResponse(ship_types=results, meta=PaginationMeta(offset=meta.offset, limit=meta.limit, total=total))
    return success(data=payload)


async def ship_type_detail(request: Request):
    try:
        type_id = parse_path_uint32(request.path_params.get("id", ""), "ship type id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    st = admin.get_ship_type_by_id(type_id)
    if st is None:
        return write_game_data_error(Exception("not found"), "ship type")
    payload = ShipTypeSummary(id=st['id'], name=st['name'])
    return success(data=payload)


async def create_ship_type(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = ShipTypeSummary(**body)
    name = (req.name or "").strip()
    if req.id == 0:
        return error(code=400, message="id is required", status_code=400)
    if not name:
        return error(code=400, message="name is required", status_code=400)
    try:
        admin.create_ship_type(dict(id=req.id, name=name))
    except Exception:
        return error(code=500, message="failed to create ship type", status_code=500)
    return success(data=None)


async def update_ship_type(request: Request):
    try:
        type_id = parse_path_uint32(request.path_params.get("id", ""), "ship type id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = ShipTypeSummary(**body)
    name = (req.name or "").strip()
    if not name:
        return error(code=400, message="name is required", status_code=400)
    st = admin.get_ship_type_by_id(type_id)
    if st is None:
        return write_game_data_error(Exception("not found"), "ship type")
    try:
        admin.update_ship_type(type_id, dict(name=name))
    except Exception:
        return error(code=500, message="failed to update ship type", status_code=500)
    return success(data=None)


async def delete_ship_type(request: Request):
    try:
        type_id = parse_path_uint32(request.path_params.get("id", ""), "ship type id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        admin.delete_ship_type(type_id)
    except Exception:
        return write_game_data_error(Exception("not found"), "ship type")
    return success(data=None)


# ---- Rarities ----

async def list_rarities(request: Request):
    try:
        meta = parse_pagination(request)
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        rarities, total = admin.list_rarities(meta.offset, meta.limit)
    except Exception:
        return error(code=500, message="failed to list rarities", status_code=500)
    results = [RaritySummary(id=r['id'], name=r['name']) for r in rarities]
    payload = RarityListResponse(rarities=results, meta=PaginationMeta(offset=meta.offset, limit=meta.limit, total=total))
    return success(data=payload)


async def rarity_detail(request: Request):
    try:
        rarity_id = parse_path_uint32(request.path_params.get("id", ""), "rarity id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    r = admin.get_rarity_by_id(rarity_id)
    if r is None:
        return write_game_data_error(Exception("not found"), "rarity")
    payload = RaritySummary(id=r['id'], name=r['name'])
    return success(data=payload)


async def create_rarity(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = RaritySummary(**body)
    name = (req.name or "").strip()
    if req.id == 0:
        return error(code=400, message="id is required", status_code=400)
    if not name:
        return error(code=400, message="name is required", status_code=400)
    try:
        admin.create_rarity(dict(id=req.id, name=name))
    except Exception:
        return error(code=500, message="failed to create rarity", status_code=500)
    return success(data=None)


async def update_rarity(request: Request):
    try:
        rarity_id = parse_path_uint32(request.path_params.get("id", ""), "rarity id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = RaritySummary(**body)
    name = (req.name or "").strip()
    if not name:
        return error(code=400, message="name is required", status_code=400)
    r = admin.get_rarity_by_id(rarity_id)
    if r is None:
        return write_game_data_error(Exception("not found"), "rarity")
    try:
        admin.update_rarity(rarity_id, dict(name=name))
    except Exception:
        return error(code=500, message="failed to update rarity", status_code=500)
    return success(data=None)


async def delete_rarity(request: Request):
    try:
        rarity_id = parse_path_uint32(request.path_params.get("id", ""), "rarity id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        admin.delete_rarity(rarity_id)
    except Exception:
        return write_game_data_error(Exception("not found"), "rarity")
    return success(data=None)


# ---- Items ----

async def list_items(request: Request):
    try:
        meta = parse_pagination(request)
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        items_page, total = admin.list_items_page(meta.offset, meta.limit)
    except Exception:
        return error(code=500, message="failed to list items", status_code=500)
    items = [ItemSummary(
        id=it['id'], name=it['name'], rarity=it['rarity'],
        shop_id=it['shop_id'], type=it['type'], virtual_type=it['virtual_type'],
    ) for it in items_page]
    payload = ItemListResponse(items=items, meta=PaginationMeta(offset=meta.offset, limit=meta.limit, total=total))
    return success(data=payload)


async def item_detail(request: Request):
    try:
        item_id = parse_path_uint32(request.path_params.get("id", ""), "item id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    it = admin.get_item_by_id(item_id)
    if it is None:
        return write_game_data_error(Exception("not found"), "item")
    payload = ItemSummary(
        id=it['id'], name=it['name'], rarity=it['rarity'],
        shop_id=it['shop_id'], type=it['type'], virtual_type=it['virtual_type'],
    )
    return success(data=payload)


async def create_item(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = ItemCreateRequest(**body)
    name = (req.name or "").strip()
    if req.id == 0:
        return error(code=400, message="id is required", status_code=400)
    if not name:
        return error(code=400, message="name is required", status_code=400)
    data = dict(id=req.id, name=name, rarity=req.rarity, shop_id=req.shop_id, type=req.type, virtual_type=req.virtual_type)
    try:
        admin.create_item_record(data)
    except Exception:
        return error(code=500, message="failed to create item", status_code=500)
    return success(data=None)


async def update_item(request: Request):
    try:
        item_id = parse_path_uint32(request.path_params.get("id", ""), "item id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = ItemUpdateRequest(**body)
    name = (req.name or "").strip()
    if not name:
        return error(code=400, message="name is required", status_code=400)
    it = admin.get_item_by_id(item_id)
    if it is None:
        return write_game_data_error(Exception("not found"), "item")
    data = dict(name=name, rarity=req.rarity, shop_id=req.shop_id, type=req.type, virtual_type=req.virtual_type)
    try:
        admin.update_item_record(item_id, data)
    except Exception:
        return error(code=500, message="failed to update item", status_code=500)
    return success(data=None)


async def delete_item(request: Request):
    try:
        item_id = parse_path_uint32(request.path_params.get("id", ""), "item id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        admin.delete_item_record(item_id)
    except Exception:
        return write_game_data_error(Exception("not found"), "item")
    return success(data=None)


# ---- Resources ----

async def list_resources(request: Request):
    try:
        meta = parse_pagination(request)
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        resources_page, total = admin.list_resources_page(meta.offset, meta.limit)
    except Exception:
        return error(code=500, message="failed to list resources", status_code=500)
    resources = [ResourceSummary(id=r['id'], item_id=r['item_id'], name=r['name']) for r in resources_page]
    payload = ResourceListResponse(resources=resources, meta=PaginationMeta(offset=meta.offset, limit=meta.limit, total=total))
    return success(data=payload)


async def resource_detail(request: Request):
    try:
        resource_id = parse_path_uint32(request.path_params.get("id", ""), "resource id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    r = admin.get_resource_by_id(resource_id)
    if r is None:
        return write_game_data_error(Exception("not found"), "resource")
    payload = ResourceSummary(id=r['id'], item_id=r['item_id'], name=r['name'])
    return success(data=payload)


async def create_resource(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = ResourceCreateRequest(**body)
    name = (req.name or "").strip()
    if req.id == 0:
        return error(code=400, message="id is required", status_code=400)
    if not name:
        return error(code=400, message="name is required", status_code=400)
    data = dict(id=req.id, item_id=req.item_id, name=name)
    try:
        admin.create_resource_record(data)
    except Exception:
        return error(code=500, message="failed to create resource", status_code=500)
    return success(data=None)


async def update_resource(request: Request):
    try:
        resource_id = parse_path_uint32(request.path_params.get("id", ""), "resource id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = ResourceUpdatePayload(**body)
    name = (req.name or "").strip()
    if not name:
        return error(code=400, message="name is required", status_code=400)
    r = admin.get_resource_by_id(resource_id)
    if r is None:
        return write_game_data_error(Exception("not found"), "resource")
    data = dict(name=name, item_id=req.item_id)
    try:
        admin.update_resource_record(resource_id, data)
    except Exception:
        return error(code=500, message="failed to update resource", status_code=500)
    return success(data=None)


async def delete_resource(request: Request):
    try:
        resource_id = parse_path_uint32(request.path_params.get("id", ""), "resource id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        admin.delete_resource_record(resource_id)
    except Exception:
        return write_game_data_error(Exception("not found"), "resource")
    return success(data=None)


# ---- Equipment ----

async def list_equipment(request: Request):
    try:
        meta = parse_pagination(request)
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        equipment, total = admin.list_equipment_page(meta.offset, meta.limit)
    except Exception:
        return error(code=500, message="failed to list equipment", status_code=500)
    results = [_equipment_payload_from_model(e) for e in equipment]
    payload = EquipmentListResponse(equipment=results, meta=PaginationMeta(offset=meta.offset, limit=meta.limit, total=total))
    return success(data=payload)


async def equipment_detail(request: Request):
    try:
        equip_id = parse_path_uint32(request.path_params.get("id", ""), "equipment id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    eq = admin.get_equipment_by_id(equip_id)
    if eq is None:
        return write_game_data_error(Exception("not found"), "equipment")
    payload = _equipment_payload_from_model(eq)
    return success(data=payload)


async def create_equipment(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = EquipmentPayload(**body)
    if req.id == 0:
        return error(code=400, message="id is required", status_code=400)
    data = _make_equipment_data(req)
    try:
        admin.create_equipment_record(data)
    except Exception:
        return error(code=500, message="failed to create equipment", status_code=500)
    return success(data=None)


async def update_equipment(request: Request):
    try:
        equip_id = parse_path_uint32(request.path_params.get("id", ""), "equipment id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = EquipmentPayload(**body)
    eq = admin.get_equipment_by_id(equip_id)
    if eq is None:
        return write_game_data_error(Exception("not found"), "equipment")
    data = _make_equipment_data(req)
    try:
        admin.update_equipment_record(equip_id, data)
    except Exception:
        return error(code=500, message="failed to update equipment", status_code=500)
    return success(data=None)


async def delete_equipment(request: Request):
    try:
        equip_id = parse_path_uint32(request.path_params.get("id", ""), "equipment id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        admin.delete_equipment_record(equip_id)
    except Exception:
        return write_game_data_error(Exception("not found"), "equipment")
    return success(data=None)


# ---- Weapons ----

async def list_weapons(request: Request):
    try:
        meta = parse_pagination(request)
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        weapons, total = admin.list_weapons_page(meta.offset, meta.limit)
    except Exception:
        return error(code=500, message="failed to list weapons", status_code=500)
    results = [_weapon_payload_from_model(w) for w in weapons]
    payload = WeaponListResponse(weapons=results, meta=PaginationMeta(offset=meta.offset, limit=meta.limit, total=total))
    return success(data=payload)


async def weapon_detail(request: Request):
    try:
        weapon_id = parse_path_uint32(request.path_params.get("id", ""), "weapon id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    w = admin.get_weapon_by_id(weapon_id)
    if w is None:
        return write_game_data_error(Exception("not found"), "weapon")
    payload = _weapon_payload_from_model(w)
    return success(data=payload)


async def create_weapon(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = WeaponPayload(**body)
    if req.id == 0:
        return error(code=400, message="id is required", status_code=400)
    data = _make_weapon_data(req)
    try:
        admin.create_weapon_record(data)
    except Exception:
        return error(code=500, message="failed to create weapon", status_code=500)
    return success(data=None)


async def update_weapon(request: Request):
    try:
        weapon_id = parse_path_uint32(request.path_params.get("id", ""), "weapon id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = WeaponPayload(**body)
    w = admin.get_weapon_by_id(weapon_id)
    if w is None:
        return write_game_data_error(Exception("not found"), "weapon")
    data = _make_weapon_data(req)
    try:
        admin.update_weapon_record(weapon_id, data)
    except Exception:
        return error(code=500, message="failed to update weapon", status_code=500)
    return success(data=None)


async def delete_weapon(request: Request):
    try:
        weapon_id = parse_path_uint32(request.path_params.get("id", ""), "weapon id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        admin.delete_weapon_record(weapon_id)
    except Exception:
        return write_game_data_error(Exception("not found"), "weapon")
    return success(data=None)


# ---- Skills ----

async def list_skills(request: Request):
    try:
        meta = parse_pagination(request)
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        skills, total = admin.list_skills_page(meta.offset, meta.limit)
    except Exception:
        return error(code=500, message="failed to list skills", status_code=500)
    results = [_skill_payload_from_model(s) for s in skills]
    payload = SkillListResponse(skills=results, meta=PaginationMeta(offset=meta.offset, limit=meta.limit, total=total))
    return success(data=payload)


async def skill_detail(request: Request):
    try:
        skill_id = parse_path_uint32(request.path_params.get("id", ""), "skill id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    s = admin.get_skill_by_id(skill_id)
    if s is None:
        return write_game_data_error(Exception("not found"), "skill")
    payload = _skill_payload_from_model(s)
    return success(data=payload)


async def create_skill(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = SkillPayload(**body)
    name = (req.name or "").strip()
    if req.id == 0:
        return error(code=400, message="id is required", status_code=400)
    if not name:
        return error(code=400, message="name is required", status_code=400)
    data = _make_skill_data(req)
    data['name'] = name
    try:
        admin.create_skill_record(data)
    except Exception:
        return error(code=500, message="failed to create skill", status_code=500)
    return success(data=None)


async def update_skill(request: Request):
    try:
        skill_id = parse_path_uint32(request.path_params.get("id", ""), "skill id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = SkillPayload(**body)
    name = (req.name or "").strip()
    if not name:
        return error(code=400, message="name is required", status_code=400)
    s = admin.get_skill_by_id(skill_id)
    if s is None:
        return write_game_data_error(Exception("not found"), "skill")
    data = _make_skill_data(req)
    data['name'] = name
    try:
        admin.update_skill_record(skill_id, data)
    except Exception:
        return error(code=500, message="failed to update skill", status_code=500)
    return success(data=None)


async def delete_skill(request: Request):
    try:
        skill_id = parse_path_uint32(request.path_params.get("id", ""), "skill id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        admin.delete_skill_record(skill_id)
    except Exception:
        return write_game_data_error(Exception("not found"), "skill")
    return success(data=None)


# ---- Buffs ----

async def list_buffs(request: Request):
    try:
        meta = parse_pagination(request)
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        buffs, total = admin.list_buffs_page(meta.offset, meta.limit)
    except Exception:
        return error(code=500, message="failed to list buffs", status_code=500)
    results = [_buff_payload_from_model(b) for b in buffs]
    payload = BuffListResponse(buffs=results, meta=PaginationMeta(offset=meta.offset, limit=meta.limit, total=total))
    return success(data=payload)


async def buff_detail(request: Request):
    try:
        buff_id = parse_path_uint32(request.path_params.get("id", ""), "buff id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    b = admin.get_buff_by_id(buff_id)
    if b is None:
        return write_game_data_error(Exception("not found"), "buff")
    payload = _buff_payload_from_model(b)
    return success(data=payload)


async def create_buff(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = BuffPayload(**body)
    name = (req.name or "").strip()
    benefit_type = (req.benefit_type or "").strip()
    if req.id == 0:
        return error(code=400, message="id is required", status_code=400)
    if not name:
        return error(code=400, message="name is required", status_code=400)
    if not benefit_type:
        return error(code=400, message="benefit_type is required", status_code=400)
    data = dict(id=req.id, name=name, description=(req.desc or "").strip(), max_time=req.max_time, benefit_type=benefit_type)
    try:
        admin.create_buff_record(data)
    except Exception:
        return error(code=500, message="failed to create buff", status_code=500)
    return success(data=None)


async def update_buff(request: Request):
    try:
        buff_id = parse_path_uint32(request.path_params.get("id", ""), "buff id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = BuffPayload(**body)
    name = (req.name or "").strip()
    benefit_type = (req.benefit_type or "").strip()
    if not name:
        return error(code=400, message="name is required", status_code=400)
    if not benefit_type:
        return error(code=400, message="benefit_type is required", status_code=400)
    b = admin.get_buff_by_id(buff_id)
    if b is None:
        return write_game_data_error(Exception("not found"), "buff")
    data = dict(name=name, description=(req.desc or "").strip(), max_time=req.max_time, benefit_type=benefit_type)
    try:
        admin.update_buff_record(buff_id, data)
    except Exception:
        return error(code=500, message="failed to update buff", status_code=500)
    return success(data=None)


async def delete_buff(request: Request):
    try:
        buff_id = parse_path_uint32(request.path_params.get("id", ""), "buff id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        admin.delete_buff_record(buff_id)
    except Exception:
        return write_game_data_error(Exception("not found"), "buff")
    return success(data=None)


# ---- Skins ----

async def list_skins(request: Request):
    try:
        meta = parse_pagination(request)
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        skins_page, total = admin.list_skins_page(meta.offset, meta.limit)
    except Exception:
        return error(code=500, message="failed to list skins", status_code=500)
    skins = [SkinSummary(id=s['id'], name=s['name'], ship_group=s['ship_group']) for s in skins_page]
    payload = SkinListResponse(skins=skins, meta=PaginationMeta(offset=meta.offset, limit=meta.limit, total=total))
    return success(data=payload)


async def skin_detail(request: Request):
    try:
        skin_id = parse_path_uint32(request.path_params.get("id", ""), "skin id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    s = admin.get_skin_by_id(skin_id)
    if s is None:
        return write_game_data_error(Exception("not found"), "skin")
    payload = _skin_payload_from_model(s)
    return success(data=payload)


async def create_skin(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = SkinPayload(**body)
    req.name = (req.name or "").strip()
    if req.id == 0:
        return error(code=400, message="id is required", status_code=400)
    if not req.name:
        return error(code=400, message="name is required", status_code=400)
    data = _make_skin_data(req)
    try:
        admin.create_skin_record(data)
    except Exception:
        return error(code=500, message="failed to create skin", status_code=500)
    return success(data=None)


async def update_skin(request: Request):
    try:
        skin_id = parse_path_uint32(request.path_params.get("id", ""), "skin id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = SkinPayload(**body)
    req.name = (req.name or "").strip()
    if not req.name:
        return error(code=400, message="name is required", status_code=400)
    s = admin.get_skin_by_id(skin_id)
    if s is None:
        return write_game_data_error(Exception("not found"), "skin")
    data = _make_skin_data(req)
    try:
        admin.update_skin_record(skin_id, data)
    except Exception:
        return error(code=500, message="failed to update skin", status_code=500)
    return success(data=None)


async def delete_skin(request: Request):
    try:
        skin_id = parse_path_uint32(request.path_params.get("id", ""), "skin id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        admin.delete_skin_record(skin_id)
    except Exception:
        return write_game_data_error(Exception("not found"), "skin")
    return success(data=None)


# ---- Skin Restrictions ----

async def list_skin_restrictions(request: Request):
    try:
        meta = parse_pagination(request)
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        restrictions, total = admin.list_global_skin_restrictions_page(meta.offset, meta.limit)
    except Exception:
        return error(code=500, message="failed to list skin restrictions", status_code=500)
    results = [SkinRestrictionPayload(skin_id=r['skin_id'], type=r['type']) for r in restrictions]
    payload = SkinRestrictionListResponse(
        skin_restrictions=results,
        meta=PaginationMeta(offset=meta.offset, limit=meta.limit, total=total),
    )
    return success(data=payload)


async def skin_restriction_detail(request: Request):
    try:
        skin_id = parse_path_uint32(request.path_params.get("skin_id", ""), "skin id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    r = admin.get_global_skin_restriction_by_skin_id(skin_id)
    if r is None:
        return write_game_data_error(Exception("not found"), "skin restriction")
    payload = SkinRestrictionPayload(skin_id=r['skin_id'], type=r['type'])
    return success(data=payload)


async def create_skin_restriction(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = SkinRestrictionCreateRequest(**body)
    if req.skin_id == 0:
        return error(code=400, message="skin_id is required", status_code=400)
    data = dict(skin_id=req.skin_id, type=req.type)
    try:
        admin.create_global_skin_restriction(data)
    except Exception:
        return error(code=500, message="failed to create skin restriction", status_code=500)
    return success(data=None)


async def update_skin_restriction(request: Request):
    try:
        skin_id = parse_path_uint32(request.path_params.get("skin_id", ""), "skin id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = SkinRestrictionUpdateRequest(**body)
    r = admin.get_global_skin_restriction_by_skin_id(skin_id)
    if r is None:
        return write_game_data_error(Exception("not found"), "skin restriction")
    try:
        admin.update_global_skin_restriction(skin_id, dict(type=req.type))
    except Exception:
        return error(code=500, message="failed to update skin restriction", status_code=500)
    return success(data=None)


async def delete_skin_restriction(request: Request):
    try:
        skin_id = parse_path_uint32(request.path_params.get("skin_id", ""), "skin id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        admin.delete_global_skin_restriction(skin_id)
    except Exception:
        return write_game_data_error(Exception("not found"), "skin restriction")
    return success(data=None)


# ---- Skin Restriction Windows ----

async def list_skin_restriction_windows(request: Request):
    try:
        meta = parse_pagination(request)
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        windows, total = admin.list_global_skin_restriction_windows_page(meta.offset, meta.limit)
    except Exception:
        return error(code=500, message="failed to list skin restriction windows", status_code=500)
    results = [SkinRestrictionWindowPayload(
        id=w['id'], skin_id=w['skin_id'], type=w['type'],
        start_time=w['start_time'], stop_time=w['stop_time'],
    ) for w in windows]
    payload = SkinRestrictionWindowListResponse(
        windows=results,
        meta=PaginationMeta(offset=meta.offset, limit=meta.limit, total=total),
    )
    return success(data=payload)


async def skin_restriction_window_detail(request: Request):
    try:
        window_id = parse_path_uint32(request.path_params.get("id", ""), "window id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    w = admin.get_global_skin_restriction_window_by_id(window_id)
    if w is None:
        return write_game_data_error(Exception("not found"), "skin restriction window")
    payload = SkinRestrictionWindowPayload(
        id=w['id'], skin_id=w['skin_id'], type=w['type'],
        start_time=w['start_time'], stop_time=w['stop_time'],
    )
    return success(data=payload)


async def create_skin_restriction_window(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = SkinRestrictionWindowCreateRequest(**body)
    if req.id == 0:
        return error(code=400, message="id is required", status_code=400)
    if req.skin_id == 0:
        return error(code=400, message="skin_id is required", status_code=400)
    data = dict(id=req.id, skin_id=req.skin_id, type=req.type, start_time=req.start_time, stop_time=req.stop_time)
    try:
        admin.create_global_skin_restriction_window(data)
    except Exception:
        return error(code=500, message="failed to create skin restriction window", status_code=500)
    return success(data=None)


async def update_skin_restriction_window(request: Request):
    try:
        window_id = parse_path_uint32(request.path_params.get("id", ""), "window id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = SkinRestrictionWindowUpdateRequest(**body)
    w = admin.get_global_skin_restriction_window_by_id(window_id)
    if w is None:
        return write_game_data_error(Exception("not found"), "skin restriction window")
    data = dict(skin_id=req.skin_id, type=req.type, start_time=req.start_time, stop_time=req.stop_time)
    try:
        admin.update_global_skin_restriction_window(window_id, data)
    except Exception:
        return error(code=500, message="failed to update skin restriction window", status_code=500)
    return success(data=None)


async def delete_skin_restriction_window(request: Request):
    try:
        window_id = parse_path_uint32(request.path_params.get("id", ""), "window id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        admin.delete_global_skin_restriction_window(window_id)
    except Exception:
        return write_game_data_error(Exception("not found"), "skin restriction window")
    return success(data=None)


# ---- Config Entries ----

async def list_config_entries(request: Request):
    category = (request.query_params.get("category") or "").strip()
    key = (request.query_params.get("key") or "").strip()
    try:
        entries = admin.list_config_entries_filtered(category, key)
    except Exception:
        return error(code=500, message="failed to list config entries", status_code=500)
    payload = ConfigEntryListResponse(entries=[_config_entry_payload_from_model(e) for e in entries])
    return success(data=payload)


async def config_entry_detail(request: Request):
    try:
        entry_id = parse_path_uint64(request.path_params.get("id", ""), "config entry id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    e = admin.get_config_entry_by_id(entry_id)
    if e is None:
        return write_game_data_error(Exception("not found"), "config entry")
    return success(data=_config_entry_payload_from_model(e))


async def create_config_entry(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = ConfigEntryMutationRequest(**body)
    category = (req.category or "").strip()
    key = (req.key or "").strip()
    if not category:
        return error(code=400, message="category is required", status_code=400)
    if not key:
        return error(code=400, message="key is required", status_code=400)
    if req.data is None or req.data.get("value") is None:
        return error(code=400, message="data is required", status_code=400)
    data = dict(category=category, key=key, data=req.data["value"])
    try:
        admin.create_config_entry_record(data)
    except Exception:
        return error(code=500, message="failed to create config entry", status_code=500)
    return success(data=None)


async def update_config_entry(request: Request):
    try:
        entry_id = parse_path_uint64(request.path_params.get("id", ""), "config entry id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error(code=400, message="invalid request", status_code=400)
    req = ConfigEntryMutationRequest(**body)
    category = (req.category or "").strip()
    key = (req.key or "").strip()
    if not category:
        return error(code=400, message="category is required", status_code=400)
    if not key:
        return error(code=400, message="key is required", status_code=400)
    if req.data is None or req.data.get("value") is None:
        return error(code=400, message="data is required", status_code=400)
    e = admin.get_config_entry_by_id(entry_id)
    if e is None:
        return write_game_data_error(Exception("not found"), "config entry")
    data = dict(category=category, key=key, data=req.data["value"])
    try:
        admin.update_config_entry_record(entry_id, data)
    except Exception:
        return error(code=500, message="failed to update config entry", status_code=500)
    return success(data=None)


async def delete_config_entry(request: Request):
    try:
        entry_id = parse_path_uint64(request.path_params.get("id", ""), "config entry id")
    except ValueError as e:
        return error(code=400, message=str(e), status_code=400)
    try:
        admin.delete_config_entry_by_id(entry_id)
    except Exception:
        return write_game_data_error(Exception("not found"), "config entry")
    return success(data=None)


# ---- Living Area Covers / Attire ----

async def list_living_area_covers():
    return await _list_config_entries_by_category("ShareCfg/livingarea_cover.json")


async def list_icon_frames():
    return await _list_config_entries_by_category("ShareCfg/item_data_frame.json")


async def list_chat_frames():
    return await _list_config_entries_by_category("ShareCfg/item_data_chat.json")


async def list_battle_ui_styles():
    return await _list_config_entries_by_category("ShareCfg/item_data_battleui.json")


async def _list_config_entries_by_category( category: str):
    try:
        entries = admin.list_config_entries_filtered(category, "")
    except Exception:
        return error(code=500, message="failed to load config entries", status_code=500)
    payload = ConfigEntryListResponse(entries=[_config_entry_payload_from_model(e) for e in entries])
    return success(data=payload)


# ---- Payload helpers ----

def _skin_payload_from_model(skin) -> SkinPayload:
    return SkinPayload(
        id=skin['id'], name=skin['name'], ship_group=skin['ship_group'],
        desc=skin['desc'], bg=skin['bg'], bg_sp=skin['bg_sp'], bgm=skin['bgm'],
        painting=skin['painting'], prefab=skin['prefab'],
        change_skin=_raw(skin['change_skin']), show_skin=skin['show_skin'],
        skeleton_skin=skin['skeleton_skin'],
        ship_l2d_id=_raw(skin['ship_l2d_id']), l2d_animations=_raw(skin['l2d_animations']),
        l2d_drag_rate=_raw(skin['l2d_drag_rate']), l2d_para_range=_raw(skin['l2d_para_range']),
        l2d_se=_raw(skin['l2d_se']), l2d_voice_calib=_raw(skin['l2d_voice_calib']),
        part_scale=skin['part_scale'], main_ui_fx=skin['main_ui_fx'],
        spine_offset=_raw(skin['spine_offset']), spine_profile=_raw(skin['spine_profile']),
        tag=_raw(skin['tag']), time=_raw(skin['time']), get_showing=_raw(skin['get_showing']),
        purchase_offset=_raw(skin['purchase_offset']), shop_offset=_raw(skin['shop_offset']),
        rarity_bg=skin['rarity_bg'], special_effects=_raw(skin['special_effects']),
        group_index=skin['group_index'], gyro=skin['gyro'], hand_id=skin['hand_id'],
        illustrator=skin['illustrator'], illustrator2=skin['illustrator2'],
        voice_actor=skin['voice_actor'], voice_actor2=skin['voice_actor2'],
        double_char=skin['double_char'], lip_smoothing=skin['lip_smoothing'],
        lip_sync_gain=skin['lip_sync_gain'], l2d_ignore_drag=skin['l2d_ignore_drag'],
        skin_type=skin['skin_type'], shop_id=skin['shop_id'], shop_type_id=skin['shop_type_id'],
        shop_dynamic_hx=skin['shop_dynamic_hx'], spine_action=_raw(skin['spine_action']),
        spine_use_live2d=skin['spine_use_live2d'],
        live2d_offset=_raw(skin['live2d_offset']), live2d_profile=_raw(skin['live2d_profile']),
        fx_container=_raw(skin['fx_container']), bound_bone=_raw(skin['bound_bone']),
        smoke=_raw(skin['smoke']),
    )


def _make_skin_data(payload: SkinPayload) -> dict:
    return dict(
        id=payload.id, name=payload.name, ship_group=payload.ship_group,
        desc=payload.desc, bg=payload.bg, bg_sp=payload.bg_sp, bgm=payload.bgm,
        painting=payload.painting, prefab=payload.prefab,
        change_skin=_raw_val(payload.change_skin), show_skin=payload.show_skin,
        skeleton_skin=payload.skeleton_skin,
        ship_l2d_id=_raw_val(payload.ship_l2d_id), l2d_animations=_raw_val(payload.l2d_animations),
        l2d_drag_rate=_raw_val(payload.l2d_drag_rate), l2d_para_range=_raw_val(payload.l2d_para_range),
        l2d_se=_raw_val(payload.l2d_se), l2d_voice_calib=_raw_val(payload.l2d_voice_calib),
        part_scale=payload.part_scale, main_ui_fx=payload.main_ui_fx,
        spine_offset=_raw_val(payload.spine_offset), spine_profile=_raw_val(payload.spine_profile),
        tag=_raw_val(payload.tag), time=_raw_val(payload.time), get_showing=_raw_val(payload.get_showing),
        purchase_offset=_raw_val(payload.purchase_offset), shop_offset=_raw_val(payload.shop_offset),
        rarity_bg=payload.rarity_bg, special_effects=_raw_val(payload.special_effects),
        group_index=payload.group_index, gyro=payload.gyro, hand_id=payload.hand_id,
        illustrator=payload.illustrator, illustrator2=payload.illustrator2,
        voice_actor=payload.voice_actor, voice_actor2=payload.voice_actor2,
        double_char=payload.double_char, lip_smoothing=payload.lip_smoothing,
        lip_sync_gain=payload.lip_sync_gain, l2d_ignore_drag=payload.l2d_ignore_drag,
        skin_type=payload.skin_type, shop_id=payload.shop_id, shop_type_id=payload.shop_type_id,
        shop_dynamic_hx=payload.shop_dynamic_hx, spine_action=_raw_val(payload.spine_action),
        spine_use_live2d=payload.spine_use_live2d,
        live2d_offset=_raw_val(payload.live2d_offset), live2d_profile=_raw_val(payload.live2d_profile),
        fx_container=_raw_val(payload.fx_container), bound_bone=_raw_val(payload.bound_bone),
        smoke=_raw_val(payload.smoke),
    )


def _equipment_payload_from_model(eq) -> EquipmentPayload:
    return EquipmentPayload(
        id=eq['id'], base=eq['base'], destroy_gold=eq['destroy_gold'],
        destroy_item=_raw(eq['destroy_item']), equip_limit=eq['equip_limit'],
        group=eq['group'], important=eq['important'], level=eq['level'],
        next=eq['next'], prev=eq['prev'], restore_gold=eq['restore_gold'],
        restore_item=_raw(eq['restore_item']),
        ship_type_forbidden=_raw(eq['ship_type_forbidden']),
        trans_use_gold=eq['trans_use_gold'], trans_use_item=_raw(eq['trans_use_item']),
        type=eq['type'], upgrade_formula_id=_raw(eq['upgrade_formula_id']),
    )


def _make_equipment_data(payload: EquipmentPayload) -> dict:
    return dict(
        id=payload.id, base=payload.base, destroy_gold=payload.destroy_gold,
        destroy_item=_raw_val(payload.destroy_item), equip_limit=payload.equip_limit,
        group=payload.group, important=payload.important, level=payload.level,
        next=payload.next, prev=payload.prev, restore_gold=payload.restore_gold,
        restore_item=_raw_val(payload.restore_item),
        ship_type_forbidden=_raw_val(payload.ship_type_forbidden),
        trans_use_gold=payload.trans_use_gold, trans_use_item=_raw_val(payload.trans_use_item),
        type=payload.type, upgrade_formula_id=_raw_val(payload.upgrade_formula_id),
    )


def _weapon_payload_from_model(w) -> WeaponPayload:
    return WeaponPayload(
        id=w['id'], action_index=w['action_index'], aim_type=w['aim_type'],
        angle=w['angle'], attack_attribute=w['attack_attribute'],
        attack_attribute_ratio=w['attack_attribute_ratio'],
        auto_aftercast=_raw(w['auto_aftercast']), axis_angle=w['axis_angle'],
        barrage_id=_raw(w['barrage_id']), bullet_id=_raw(w['bullet_id']),
        charge_param=_raw(w['charge_param']), corrected=w['corrected'],
        damage=w['damage'], effect_move=w['effect_move'], expose=w['expose'],
        fire_fx=w['fire_fx'], fire_fx_loop_type=w['fire_fx_loop_type'],
        fire_sfx=w['fire_sfx'], initial_over_heat=w['initial_over_heat'],
        min_range=w['min_range'], oxy_type=_raw(w['oxy_type']),
        precast_param=_raw(w['precast_param']), queue=w['queue'],
        range=w['range'], recover_time=_raw(w['recover_time']),
        reload_max=w['reload_max'], search_condition=_raw(w['search_condition']),
        search_type=w['search_type'], shake_screen=w['shake_screen'],
        spawn_bound=_raw(w['spawn_bound']), suppress=w['suppress'],
        torpedo_ammo=w['torpedo_ammo'], type=w['type'],
    )


def _make_weapon_data(payload: WeaponPayload) -> dict:
    return dict(
        id=payload.id, action_index=payload.action_index, aim_type=payload.aim_type,
        angle=payload.angle, attack_attribute=payload.attack_attribute,
        attack_attribute_ratio=payload.attack_attribute_ratio,
        auto_aftercast=_raw_val(payload.auto_aftercast), axis_angle=payload.axis_angle,
        barrage_id=_raw_val(payload.barrage_id), bullet_id=_raw_val(payload.bullet_id),
        charge_param=_raw_val(payload.charge_param), corrected=payload.corrected,
        damage=payload.damage, effect_move=payload.effect_move, expose=payload.expose,
        fire_fx=payload.fire_fx, fire_fx_loop_type=payload.fire_fx_loop_type,
        fire_sfx=payload.fire_sfx, initial_over_heat=payload.initial_over_heat,
        min_range=payload.min_range, oxy_type=_raw_val(payload.oxy_type),
        precast_param=_raw_val(payload.precast_param), queue=payload.queue,
        range=payload.range, recover_time=_raw_val(payload.recover_time),
        reload_max=payload.reload_max, search_condition=_raw_val(payload.search_condition),
        search_type=payload.search_type, shake_screen=payload.shake_screen,
        spawn_bound=_raw_val(payload.spawn_bound), suppress=payload.suppress,
        torpedo_ammo=payload.torpedo_ammo, type=payload.type,
    )


def _skill_payload_from_model(s) -> SkillPayload:
    return SkillPayload(
        id=s['id'], name=s['name'], desc=s['desc'], cd=s['cd'],
        painting=_raw(s['painting']), picture=s['picture'],
        ani_effect=_raw(s['ani_effect']), ui_effect=s['ui_effect'],
        effect_list=_raw(s['effect_list']),
    )


def _make_skill_data(payload: SkillPayload) -> dict:
    return dict(
        id=payload.id, desc=payload.desc, cd=payload.cd,
        painting=_raw_val(payload.painting), picture=payload.picture,
        ani_effect=_raw_val(payload.ani_effect), ui_effect=payload.ui_effect,
        effect_list=_raw_val(payload.effect_list),
    )


def _buff_payload_from_model(b) -> BuffPayload:
    return BuffPayload(
        id=b['id'], name=b['name'], desc=b['description'],
        max_time=b['max_time'], benefit_type=b['benefit_type'],
    )


def _config_entry_payload_from_model(e) -> ConfigEntryPayload:
    return ConfigEntryPayload(
        id=e['id'], category=e['category'], key=e['key'],
        data=RawJSON(value=e['data']),
    )


def _raw(val):
    return RawJSON(value=val)


def _raw_val(raw):
    if raw is None:
        return None
    if hasattr(raw, "value"):
        return raw.value
    if isinstance(raw, dict):
        return raw.get("value")
    return raw
