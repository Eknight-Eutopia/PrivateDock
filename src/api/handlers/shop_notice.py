from fastapi import Request
from src.api.response.response import ok as success, error
from src.api.types import *
from src.orm import (
    count_shop_offers, list_shop_offers, get_shop_offer, create_shop_offer, update_shop_offer, delete_shop_offer,
    notice_get, notice_create, notice_update, notice_delete,
    notices_list, notices_active, notices_count,
    arena_shop_get, arena_shop_upsert,
    medal_shop_get, medal_shop_upsert, medal_shop_goods_list, medal_shop_good_create, medal_shop_good_update, medal_shop_good_delete,
    guild_shop_get, guild_shop_upsert, guild_shop_goods_list, guild_shop_good_create, guild_shop_good_update, guild_shop_good_delete,
    mini_game_shop_get, mini_game_shop_upsert, mini_game_shop_goods_list, mini_game_shop_good_create, mini_game_shop_good_update, mini_game_shop_good_delete,
    shopping_street_state_get, shopping_street_state_upsert, shopping_street_goods_list, shopping_street_good_upsert, shopping_street_good_delete,
)
from .players import parse_pagination, parse_path_uint32
from ..types.player import ShoppingStreetResponse, ShoppingStreetState, ShoppingStreetGood, \
    ShoppingStreetGoodsResponse, \
    ShoppingStreetUpdateRequest, ArenaShopUpdateRequest, \
    MedalShopResponse, MedalShopState, MedalShopItem, MedalShopGoodsResponse, \
    MedalShopUpdateRequest, GuildShopResponse, GuildShopState, GuildShopGood, \
    GuildShopGoodsResponse, GuildShopUpdateRequest, \
    MiniGameShopResponse, MiniGameShopState, MiniGameShopGood, \
    MiniGameShopGoodsResponse, MiniGameShopUpdateRequest
from ...orm.medal_shop_good import MedalShopGood


async def list_offers(request: Request):
    try:
        pagination = parse_pagination(request)
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    genre = request.query_params.get("genre", "")
    if genre and genre.isdigit():
        genre_val = str(int(genre))
    elif genre:
        genre_val = genre
    else:
        genre_val = ""
    total = await count_shop_offers(genre_val)
    rows = await list_shop_offers(pagination.offset, pagination.limit, genre_val)
    offers = [ShopOfferSummary(**r) for r in rows]
    payload = ShopOfferListResponse(
        offers=offers,
        meta=PaginationMeta(offset=pagination.offset, limit=pagination.limit, total=total),
    )
    return success(data=payload.dict())


