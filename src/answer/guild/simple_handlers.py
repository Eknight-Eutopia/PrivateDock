import time
from datetime import datetime, timezone

from src.answer.guild.helpers import (
    now_unix,
    is_valid_guild_name, is_valid_guild_faction, is_valid_guild_policy,
    clamp_guild_apply_content,
    guildResultSuccess, guildResultFailure, guildResultNameInvalid,
    guildApplyResultSuccess, guildApplyResultFailure,
    guildApplyResultJoinCD, guildApplyResultMaxed,
    guildApplyResultFrozen, guildApplyResultFull,
    guildApplyOutstandingLimit,
    load_game_set_uint, build_guild_chat_player,
    load_guild_store_purchase_entry, normalize_guild_shop_selection,
    map_guild_shop_drop_type,
    guildShopPurchaseResultOK, guildShopPurchaseResultInvalid,
    guildShopPurchaseResultInsufficient, guildShopPurchaseResultStock,
    guildShopPurchaseResultUnsupported, guildShopPurchaseResultDBError,
    guildShopCoinResourceID,
    guildShopGetShop, guildShopAutoRefresh, guildShopManualRefresh,
)
from src.db.store import get_default_store
from src.orm import (
    guild_shop_good_get_by_index, guild_shop_good_decrement,
    has_enough_resource_async, consume_resource_async,
    add_item, add_ship,
)
from src.protobuf import protobuf


async def guild_apply(buffer: bytes, client) -> tuple:
    request = protobuf.CS_60005()
    request.ParseFromString(buffer)
    response = protobuf.SC_60006(result=guildApplyResultFailure)
    if getattr(client, 'commander', None) is None:
        return await client.send_message(60006, response)
    guild_id = request.id
    if guild_id == 0:
        response.result = guildApplyResultFrozen
        return await client.send_message(60006, response)
    store = get_default_store()
    existing = await store.afetchrow(
        "SELECT guild_id FROM guild_members WHERE commander_id = $1",
        client.commander.commander_id,
    )
    if existing:
        response.result = guildApplyResultJoinCD
        return await client.send_message(60006, response)
    wait_row = await store.fetchval(
        "SELECT guild_wait_time FROM commander_guild_states WHERE commander_id = $1",
        client.commander.commander_id,
    )
    if wait_row and wait_row > int(time.time()):
        response.result = guildApplyResultJoinCD
        return await client.send_message(60006, response)
    guild = await store.afetchrow(
        "SELECT id, level, member_count FROM guilds WHERE id = $1", guild_id,
    )
    if guild is None:
        response.result = guildApplyResultFrozen
        return await client.send_message(60006, response)
    member_limit = 30 + (guild["level"] * 5)
    if guild["member_count"] >= member_limit:
        response.result = guildApplyResultFull
        return await client.send_message(60006, response)
    existing_req = await store.afetchrow(
        "SELECT 1 FROM guild_join_requests WHERE guild_id = $1 AND applicant_commander_id = $2 LIMIT 1",
        guild_id, client.commander.commander_id,
    )
    if not existing_req:
        count = await store.fetchval(
            "SELECT COUNT(*) FROM guild_join_requests WHERE applicant_commander_id = $1",
            client.commander.commander_id,
        )
        if count >= guildApplyOutstandingLimit:
            response.result = guildApplyResultMaxed
            return await client.send_message(60006, response)
    content = clamp_guild_apply_content(request.content)
    await store.aexecute(
        "INSERT INTO guild_join_requests (guild_id, applicant_commander_id, content, requested_at) "
        "VALUES ($1, $2, $3, $4) "
        "ON CONFLICT (guild_id, applicant_commander_id) DO UPDATE SET content = $3",
        guild_id, client.commander.commander_id, content, datetime.now(timezone.utc),
    )
    response.result = guildApplyResultSuccess
    return await client.send_message(60006, response)


async def guild_dissolve(buffer: bytes, client) -> tuple:
    payload = protobuf.CS_60010()
    payload.ParseFromString(buffer)
    response = protobuf.SC_60011(result=guildResultFailure)
    guild_id = payload.id
    if guild_id == 0:
        return await client.send_message(60011, response)
    store = get_default_store()
    await store.aexecute("DELETE FROM guilds WHERE id = $1 AND id IN (SELECT guild_id FROM guild_members WHERE commander_id = $2 AND duty = 1)", guild_id, client.commander.commander_id)
    response.result = guildResultSuccess
    return await client.send_message(60011, response)


