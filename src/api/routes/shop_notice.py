from fastapi import APIRouter, Request

from src.api.handlers.shop_notice import (
    list_offers, create_offer, update_offer, delete_offer,
    list_notices, get_notice, create_notice, update_notice, delete_notice,
    active_notices,
)

shop_router = router = APIRouter(prefix="/api/v1/shop", tags=["shop"])
notice_router = APIRouter(prefix="/api/v1/notices", tags=["notices"])


@shop_router.get("/offers")
async def list_offers_route(req: Request):
    return await list_offers(req)


@shop_router.post("/offers")
async def create_offer_route(req: Request):
    return await create_offer(req)


@shop_router.patch("/offers/{id}")
async def update_offer_route(req: Request):
    return await update_offer(req)


@shop_router.delete("/offers/{id}")
async def delete_offer_route(req: Request):
    return await delete_offer(req)


@shop_router.get("/shopping-street/{player_id}")
async def get_shopping_street_route(req: Request):
    from src.api.handlers.shop_notice import shopping_street_list
    return await shopping_street_list(req)


@shop_router.put("/shopping-street/{player_id}")
async def update_shopping_street_route(req: Request):
    from src.api.handlers.shop_notice import update_shopping_street
    return await update_shopping_street(req)


@shop_router.post("/shopping-street/{player_id}/refresh")
async def refresh_shopping_street_route(req: Request):
    from src.api.handlers.shop_notice import refresh_shopping_street
    return await refresh_shopping_street(req)


@shop_router.get("/shopping-street/{player_id}/goods")
async def list_shopping_street_goods_route(req: Request):
    from src.api.handlers.shop_notice import shopping_street_goods_list_route as fn
    return await fn(req)


@shop_router.put("/shopping-street/{player_id}/goods")
async def replace_shopping_street_goods_route(req: Request):
    from src.api.handlers.shop_notice import replace_shopping_street_goods
    return await replace_shopping_street_goods(req)


@shop_router.post("/shopping-street/{player_id}/goods")
async def create_shopping_street_good_route(req: Request):
    from src.api.handlers.shop_notice import create_shopping_street_good
    return await create_shopping_street_good(req)


@shop_router.patch("/shopping-street/{player_id}/goods/{goods_id}")
async def patch_shopping_street_good_route(req: Request):
    from src.api.handlers.shop_notice import patch_shopping_street_good
    return await patch_shopping_street_good(req)


@shop_router.delete("/shopping-street/{player_id}/goods/{goods_id}")
async def delete_shopping_street_good_route(req: Request):
    from src.api.handlers.shop_notice import delete_shopping_street_good
    return await delete_shopping_street_good(req)


@shop_router.get("/arena/{player_id}")
async def get_arena_shop_route(req: Request):
    from src.api.handlers.shop_notice import arena_shop_get_route as fn
    return await fn(req)


@shop_router.put("/arena/{player_id}")
async def update_arena_shop_route(req: Request):
    from src.api.handlers.shop_notice import arena_shop_update_route as fn
    return await fn(req)


@shop_router.get("/medal/{player_id}")
async def get_medal_shop_route(req: Request):
    from src.api.handlers.shop_notice import medal_shop_get_route as fn
    return await fn(req)


@shop_router.put("/medal/{player_id}")
async def update_medal_shop_route(req: Request):
    from src.api.handlers.shop_notice import medal_shop_update_route as fn
    return await fn(req)


@shop_router.get("/medal/{player_id}/goods")
async def list_medal_shop_goods_route(req: Request):
    from src.api.handlers.shop_notice import medal_shop_goods_list_route as fn
    return await fn(req)


@shop_router.post("/medal/{player_id}/goods")
async def create_medal_shop_good_route(req: Request):
    from src.api.handlers.shop_notice import create_medal_shop_good as fn
    return await fn(req)


@shop_router.patch("/medal/{player_id}/goods/{index}")
async def patch_medal_shop_good_route(req: Request):
    from src.api.handlers.shop_notice import patch_medal_shop_good as fn
    return await fn(req)


@shop_router.delete("/medal/{player_id}/goods/{index}")
async def delete_medal_shop_good_route(req: Request):
    from src.api.handlers.shop_notice import delete_medal_shop_good as fn
    return await fn(req)


@shop_router.get("/guild/{player_id}")
async def get_guild_shop_route(req: Request):
    from src.api.handlers.shop_notice import guild_shop_get_route as fn
    return await fn(req)


@shop_router.put("/guild/{player_id}")
async def update_guild_shop_route(req: Request):
    from src.api.handlers.shop_notice import guild_shop_update_route as fn
    return await fn(req)


@shop_router.get("/guild/{player_id}/goods")
async def list_guild_shop_goods_route(req: Request):
    from src.api.handlers.shop_notice import guild_shop_goods_list_route as fn
    return await fn(req)


@shop_router.post("/guild/{player_id}/goods")
async def create_guild_shop_good_route(req: Request):
    from src.api.handlers.shop_notice import create_guild_shop_good as fn
    return await fn(req)


@shop_router.patch("/guild/{player_id}/goods/{index}")
async def patch_guild_shop_good_route(req: Request):
    from src.api.handlers.shop_notice import patch_guild_shop_good as fn
    return await fn(req)


@shop_router.delete("/guild/{player_id}/goods/{index}")
async def delete_guild_shop_good_route(req: Request):
    from src.api.handlers.shop_notice import delete_guild_shop_good as fn
    return await fn(req)


@shop_router.get("/mini-game/{player_id}")
async def get_mini_game_shop_route(req: Request):
    from src.api.handlers.shop_notice import mini_game_shop_get_route as fn
    return await fn(req)


@shop_router.put("/mini-game/{player_id}")
async def update_mini_game_shop_route(req: Request):
    from src.api.handlers.shop_notice import mini_game_shop_update_route as fn
    return await fn(req)


@shop_router.get("/mini-game/{player_id}/goods")
async def list_mini_game_shop_goods_route(req: Request):
    from src.api.handlers.shop_notice import mini_game_shop_goods_list_route as fn
    return await fn(req)


@shop_router.post("/mini-game/{player_id}/goods")
async def create_mini_game_shop_good_route(req: Request):
    from src.api.handlers.shop_notice import create_mini_game_shop_good as fn
    return await fn(req)


@shop_router.patch("/mini-game/{player_id}/goods/{goods_id}")
async def patch_mini_game_shop_good_route(req: Request):
    from src.api.handlers.shop_notice import patch_mini_game_shop_good as fn
    return await fn(req)


@shop_router.delete("/mini-game/{player_id}/goods/{goods_id}")
async def delete_mini_game_shop_good_route(req: Request):
    from src.api.handlers.shop_notice import delete_mini_game_shop_good as fn
    return await fn(req)


@notice_router.get("")
async def list_notices_route(req: Request):
    return await list_notices(req)


@notice_router.post("")
async def create_notice_route(req: Request):
    return await create_notice(req)


@notice_router.get("/active")
async def active_notices_route():
    return await active_notices()


@notice_router.get("/{notice_id}")
async def get_notice_route(req: Request):
    return await get_notice(req)


@notice_router.put("/{notice_id}")
async def update_notice_route(req: Request):
    return await update_notice(req)


@notice_router.delete("/{notice_id}")
async def delete_notice_route(req: Request):
    return await delete_notice(req)