async def create_offer(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = ShopOfferSummary(**body)
    await create_shop_offer(req.dict())
    return success(data=None)


async def update_offer(request: Request):
    try:
        offer_id = parse_path_uint32(request.path_params.get("id", ""), "offer id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    existing = await get_shop_offer(offer_id)
    if existing is None:
        return error("not_found", "shop offer not found", status_code=404)
    await update_shop_offer(offer_id, body)
    return success(data=None)


async def delete_offer(request: Request):
    try:
        offer_id = parse_path_uint32(request.path_params.get("id", ""), "offer id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    if not await delete_shop_offer(offer_id):
        return error("not_found", "shop offer not found", status_code=404)
    return success(data=None)


async def list_notices(request: Request):
    try:
        pagination = parse_pagination(request)
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    total = await notices_count()
    rows = await notices_list(pagination.offset, pagination.limit)
    notices = [NoticeSummary(**r) for r in rows]
    payload = NoticeListResponse(
        notices=notices,
        meta=PaginationMeta(offset=pagination.offset, limit=pagination.limit, total=total),
    )
    return success(data=payload.dict())


async def get_notice(request: Request):
    try:
        notice_id = parse_path_uint32(request.path_params.get("id", ""), "notice id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    r = await notice_get(notice_id)
    if r is None:
        return error("not_found", "notice not found", status_code=404)
    return success(data=NoticeSummary(**r).dict())


async def create_notice(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = NoticeSummary(**body)
    if not req.title.strip() or not req.content.strip():
        return error("bad_request", "title and content are required", status_code=400)
    await notice_create(req.dict())
    return success(data=None)


async def update_notice(request: Request):
    try:
        notice_id = parse_path_uint32(request.path_params.get("id", ""), "notice id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    existing = await notice_get(notice_id)
    if existing is None:
        return error("not_found", "notice not found", status_code=404)
    await notice_update(notice_id, body)
    return success(data=None)


async def delete_notice(request: Request):
    try:
        notice_id = parse_path_uint32(request.path_params.get("id", ""), "notice id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    if not await notice_delete(notice_id):
        return error("not_found", "notice not found", status_code=404)
    return success(data=None)


async def shopping_street_list(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid player id", status_code=400)
    state = await shopping_street_state_get(commander_id)
    if state is None:
        payload = ShoppingStreetResponse(
            state=ShoppingStreetState(level=0, next_flash_time=0, level_up_time=0, flash_count=0, last_refreshed_at=0),
            goods=[],
        )
        return success(data=payload.dict())
    goods = await shopping_street_goods_list(commander_id)
    payload = ShoppingStreetResponse(
        state=ShoppingStreetState(
            level=state.get("level", 0),
            next_flash_time=state.get("next_flash_time", 0),
            level_up_time=state.get("level_up_time", 0),
            flash_count=state.get("flash_count", 0),
            last_refreshed_at=state.get("last_refreshed_at", 0),
        ),
        goods=[ShoppingStreetGood(goods_id=g["goods_id"], discount=g["discount"], buy_count=g["buy_count"]) for g in goods],
    )
    return success(data=payload.dict())


async def update_shopping_street(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid player id", status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = ShoppingStreetUpdateRequest(**body)
    state = await shopping_street_state_get(commander_id)
    if state is None:
        state = {"level": 0, "next_flash_time": 0, "level_up_time": 0, "flash_count": 0}
    await shopping_street_state_upsert(
        commander_id,
        level=state["level"],
        next_flash_time=state["next_flash_time"],
        level_up_time=state["level_up_time"],
        flash_count=req.daily_refresh or 0,
    )
    for g in (req.goods or []):
        await shopping_street_good_upsert(commander_id, g.get("id", 0), g.get("discount", 0), g.get("buy_count", 0))
    return success(data=None)


async def refresh_shopping_street(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid player id", status_code=400)
    state = await shopping_street_state_get(commander_id)
    flash_count = (state["flash_count"] + 1) if state else 1
    await shopping_street_state_upsert(commander_id, level=0, next_flash_time=0, level_up_time=0, flash_count=flash_count)
    return success(data=None)


async def shopping_street_goods_list_route(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid player id", status_code=400)
    goods = await shopping_street_goods_list(commander_id)
    payload = ShoppingStreetGoodsResponse(
        goods=[ShoppingStreetGood(goods_id=g["goods_id"], discount=g["discount"], buy_count=g["buy_count"]) for g in goods]
    )
    return success(data=payload.dict())


async def replace_shopping_street_goods(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid player id", status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    if not isinstance(body, list):
        return error("bad_request", "expected array of goods", status_code=400)
    existing_goods = await shopping_street_goods_list(commander_id)
    for g in existing_goods:
        await shopping_street_good_delete(commander_id, g["goods_id"])
    for g in body:
        await shopping_street_good_upsert(commander_id, g.get("id", 0), g.get("discount", 0), g.get("buy_count", 0))
    return success(data=None)


async def create_shopping_street_good(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid player id", status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    await shopping_street_good_upsert(commander_id, body.get("id", 0), body.get("discount", 0), body.get("buy_count", 0))
    return success(data=None)


async def patch_shopping_street_good(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
        goods_id_s = request.path_params.get("goods_id", "")
        goods_id = int(goods_id_s)
    except (ValueError, TypeError):
        return error("bad_request", "invalid id", status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    goods = await shopping_street_goods_list(commander_id)
    found = any(g["goods_id"] == goods_id for g in goods)
    if not found:
        return error("not_found", "good not found", status_code=404)
    discount = body.get("discount", 0)
    buy_count = body.get("buy_count", 0)
    await shopping_street_good_upsert(commander_id, goods_id, discount, buy_count)
    return success(data=None)


async def delete_shopping_street_good(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
        goods_id = int(request.path_params.get("goods_id", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid id", status_code=400)
    if not await shopping_street_good_delete(commander_id, goods_id):
        return error("not_found", "good not found", status_code=404)
    return success(data=None)


async def arena_shop_get_route(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid player id", status_code=400)
    r = await arena_shop_get(commander_id)
    if r is None:
        return success(data=dict(currency=0, goods=[], refresh_count=0))
    return success(data=dict(
        currency=r.get("flash_count", 0),
        goods=[],
        refresh_count=r.get("next_flash_time", 0),
    ))


async def arena_shop_update_route(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid player id", status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = ArenaShopUpdateRequest(**body)
    await arena_shop_upsert(commander_id, req.currency or 0, 0, req.refresh_count or 0)
    return success(data=None)


async def medal_shop_get_route(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid player id", status_code=400)
    r = await medal_shop_get(commander_id)
    goods = await medal_shop_goods_list(commander_id)
    if r is None:
        payload = MedalShopResponse(
            state=MedalShopState(next_refresh_time=0),
            items=[],
        )
        return success(data=payload.dict())
    payload = MedalShopResponse(
        state=MedalShopState(next_refresh_time=r.get("next_refresh_time", 0)),
        items=[MedalShopItem(id=g["goods_id"], count=g["count"], index=g["index"]) for g in goods],
    )
    return success(data=payload.dict())


async def medal_shop_update_route(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid player id", status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = MedalShopUpdateRequest(**body)
    await medal_shop_upsert(commander_id, req.refresh_count or 0)
    for g in (req.goods or []):
        await medal_shop_good_create(commander_id, g.get("index", 0), g.get("goods_id", 0), g.get("count", 0))
    return success(data=None)


async def medal_shop_goods_list_route(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid player id", status_code=400)
    goods = await medal_shop_goods_list(commander_id)
    payload = MedalShopGoodsResponse(
        goods=[MedalShopGood(index=g["index"], goods_id=g["goods_id"], count=g["count"]) for g in goods]
    )
    return success(data=payload.dict())


async def create_medal_shop_good(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid player id", status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    await medal_shop_good_create(commander_id, body.get("index", 0), body.get("goods_id", 0), body.get("count", 0))
    return success(data=None)


async def patch_medal_shop_good(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
        index = int(request.path_params.get("index", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid id", status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    ok = await medal_shop_good_update(commander_id, index, body.get("goods_id"), body.get("count"))
    if not ok:
        return error("not_found", "good not found", status_code=404)
    return success(data=None)


async def delete_medal_shop_good(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
        index = int(request.path_params.get("index", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid id", status_code=400)
    if not await medal_shop_good_delete(commander_id, index):
        return error("not_found", "good not found", status_code=404)
    return success(data=None)


async def guild_shop_get_route(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid player id", status_code=400)
    r = await guild_shop_get(commander_id)
    goods = await guild_shop_goods_list(commander_id)
    if r is None:
        payload = GuildShopResponse(
            state=GuildShopState(refresh_count=0, next_refresh_time=0),
            goods=[],
        )
        return success(data=payload.dict())
    payload = GuildShopResponse(
        state=GuildShopState(
            refresh_count=r.get("refresh_count", 0),
            next_refresh_time=r.get("next_refresh_time", 0),
        ),
        goods=[GuildShopGood(index=g["index"], goods_id=g["goods_id"], count=g["count"]) for g in goods],
    )
    return success(data=payload.dict())


async def guild_shop_update_route(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid player id", status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = GuildShopUpdateRequest(**body)
    await guild_shop_upsert(commander_id, req.currency or 0, req.refresh_count or 0)
    for g in (req.goods or []):
        await guild_shop_good_create(commander_id, g.get("index", 0), g.get("goods_id", 0), g.get("count", 0))
    return success(data=None)


async def guild_shop_goods_list_route(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid player id", status_code=400)
    goods = await guild_shop_goods_list(commander_id)
    payload = GuildShopGoodsResponse(
        goods=[GuildShopGood(index=g["index"], goods_id=g["goods_id"], count=g["count"]) for g in goods]
    )
    return success(data=payload.dict())


async def create_guild_shop_good(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid player id", status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    await guild_shop_good_create(commander_id, body.get("index", 0), body.get("goods_id", 0), body.get("count", 0))
    return success(data=None)


async def patch_guild_shop_good(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
        index = int(request.path_params.get("index", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid id", status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    ok = await guild_shop_good_update(commander_id, index, body.get("goods_id"), body.get("count"))
    if not ok:
        return error("not_found", "good not found", status_code=404)
    return success(data=None)


async def delete_guild_shop_good(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
        index = int(request.path_params.get("index", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid id", status_code=400)
    if not await guild_shop_good_delete(commander_id, index):
        return error("not_found", "good not found", status_code=404)
    return success(data=None)


async def mini_game_shop_get_route(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid player id", status_code=400)
    r = await mini_game_shop_get(commander_id)
    goods = await mini_game_shop_goods_list(commander_id)
    if r is None:
        payload = MiniGameShopResponse(
            state=MiniGameShopState(next_refresh_time=0),
            goods=[],
        )
        return success(data=payload.dict())
    payload = MiniGameShopResponse(
        state=MiniGameShopState(next_refresh_time=r.get("next_refresh_time", 0)),
        goods=[MiniGameShopGood(goods_id=g["goods_id"], count=g["count"]) for g in goods],
    )
    return success(data=payload.dict())


async def mini_game_shop_update_route(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid player id", status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = MiniGameShopUpdateRequest(**body)
    await mini_game_shop_upsert(commander_id, req.refresh_count or 0)
    for g in (req.goods or []):
        await mini_game_shop_good_create(commander_id, g.get("goods_id", 0), g.get("count", 0))
    return success(data=None)


async def mini_game_shop_goods_list_route(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid player id", status_code=400)
    goods = await mini_game_shop_goods_list(commander_id)
    payload = MiniGameShopGoodsResponse(
        goods=[MiniGameShopGood(goods_id=g["goods_id"], count=g["count"]) for g in goods]
    )
    return success(data=payload.dict())


async def create_mini_game_shop_good(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid player id", status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    await mini_game_shop_good_create(commander_id, body.get("goods_id", 0), body.get("count", 0))
    return success(data=None)


async def patch_mini_game_shop_good(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
        goods_id = int(request.path_params.get("goods_id", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid id", status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    ok = await mini_game_shop_good_update(commander_id, goods_id, body.get("count"))
    if not ok:
        return error("not_found", "good not found", status_code=404)
    return success(data=None)


async def delete_mini_game_shop_good(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
        goods_id = int(request.path_params.get("goods_id", ""))
    except (ValueError, TypeError):
        return error("bad_request", "invalid id", status_code=400)
    if not await mini_game_shop_good_delete(commander_id, goods_id):
        return error("not_found", "good not found", status_code=404)
    return success(data=None)


def _fmt_dt(value):
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


async def active_notices():
    rows = await notices_active()
    return success(data=[n.dict() for n in [NoticeSummary(**r) for r in rows]])