async def guild_fire(buffer: bytes, client) -> tuple:
    payload = protobuf.CS_60014()
    payload.ParseFromString(buffer)
    response = protobuf.SC_60015(result=guildResultFailure)
    target = payload.player_id
    if target == 0 or target == client.commander.commander_id:
        return await client.send_message(60015, response)
    store = get_default_store()
    await store.aexecute("DELETE FROM guild_members WHERE guild_id IN (SELECT guild_id FROM guild_members WHERE commander_id = $1 AND duty IN (1,2)) AND commander_id = $2", client.commander.commander_id, target)
    response.result = guildResultSuccess
    return await client.send_message(60015, response)


async def guild_impeach(buffer: bytes, client) -> tuple:
    payload = protobuf.CS_60016()
    payload.ParseFromString(buffer)
    response = protobuf.SC_60017(result=guildResultFailure)
    target = payload.player_id
    if target == 0 or target == client.commander.commander_id:
        return await client.send_message(60017, response)
    store = get_default_store()
    await store.aexecute(
        "UPDATE guilds SET kick_leader_cd = $3 WHERE id IN (SELECT guild_id FROM guild_members WHERE commander_id = $1) AND id IN (SELECT guild_id FROM guild_members WHERE commander_id = $2)",
        client.commander.commander_id, target, int(datetime.now(timezone.utc).timestamp()) + 86400,
    )
    response.result = guildResultSuccess
    return await client.send_message(60017, response)


async def modify_guild_info(buffer: bytes, client) -> tuple:
    payload = protobuf.CS_60026()
    payload.ParseFromString(buffer)
    response = protobuf.SC_60027(result=guildResultFailure)
    op_type = payload.type
    if op_type < 1 or op_type > 5:
        return await client.send_message(60027, response)
    store = get_default_store()
    row = await store.afetchrow(
        "SELECT g.id FROM guilds g JOIN guild_members gm ON gm.guild_id = g.id WHERE gm.commander_id = $1",
        client.commander.commander_id,
    )
    if row is None:
        return await client.send_message(60027, response)
    int_val = payload.int
    str_val = payload.str.strip()
    if op_type == 1 and not is_valid_guild_name(str_val):
        response.result = guildResultNameInvalid
        return await client.send_message(60027, response)
    if op_type == 2 and not is_valid_guild_faction(int_val):
        return await client.send_message(60027, response)
    if op_type == 3 and not is_valid_guild_policy(int_val):
        return await client.send_message(60027, response)
    if op_type == 4 and not str_val:
        return await client.send_message(60027, response)
    if op_type == 1:
        name_cost = await load_game_set_uint("modify_guild_cost")
        if not await _has_resource(client, 4, name_cost):
            return await client.send_message(60027, response)
    fields = {1: "name", 2: "faction", 3: "policy", 4: "announce", 5: "manifesto"}
    field = fields.get(op_type)
    if field == "name":
        existing = await store.fetchval("SELECT 1 FROM guilds WHERE name = $1 AND id != $2 LIMIT 1", str_val, row["id"])
        if existing:
            response.result = guildResultNameInvalid
            return await client.send_message(60027, response)
    if op_type == 1:
        val = str_val
    elif op_type in (2, 3):
        val = int_val
    else:
        val = str_val
    await store.aexecute(f"UPDATE guilds SET {field} = $1 WHERE id = $2", val, row["id"])
    response.result = guildResultSuccess
    _, _, err = client.send_message(60027, response)
    return (0, 60027, err) if err else (0, 60027, None)


async def guild_quit(buffer: bytes, client) -> tuple:
    payload = protobuf.CS_60018()
    payload.ParseFromString(buffer)
    response = protobuf.SC_60019(result=guildResultFailure)
    guild_id = payload.id
    if guild_id == 0:
        return await client.send_message(60019, response)
    store = get_default_store()
    await store.aexecute("DELETE FROM guild_members WHERE guild_id = $1 AND commander_id = $2", guild_id, client.commander.commander_id)
    response.result = guildResultSuccess
    return await client.send_message(60019, response)


