import asyncio
import datetime
from typing import Optional

from src.connection.client import Client
from src.orm.item import has_enough_item as _has_enough_item, consume_item as _consume_item
from src.orm.resource import has_enough_resource as _has_enough_resource, consume_resource as _consume_resource
from src.protobuf import protobuf
from src.logger.logger import log_event, LOG_LEVEL_ERROR, LOG_LEVEL_DEBUG
import traceback
from src.orm.commander import increment_commander_build_counts

from .helpers import (
    BUILD_DOCK_SLOTS,
    _current_dock_slots,
    list_builds_range,
    get_commander_counts,
    update_build_finish_time,
    settle_commander_builds_sync,
    plan_builds_sync,
)
from src.config.game_variables import get_tutorial_first_build_ship
from .build_rates import draw_ship as _draw_ship
from .build_logic import (
    pool_ships as _pool_ships,
    build_cost_normal as _build_cost_normal,
    build_info_from_row as _build_info_from_row,
    exchange_points_for_pool as _exchange_points_for_pool,
    regular_exchange_request as _regular_exchange_request,
)


def _draw_pool_ship_sync(pool_id: int) -> Optional[int]:
    ships = _pool_ships(pool_id)
    if not ships:
        return None
    return _draw_ship(ships, mode="base")


def _increment_draw_count_sync(
    commander_id: int,
    count: int,
    exchange_points: int,
    exchange_cap: int,
):
    increment_commander_build_counts(
        commander_id, count, exchange_points, exchange_cap
    )


def _refresh_commander_builds(client: Client, rows: list):
    """Point the live commander cache at authoritative queue rows (id order)."""
    try:
        client.commander.builds = rows
    except Exception:
        pass


async def _send_build_result(client: Client, response) -> None:
    """Send SC_12003, then overwrite the client's optimistic wallet with DB state."""
    await client.send_message(12003, response)
    try:
        from src.answer.player_resource_sync import send_player_resource_sync
        send_player_resource_sync(client)
    except Exception:
        pass


