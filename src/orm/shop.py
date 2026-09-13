from typing import Any, Optional
from sqlalchemy import select, text

from src.db.session import get_sync_session, get_session
from src.orm.arena_shop_state import ArenaShopState
from src.orm.commander_medal_display import CommanderMedalDisplay
from src.orm.guild_shop_good import GuildShopGood
from src.orm.guild_shop_state import GuildShopState
from src.orm.medal_shop_good import MedalShopGood
from src.orm.medal_shop_state import MedalShopState
from src.orm.mini_game_shop_good import MiniGameShopGood
from src.orm.mini_game_shop_state import MiniGameShopState
from src.orm.month_shop import MonthShopPurchase


def _sync_list_month_shop_purchase_counts(commander_id: int, month: int) -> dict[int, int]:
    with get_sync_session() as session:
        rows = session.execute(
            select(MonthShopPurchase).where(
                MonthShopPurchase.commander_id == commander_id,
                MonthShopPurchase.month == month,
            )
        ).scalars().all()
        return {r.goods_id: r.buy_count for r in rows}


def _sync_set_commander_medal_display(commander_id: int, medal_ids: list[int]):
    with get_sync_session() as session:
        existing = session.execute(
            select(CommanderMedalDisplay).where(CommanderMedalDisplay.commander_id == commander_id)
        ).scalars().all()
        for e in existing:
            session.delete(e)
        for i, mid in enumerate(medal_ids):
            session.add(CommanderMedalDisplay(commander_id=commander_id, position=i, medal_id=mid))
        session.commit()


# ── Arena Shop async ──