async def guild_search(buffer: bytes, client) -> tuple:
    request = protobuf.CS_60028()
    request.ParseFromString(buffer)
    response = protobuf.SC_60029(result=guildResultFailure, guild=[])
    keyword = request.keyword.strip()
    if not keyword:
        return await client.send_message(60029, response)
    store = get_default_store()
    search_type = request.type
    if search_type == 0:
        try:
            guild_id = int(keyword)
        except ValueError:
            return await client.send_message(60029, response)
        rows = await store.afetch(
            "SELECT g.id, g.name, g.level, g.policy, g.faction, g.member_count, g.capital, g.exp, g.announce, g.manifesto, "
            "c.commander_id as leader_id, c.name as leader_name, c.level as leader_level "
            "FROM guilds g "
            "JOIN guild_members gm ON gm.guild_id = g.id AND gm.duty = 1 "
            "JOIN commanders c ON c.commander_id = gm.commander_id "
            "WHERE g.id = $1", guild_id,
        )
        entries = list(rows)
    elif search_type == 1:
        rows = await store.afetch(
            "SELECT g.id, g.name, g.level, g.policy, g.faction, g.member_count, g.capital, g.exp, g.announce, g.manifesto, "
            "c.commander_id as leader_id, c.name as leader_name, c.level as leader_level "
            "FROM guilds g "
            "JOIN guild_members gm ON gm.guild_id = g.id AND gm.duty = 1 "
            "JOIN commanders c ON c.commander_id = gm.commander_id "
            "WHERE g.name ILIKE $1", f"%{keyword}%",
        )
        entries = list(rows)
    else:
        return await client.send_message(60029, response)
    del response.guild[:]
    for entry in entries:
        response.guild.append(protobuf.GUILD_SIMPLE_INFO(
            base=protobuf.GUILD_BASE_INFO(id=entry["id"], name=entry["name"] or "", level=entry["level"], policy=entry["policy"], faction=entry["faction"], announce=entry.get("announce") or "", manifesto=entry.get("manifesto") or "", member_count=entry["member_count"], exp=entry["exp"], change_faction_cd=0, kick_leader_cd=0),
            leader=protobuf.PLAYER_INFO_P60(id=entry["leader_id"], name=entry["leader_name"] or "", lv=entry["leader_level"]),
            tech_seat=0,
    ))
    response.result = guildResultSuccess
    return await client.send_message(60029, response)


async def guild_send_message(buffer: bytes, client) -> tuple:
    payload = protobuf.CS_60007()
    payload.ParseFromString(buffer)
    store = get_default_store()
    now = datetime.now(timezone.utc)
    row = await store.afetchrow(
        "INSERT INTO guild_chat_messages (guild_id, sender_id, content, sent_at) "
        "VALUES ((SELECT guild_id FROM guild_members WHERE commander_id = $1), $1, $2, $3) RETURNING id, content, sent_at",
        client.commander.commander_id, payload.chat, now,
    )
    chat = protobuf.GUIDE_CHAT(
        player=build_guild_chat_player(client.commander),
        content=row["content"],
        time=int(row["sent_at"].timestamp()) if hasattr(row["sent_at"], 'timestamp') else now_unix(),
    )
    packet = protobuf.SC_60008(chat=chat)
    client.server.broadcast_guild_chat(packet)
    return 0, 60008, None


async def guild_get_user_info_command(_buffer: bytes, client) -> tuple:
    from src.answer.guild.public_tech import ensure_donate_tasks, reset_donate_if_new_day
    store = get_default_store()
    row = await store.afetchrow(
        "SELECT donate_count, donate_tasks, benefit_time, weekly_task_flag, extra_donate, extra_operation FROM guild_user_infos WHERE commander_id = $1",
        client.commander.commander_id,
    )
    if row is None:
        from src.answer.guild.public_tech import ensure_player_tech_states
        tech_ids_list = ensure_player_tech_states(client.commander.commander_id)
        response = protobuf.SC_60103(user_info=protobuf.USER_GUILD_INFO(
            donate_count=0, donate_tasks=[], benefit_time=0,
            tech_id=tech_ids_list, weekly_task_flag=0, extra_donate=0, extra_operation=0,
        ))
        return await client.send_message(60103, response)
    tech_ids = await store.afetch(
        "SELECT tech_id FROM guild_user_technology_states WHERE commander_id = $1 ORDER BY tech_group",
        client.commander.commander_id,
    )
    if not tech_ids:
        from src.answer.guild.public_tech import ensure_player_tech_states
        tech_ids_list = ensure_player_tech_states(client.commander.commander_id)
    else:
        tech_ids_list = [t["tech_id"] for t in tech_ids]
    info = reset_donate_if_new_day(client.commander.commander_id)
    donate_tasks = list(info["donate_tasks"] or [])
    if not donate_tasks:
        donate_tasks = ensure_donate_tasks(client.commander.commander_id)
    response = protobuf.SC_60103(
        user_info=protobuf.USER_GUILD_INFO(
            donate_count=info["donate_count"],
            donate_tasks=donate_tasks,
            benefit_time=row["benefit_time"],
            tech_id=tech_ids_list,
            weekly_task_flag=row.get("weekly_task_flag", 0),
            extra_donate=row.get("extra_donate", 0),
            extra_operation=row.get("extra_operation", 0),
        ),
    )
    return await client.send_message(60103, response)


