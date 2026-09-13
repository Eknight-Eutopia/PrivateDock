from fastapi import APIRouter, Request

from src.api.handlers.game_data import (
    list_ships, ship_detail, create_ship, update_ship, delete_ship,
    list_ship_types, ship_type_detail, create_ship_type, update_ship_type, delete_ship_type,
    list_rarities, rarity_detail, create_rarity, update_rarity, delete_rarity,
    list_items, create_item, update_item, delete_item,
    list_resources, create_resource, update_resource, delete_resource,
    list_skins, list_equipment, list_skills, list_weapons, list_buffs,
    list_config_entries, create_config_entry, config_entry_detail, update_config_entry, delete_config_entry,
)

router = APIRouter(prefix="/api/v1", tags=["game_data"])


@router.get("/ships")
async def list_ships_route(request: Request):
    return await list_ships(request)


@router.get("/ships/{id}")
async def get_ship_route(request: Request):
    return await ship_detail(request)


@router.post("/ships")
async def create_ship_route(request: Request):
    return await create_ship(request)


@router.put("/ships/{id}")
async def update_ship_route(request: Request):
    return await update_ship(request)


@router.delete("/ships/{id}")
async def delete_ship_route(request: Request):
    return await delete_ship(request)


@router.get("/ship-types")
async def list_ship_types_route(request: Request):
    return await list_ship_types(request)


@router.get("/ship-types/{id}")
async def get_ship_type_route(request: Request):
    return await ship_type_detail(request)


@router.post("/ship-types")
async def create_ship_type_route(request: Request):
    return await create_ship_type(request)


@router.put("/ship-types/{id}")
async def update_ship_type_route(request: Request):
    return await update_ship_type(request)


@router.delete("/ship-types/{id}")
async def delete_ship_type_route(request: Request):
    return await delete_ship_type(request)


@router.get("/rarities")
async def list_rarities_route(request: Request):
    return await list_rarities(request)


@router.get("/rarities/{id}")
async def get_rarity_route(request: Request):
    return await rarity_detail(request)


@router.post("/rarities")
async def create_rarity_route(request: Request):
    return await create_rarity(request)


@router.put("/rarities/{id}")
async def update_rarity_route(request: Request):
    return await update_rarity(request)


@router.delete("/rarities/{id}")
async def delete_rarity_route(request: Request):
    return await delete_rarity(request)


@router.get("/items")
async def list_items_route(request: Request):
    return await list_items(request)


@router.post("/items")
async def create_item_route(request: Request):
    return await create_item(request)


@router.put("/items/{id}")
async def update_item_route(request: Request):
    return await update_item(request)


@router.delete("/items/{id}")
async def delete_item_route(request: Request):
    return await delete_item(request)


@router.get("/resources")
async def list_resources_route(request: Request):
    return await list_resources(request)


@router.post("/resources")
async def create_resource_route(request: Request):
    return await create_resource(request)


@router.put("/resources/{id}")
async def update_resource_route(request: Request):
    return await update_resource(request)


@router.delete("/resources/{id}")
async def delete_resource_route(request: Request):
    return await delete_resource(request)


@router.get("/skins")
async def list_skins_route(request: Request):
    return await list_skins(request)


@router.get("/equipment")
async def list_equipment_route(request: Request):
    return await list_equipment(request)


@router.get("/skills")
async def list_skills_route(request: Request):
    return await list_skills(request)


@router.get("/weapons")
async def list_weapons_route(request: Request):
    return await list_weapons(request)


@router.get("/buffs")
async def list_buffs_route(request: Request):
    return await list_buffs(request)


@router.get("/config-entries")
async def list_config_entries_route(request: Request):
    return await list_config_entries(request)


@router.post("/config-entries")
async def create_config_entry_route(request: Request):
    return await create_config_entry(request)


@router.get("/config-entries/{id}")
async def get_config_entry_route(request: Request):
    return await config_entry_detail(request)


@router.put("/config-entries/{id}")
async def update_config_entry_route(request: Request):
    return await update_config_entry(request)


@router.delete("/config-entries/{id}")
async def delete_config_entry_route(request: Request):
    return await delete_config_entry(request)