async def arena_shop_get(commander_id: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        r = await session.get(ArenaShopState, commander_id)
        if r is None:
            return None
        return {
            "commander_id": r.commander_id,
            "flash_count": r.flash_count,
            "last_refresh_time": r.last_refresh_time,
            "next_flash_time": r.next_flash_time,
        }


async def arena_shop_upsert(commander_id: int, flash_count: int, last_refresh_time: int, next_flash_time: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("""
                INSERT INTO arena_shop_states (commander_id, flash_count, last_refresh_time, next_flash_time)
                VALUES (:cid, :fc, :lrt, :nft)
                ON CONFLICT (commander_id) DO UPDATE SET
                    flash_count = EXCLUDED.flash_count,
                    last_refresh_time = EXCLUDED.last_refresh_time,
                    next_flash_time = EXCLUDED.next_flash_time
            """),
            {"cid": commander_id, "fc": flash_count, "lrt": last_refresh_time, "nft": next_flash_time},
        )
        await session.commit()


# ── Medal Shop async ──

async def medal_shop_get(commander_id: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        r = await session.get(MedalShopState, commander_id)
        if r is None:
            return None
        return {"commander_id": r.commander_id, "next_refresh_time": r.next_refresh_time}


async def medal_shop_upsert(commander_id: int, next_refresh_time: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("""
                INSERT INTO medal_shop_states (commander_id, next_refresh_time)
                VALUES (:cid, :nrt)
                ON CONFLICT (commander_id) DO UPDATE SET
                    next_refresh_time = EXCLUDED.next_refresh_time
            """),
            {"cid": commander_id, "nrt": next_refresh_time},
        )
        await session.commit()


async def medal_shop_goods_list(commander_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            select(MedalShopGood).where(MedalShopGood.commander_id == commander_id).order_by(MedalShopGood.index)
        )
        return [
            {"commander_id": r.commander_id, "index": r.index, "goods_id": r.goods_id, "count": r.count}
            for r in result.scalars().all()
        ]


async def medal_shop_good_create(commander_id: int, index: int, goods_id: int, count: int) -> None:
    async with get_session() as session:
        session.add(MedalShopGood(commander_id=commander_id, index=index, goods_id=goods_id, count=count))
        await session.commit()


async def medal_shop_good_update(commander_id: int, index: int, goods_id: int = None, count: int = None) -> None:
    async with get_session() as session:
        r = await session.get(MedalShopGood, (commander_id, index))
        if r is None:
            return
        if goods_id is not None:
            r.goods_id = goods_id
        if count is not None:
            r.count = count
        await session.commit()


async def medal_shop_good_delete(commander_id: int, index: int) -> bool:
    async with get_session() as session:
        r = await session.get(MedalShopGood, (commander_id, index))
        if r is None:
            return False
        await session.delete(r)
        await session.commit()
        return True


# ── Guild Shop async ──

async def guild_shop_get(commander_id: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        r = await session.get(GuildShopState, commander_id)
        if r is None:
            return None
        return {
            "commander_id": r.commander_id,
            "refresh_count": r.refresh_count,
            "next_refresh_time": r.next_refresh_time,
        }


async def guild_shop_upsert(commander_id: int, refresh_count: int, next_refresh_time: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("""
                INSERT INTO guild_shop_states (commander_id, refresh_count, next_refresh_time)
                VALUES (:cid, :rc, :nrt)
                ON CONFLICT (commander_id) DO UPDATE SET
                    refresh_count = EXCLUDED.refresh_count,
                    next_refresh_time = EXCLUDED.next_refresh_time
            """),
            {"cid": commander_id, "rc": refresh_count, "nrt": next_refresh_time},
        )
        await session.commit()


async def guild_shop_goods_list(commander_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            select(GuildShopGood).where(GuildShopGood.commander_id == commander_id).order_by(GuildShopGood.index)
        )
        return [
            {"commander_id": r.commander_id, "index": r.index, "goods_id": r.goods_id, "count": r.count}
            for r in result.scalars().all()
        ]


async def guild_shop_good_create(commander_id: int, index: int, goods_id: int, count: int) -> None:
    async with get_session() as session:
        session.add(GuildShopGood(commander_id=commander_id, index=index, goods_id=goods_id, count=count))
        await session.commit()


async def guild_shop_good_update(commander_id: int, index: int, goods_id: int = None, count: int = None) -> None:
    async with get_session() as session:
        r = await session.get(GuildShopGood, (commander_id, index))
        if r is None:
            return
        if goods_id is not None:
            r.goods_id = goods_id
        if count is not None:
            r.count = count
        await session.commit()


async def guild_shop_good_delete(commander_id: int, index: int) -> bool:
    async with get_session() as session:
        r = await session.get(GuildShopGood, (commander_id, index))
        if r is None:
            return False
        await session.delete(r)
        await session.commit()
        return True


async def guild_shop_good_get_by_index(commander_id: int, index: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        r = await session.get(GuildShopGood, (commander_id, index))
        if r is None:
            return None
        return {"goods_id": r.goods_id, "count": r.count}


async def guild_shop_good_decrement(commander_id: int, index: int, goods_id: int, amount: int) -> bool:
    async with get_session() as session:
        r = await session.get(GuildShopGood, (commander_id, index))
        if r is None or r.goods_id != goods_id or r.count < amount:
            return False
        r.count -= amount
        await session.commit()
        return True


async def guild_shop_state_get(commander_id: int) -> Optional[dict[str, Any]]:
    from src.orm.guild_shop_state import GuildShopState
    async with get_session() as session:
        r = await session.get(GuildShopState, commander_id)
        if r is None:
            return None
        return {"refresh_count": r.refresh_count, "next_refresh_time": r.next_refresh_time}


# ── Mini Game Shop async ──

async def mini_game_shop_get(commander_id: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        r = await session.get(MiniGameShopState, commander_id)
        if r is None:
            return None
        return {"commander_id": r.commander_id, "next_refresh_time": r.next_refresh_time}


async def mini_game_shop_upsert(commander_id: int, next_refresh_time: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("""
                INSERT INTO mini_game_shop_states (commander_id, next_refresh_time)
                VALUES (:cid, :nrt)
                ON CONFLICT (commander_id) DO UPDATE SET
                    next_refresh_time = EXCLUDED.next_refresh_time
            """),
            {"cid": commander_id, "nrt": next_refresh_time},
        )
        await session.commit()


async def mini_game_shop_goods_list(commander_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            select(MiniGameShopGood).where(MiniGameShopGood.commander_id == commander_id)
        )
        return [
            {"commander_id": r.commander_id, "goods_id": r.goods_id, "count": r.count}
            for r in result.scalars().all()
        ]


async def mini_game_shop_good_create(commander_id: int, goods_id: int, count: int) -> None:
    async with get_session() as session:
        session.add(MiniGameShopGood(commander_id=commander_id, goods_id=goods_id, count=count))
        await session.commit()


async def mini_game_shop_good_update(commander_id: int, goods_id: int, count: int = None) -> None:
    async with get_session() as session:
        r = await session.get(MiniGameShopGood, (commander_id, goods_id))
        if r is None:
            return
        if count is not None:
            r.count = count
        await session.commit()


async def mini_game_shop_good_delete(commander_id: int, goods_id: int) -> bool:
    async with get_session() as session:
        r = await session.get(MiniGameShopGood, (commander_id, goods_id))
        if r is None:
            return False
        await session.delete(r)
        await session.commit()
        return True


# ── Shopping Street async ──

async def shopping_street_state_get(commander_id: int) -> Optional[dict[str, Any]]:
    from src.orm.shopping_street import get_shopping_street_state
    return get_shopping_street_state(commander_id)


async def shopping_street_state_upsert(commander_id: int, level: int, next_flash_time: int, level_up_time: int, flash_count: int) -> None:
    from src.orm.shopping_street import upsert_shopping_street_state
    upsert_shopping_street_state(commander_id, level, next_flash_time, level_up_time, flash_count)


async def shopping_street_goods_list(commander_id: int) -> list[dict[str, Any]]:
    from src.orm.shopping_street import list_shopping_street_goods
    return list_shopping_street_goods(commander_id)


async def shopping_street_good_upsert(commander_id: int, goods_id: int, discount: int, buy_count: int) -> None:
    from src.orm.shopping_street import upsert_shopping_street_good
    upsert_shopping_street_good(commander_id, goods_id, discount, buy_count)


async def shopping_street_good_delete(commander_id: int, goods_id: int) -> bool:
    from src.orm.shopping_street import delete_shopping_street_good
    return delete_shopping_street_good(commander_id, goods_id)


# ── Notices async ──

async def notices_list(offset: int = 0, limit: int = 100) -> list[dict[str, Any]]:
    from src.orm.notice import list_notices
    rows = list_notices()
    return [
        {
            "id": r.id, "version": r.version, "btn_title": r.btn_title,
            "title": r.title, "title_image": r.title_image, "time_desc": r.time_desc,
            "content": r.content, "tag_type": r.tag_type, "icon": r.icon, "track": r.track,
        }
        for r in rows
    ][offset:offset + limit]


async def notices_active() -> list[dict[str, Any]]:
    from src.orm.notice import list_notices
    rows = list_notices()
    return [
        {
            "id": r.id, "version": r.version, "btn_title": r.btn_title,
            "title": r.title, "title_image": r.title_image, "time_desc": r.time_desc,
            "content": r.content, "tag_type": r.tag_type, "icon": r.icon, "track": r.track,
        }
        for r in rows if int(r.version) > 0
    ]


async def notices_count() -> int:
    from src.orm.notice import list_notices
    return len(list_notices())


async def notice_get(notice_id: int) -> Optional[dict[str, Any]]:
    from src.orm.notice import notice_retrieve
    r = notice_retrieve(notice_id)
    if r is None:
        return None
    return {
        "id": r.id, "version": r.version, "btn_title": r.btn_title,
        "title": r.title, "title_image": r.title_image, "time_desc": r.time_desc,
        "content": r.content, "tag_type": r.tag_type, "icon": r.icon, "track": r.track,
    }


async def notice_create(data: dict[str, Any]) -> None:
    from src.orm.notice import Notice, notice_create as _create
    _create(Notice(
        id=data["id"],
        version=data.get("version", ""),
        btn_title=data.get("btn_title", ""),
        title=data.get("title", ""),
        title_image=data.get("title_image", ""),
        time_desc=data.get("time_desc", ""),
        content=data.get("content", ""),
        tag_type=data.get("tag_type", 0),
        icon=data.get("icon", 0),
        track=data.get("track", ""),
    ))


async def notice_update(notice_id: int, data: dict[str, Any]) -> None:
    from src.orm.notice import Notice, notice_update as _update
    _update(Notice(
        id=notice_id,
        version=data.get("version", ""),
        btn_title=data.get("btn_title", ""),
        title=data.get("title", ""),
        title_image=data.get("title_image", ""),
        time_desc=data.get("time_desc", ""),
        content=data.get("content", ""),
        tag_type=data.get("tag_type", 0),
        icon=data.get("icon", 0),
        track=data.get("track", ""),
    ))


async def notice_delete(notice_id: int) -> bool:
    from src.orm.notice import notice_delete as _delete
    return _delete(notice_id)


__all__ = [
    "ArenaShopState", "MedalShopState", "MedalShopGood",
    "GuildShopState", "GuildShopGood",
    "MiniGameShopState", "MiniGameShopGood",
    "MonthShopPurchase",
    "_sync_list_month_shop_purchase_counts",
    "_sync_set_commander_medal_display",
]

list_month_shop_purchase_counts = _sync_list_month_shop_purchase_counts
set_commander_medal_display = _sync_set_commander_medal_display