async def get_guild_shop(buffer: bytes, client) -> tuple:
    payload = protobuf.CS_60033()
    payload.ParseFromString(buffer)
    if getattr(client, "commander", None) is None:
        response = protobuf.SC_60034(result=1)
        return await client.send_message(60034, response)

    from src.guildshop import (
        load_config,
        refresh_if_needed,
        refresh_goods,
        RefreshOptions,
    )
    from src.orm.resource import consume_resource_async, has_enough_resource_async

    config = load_config()
    if config is None:
        response = protobuf.SC_60034(result=1)
        return await client.send_message(60034, response)

    now = datetime.now(timezone.utc)
    commander_id = client.commander.commander_id

    state, goods, err = refresh_if_needed(commander_id, now, config)
    if err:
        response = protobuf.SC_60034(result=1)
        return await client.send_message(60034, response)

    result = 0
    req_type = payload.type
    if req_type == guildShopManualRefresh:
        if not config.can_manual_refresh(state["refresh_count"]):
            result = 1
        else:
            cost = config.refresh_cost(state["refresh_count"] + 1)
            if cost > 0 and not await has_enough_resource_async(commander_id, guildShopCoinResourceID, cost):
                result = 1
            else:
                goods, err = refresh_goods(
                    commander_id,
                    now,
                    config,
                    RefreshOptions(
                        refresh_count=state["refresh_count"] + 1,
                        next_refresh_time=state["next_refresh_time"],
                    ),
                )
                if err:
                    result = 1
                else:
                    if cost > 0:
                        await consume_resource_async(commander_id, guildShopCoinResourceID, cost)
                    state, goods, err = refresh_if_needed(commander_id, now, config)
                    if err:
                        result = 1
    elif req_type != guildShopGetShop and req_type != guildShopAutoRefresh:
        result = 1

    good_list = [
        protobuf.GOODS_INFO_P60(id=g["goods_id"], count=g["count"], index=g["index"])
        for g in goods
    ]
    response = protobuf.SC_60034(
        result=result,
        info=protobuf.SHOP_INFO(
            refresh_count=state["refresh_count"],
            next_refresh_time=state["next_refresh_time"],
            good_list=good_list,
        ),
    )
    return await client.send_message(60034, response)


async def guild_shop_purchase(buffer: bytes, client) -> tuple:
    payload = protobuf.CS_60035()
    payload.ParseFromString(buffer)
    response = protobuf.SC_60036(result=guildShopPurchaseResultInvalid)
    goods_id = payload.goodsid
    index = payload.index
    if goods_id == 0 or index == 0:
        return await client.send_message(60036, response)
    config, found = await load_guild_store_purchase_entry(goods_id)
    if not found or not config.goods or config.num == 0:
        return await client.send_message(60036, response)
    selected = list(payload.selected)
    rewards, total_units, valid = normalize_guild_shop_selection(config, selected)
    if not valid:
        return await client.send_message(60036, response)
    total_cost = config.price * total_units
    drop_type, ok = map_guild_shop_drop_type(config.type)
    if not ok:
        response.result = guildShopPurchaseResultUnsupported
        return await client.send_message(60036, response)
    slot = await guild_shop_good_get_by_index(client.commander.commander_id, index)
    if slot is None or slot["goods_id"] != goods_id or slot["count"] < total_units:
        response.result = guildShopPurchaseResultStock if (slot and slot["count"] < total_units) else guildShopPurchaseResultInvalid
        return await client.send_message(60036, response)
    commander_id = client.commander.commander_id
    if not await has_enough_resource_async(commander_id, guildShopCoinResourceID, total_cost):
        response.result = guildShopPurchaseResultInsufficient
        return await client.send_message(60036, response)
    try:
        await consume_resource_async(commander_id, guildShopCoinResourceID, total_cost)
        decr_ok = await guild_shop_good_decrement(commander_id, index, goods_id, total_units)
        if not decr_ok:
            response.result = guildShopPurchaseResultDBError
            return await client.send_message(60036, response)
        drop_list = []
        for rid, units in rewards.items():
            reward_amount = config.num * units
            if drop_type == 2:  # DROP_TYPE_ITEM
                add_item(commander_id, rid, reward_amount)
            elif drop_type == 4:  # DROP_TYPE_SHIP
                for _ in range(reward_amount):
                    add_ship(commander_id, rid)
            drop_list.append(protobuf.DROPINFO(type=drop_type, id=rid, number=reward_amount))
        response.result = guildShopPurchaseResultOK
        response.drop_list.extend(drop_list)
        try:
            from src.answer.task_handlers import schedule_emit, schedule_possession_sync
            schedule_emit(client, 151, goods_id, total_units)
            schedule_emit(client, 151, 0, total_units)
            schedule_possession_sync(client)
        except Exception:
            pass
    except Exception:
        response.result = guildShopPurchaseResultDBError
        response.drop_list.clear()
    return await client.send_message(60036, response)


async def _has_resource(client, res_id: int, amount: int) -> bool:
    return await has_enough_resource_async(client.commander.commander_id, res_id, amount)