def handle_ship_build(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_12002()
    payload.ParseFromString(buffer)
    response = protobuf.SC_12003()

    pool_id = payload.id
    count = payload.count
    cost_type = payload.costtype
    log_event("ShipBuild", "Start",
              f"cid={client.commander.commander_id} pool={pool_id} count={count} cost_type={cost_type}",
              LOG_LEVEL_DEBUG)

    gold_cost, cube_cost = _build_cost_normal(pool_id)
    gold_cost *= count
    cube_cost *= count

    cid = client.commander.commander_id
    if cost_type == 0:
        if not _has_enough_resource(cid, 1, gold_cost):
            response.result = 2
            asyncio.create_task(client.send_message(12003, response))
            return 0, 12003, None
        if not _has_enough_item(cid, 20001, cube_cost):
            response.result = 3
            asyncio.create_task(client.send_message(12003, response))
            return 0, 12003, None

    # Draw first so a failed roll never leaves a partial batch inserted.
    # Tutorial first build: until the auto-commit Guide task "Build 1 ship."
    # (23003) is submitted, this commander has not done the tutorial build —
    # the first drawn ship is pinned to the fixed ship from game_variables.json
    # (tutorial_first_build_ship) so every new player gets the same ship;
    # 0/absent keeps the normal roll. is_first_build is cached on the Commander
    # (one DB read per session) and flipped once the pin is consumed.
    drawn_ship_ids = []
    if client.commander.is_first_build:
        forced_first_ship = get_tutorial_first_build_ship()
        if forced_first_ship is not None:
            log_event("ShipBuild", "TutorialPin",
                      f"cid={cid} first build pinned to {forced_first_ship}",
                      LOG_LEVEL_DEBUG)
            drawn_ship_ids.append(forced_first_ship)
            count -= 1
            client.commander.is_first_build = False
    for _ in range(count):
        ship_id = _draw_pool_ship_sync(pool_id)
        if ship_id is None:
            response.result = 1
            asyncio.create_task(client.send_message(12003, response))
            return 0, 12003, None
        drawn_ship_ids.append(ship_id)

    now = datetime.datetime.now(datetime.timezone.utc)
    draws = [{"ship_id": sid, "pool_id": pool_id} for sid in drawn_ship_ids]
    all_rows, new_rows = plan_builds_sync(cid, draws, now)
    _refresh_commander_builds(client, all_rows)

    # `count` was decremented by the tutorial pin, so derive every count from
    # the ships actually queued -- otherwise a 1x first build emits progress
    # for 0 ships and "Build 1 ship." (23003) never advances.
    queued_count = len(drawn_ship_ids)

    if cost_type == 0:
        _consume_item(cid, 20001, cube_cost)
    _consume_resource(cid, 1, gold_cost)

    _increment_draw_count_sync(
        cid,
        queued_count,
        queued_count * _exchange_points_for_pool(pool_id),
        _regular_exchange_request(),
    )

    # Server-authoritative task progress: starting a build advances "Build N ships" tasks.
    try:
        from src.answer.task_handlers import schedule_emit
        schedule_emit(client, 30, 0, queued_count)
    except Exception:
        pass

    response.result = 0
    response.build_info.extend(_build_info_from_row(row, now) for row in new_rows)
    asyncio.create_task(_send_build_result(client, response))
    return 0, 12003, None


def handle_ongoing_builds(
    _buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    async def _do():
        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            # Reconcile the 4-slot queue against real time (offline builds may
            # have finished / advanced) before reporting the worklist.
            rows = settle_commander_builds_sync(client.commander.commander_id, now)
            _refresh_commander_builds(client, rows)

            counts = await get_commander_counts(client.commander.commander_id)
            response = protobuf.SC_12024(
                worklist_count=_current_dock_slots(),
                worklist_list=[_build_info_from_row(row, now) for row in rows],
                draw_count_1=counts.get("draw_count1", 0),
                draw_count_10=counts.get("draw_count10", 0),
                exchange_count=counts.get("exchange_count", 0),
            )
            await client.send_message(12024, response)
        except Exception as e:
            log_event("ShipBuild", "handle_ongoing_builds", f"{e}\n{traceback.format_exc()}", LOG_LEVEL_ERROR)

    asyncio.create_task(_do())
    return 0, 12024, None


def handle_build_quick_finish(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_12008()
    payload.ParseFromString(buffer)
    response = protobuf.SC_12009()
    pos_list = list(payload.pos_list)

    async def _do():
        min_pos = 999999
        max_pos = 0
        for pos in pos_list:
            if pos < min_pos:
                min_pos = pos
            if pos > max_pos:
                max_pos = pos

        if min_pos > 0:
            min_pos -= 1
        if max_pos > 0:
            max_pos -= 1
        if max_pos == min_pos:
            max_pos += 1

        limit = max_pos - min_pos + 1
        builds = await list_builds_range(client.commander.commander_id, min_pos, limit)

        cid = client.commander.commander_id
        now = datetime.datetime.now(datetime.timezone.utc)
        for build in builds:
            if not _has_enough_item(cid, 15003, 1):
                continue
            await update_build_finish_time(build["id"], now - datetime.timedelta(seconds=1))
            _consume_item(cid, 15003, 1)

        # Freeing a slot may start queued builds earlier than planned: settle.
        rows = settle_commander_builds_sync(cid, now)
        _refresh_commander_builds(client, rows)

        response.result = 0
        response.pos_list.extend(pos_list)
        await client.send_message(12009, response)

    asyncio.create_task(_do())
    return 0, 12009, None


def handle_build_finish(
    _buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    async def _do():
        try:
            # Pure info query (client getshipcommand.lua maps pos->tid from
            # infoList BEFORE sending CS_12025).
            # pos must be the 1-based index into the same canonical order as
            # SC_12024's worklist_list and CS_12025's pos resolution.
            from .helpers import list_all_builds
            builds = await list_all_builds(client.commander.commander_id)
            build_infos = [
                protobuf.BUILD_INFO(pos=i + 1, tid=work["ship_id"])
                for i, work in enumerate(builds)
            ]
            bl = getattr(client.commander, "builds", None)
            if bl is not None:
                client.commander.builds = list(builds)
            response = protobuf.SC_12044()
            response.infoList.extend(build_infos)
            await client.send_message(12044, response)
        except Exception as e:
            log_event("ShipBuild", "BuildFinishError", f"{e}\n{traceback.format_exc()}", LOG_LEVEL_ERROR)

    asyncio.create_task(_do())
    return 0, 12044, None
