import json
from datetime import datetime, timezone

from src.answer.guild.helpers import (
    now_unix, current_week_monday_0_clock, guildChunkResultSuccess, guildChunkResultFailure,
    guildResultGuildFrozen, guildCoinResourceID, goldResourceID,
    load_guild_contribution_template, load_default_guild_donate_tasks,
    load_guild_mission_template, load_guild_technology_template,
    load_game_set_uint, dropTypeResource, dropTypeItem,
)
from src.db.store import get_default_store
from src.protobuf import protobuf


async def accept_guild_join_request(buffer: bytes, client) -> tuple:
    request = protobuf.CS_60020()
    request.ParseFromString(buffer)
    response = protobuf.SC_60021(result=guildChunkResultFailure)
    if getattr(client, 'commander', None) is None or request.player_id == 0:
        return await client.send_message(60021, response)
    store = get_default_store()
    row = await store.afetchrow(
        "SELECT accept_guild_join_request($1, $2) as result",
        client.commander.commander_id, request.player_id,
    )
    result = row["result"] if row else guildChunkResultFailure
    response.result = result
    if result == guildChunkResultSuccess:
        # Server-authoritative task progress: the ACCEPTED applicant just joined
        # a guild ("Join any guild", sub_type 403) -- sync their possession
        # tasks if that player is connected.
        try:
            from src.orm.active_commander import get_active_client
            from src.answer.task_handlers import schedule_possession_sync
            target = get_active_client(request.player_id)
            if target is not None:
                schedule_possession_sync(target)
        except Exception:
            pass
    return await client.send_message(60021, response)


async def guild_list_refresh(buffer: bytes, client) -> tuple:
    request = protobuf.CS_60024()
    request.ParseFromString(buffer)
    response = protobuf.SC_60025(guild_list=[])
    if request.type != 0:
        return await client.send_message(60025, response)
    store = get_default_store()
    rows = await store.afetch(
        "SELECT g.id, g.name, g.level, g.policy, g.faction, g.announce, g.manifesto, g.member_count, g.capital, g.exp, "
        "c.commander_id as leader_id, c.name as leader_name, c.level as leader_level, "
        "c.display_icon_id, c.display_skin_id, c.selected_icon_frame_id, c.selected_chat_frame_id, c.display_icon_theme_id "
        "FROM guilds g "
        "JOIN guild_members gm ON gm.guild_id = g.id AND gm.duty = 1 "
        "JOIN commanders c ON c.commander_id = gm.commander_id "
        "ORDER BY g.member_count DESC LIMIT 30"
    )
    for row in rows:
        response.guild_list.append(protobuf.GUILD_SIMPLE_INFO(
            base=protobuf.GUILD_BASE_INFO(id=row["id"], name=row["name"] or "", level=row["level"], policy=row["policy"], faction=row["faction"], announce=row.get("announce") or "", manifesto=row.get("manifesto") or "", member_count=row["member_count"], exp=row["exp"], change_faction_cd=0, kick_leader_cd=0),
            leader=protobuf.PLAYER_INFO_P60(id=row["leader_id"], name=row["leader_name"] or "", lv=row["leader_level"]),
            tech_seat=0,
    ))
    return await client.send_message(60025, response)


async def guild_commit_donate(buffer: bytes, client) -> tuple:
    request = protobuf.CS_62002()
    request.ParseFromString(buffer)
    response = protobuf.SC_62003(result=guildChunkResultFailure, donate_tasks=[])
    if getattr(client, 'commander', None) is None or request.id == 0:
        return await client.send_message(62003, response)
    tpl, ok = await load_guild_contribution_template(request.id)
    if not ok:
        return await client.send_message(62003, response)
    store = get_default_store()
    info_row = await store.afetchrow(
        "SELECT donate_count, donate_tasks, benefit_time, weekly_task_flag, extra_donate, extra_operation FROM guild_user_infos WHERE commander_id = $1",
        client.commander.commander_id,
    )
    tasks = list(info_row["donate_tasks"]) if info_row and info_row.get("donate_tasks") else []
    if not tasks:
        tasks = await load_default_guild_donate_tasks()
    if request.id not in tasks:
        response.DonateTasks = tasks
        return await client.send_message(62003, response)
    guild_row = await store.afetchrow(
        "SELECT g.id, g.capital FROM guilds g JOIN guild_members gm ON gm.guild_id = g.id WHERE gm.commander_id = $1",
        client.commander.commander_id,
    )
    guild_id = guild_row["id"] if guild_row else None
    member_row = None
    if guild_id:
        member_row = await store.afetchrow(
            "SELECT commander_id, liveness FROM guild_members WHERE guild_id = $1 AND commander_id = $2",
            guild_id, client.commander.commander_id,
        )
    consume = tpl.consume
    if len(consume) >= 3:
        consume_type = consume[0]
        consume_id = consume[1]
        consume_amount = consume[2]
        if consume_type == dropTypeResource:
            if not await _consume_resource(client, consume_id, consume_amount):
                response.DonateTasks = tasks
                return await client.send_message(62003, response)
        else:
            if not await _consume_item(client, consume_id, consume_amount):
                response.DonateTasks = tasks
                return await client.send_message(62003, response)
    if guild_id:
        await store.aexecute(
            "UPDATE guild_user_infos SET donate_count = donate_count + 1, donate_tasks = $2 WHERE commander_id = $1",
            client.commander.commander_id, json.dumps(tasks),
        )
        await store.aexecute(
            "UPDATE guilds SET capital = capital + $2, updated_at = CURRENT_TIMESTAMP WHERE id = $1",
            guild_id, tpl.award_capital,
        )
        if member_row:
            await store.aexecute(
                "UPDATE guild_members SET liveness = liveness + $3 WHERE guild_id = $1 AND commander_id = $2",
                guild_id, client.commander.commander_id, tpl.guild_active,
            )
    response.result = guildChunkResultSuccess
    response.DonateTasks = tasks
    _, _, send_err = client.send_message(62003, response)
    if send_err:
        return 0, 62003, send_err
    if guild_id:
        await store.aexecute(
            "INSERT INTO guild_capital_logs (guild_id, category, member_id, name, event_type, event_target, time) "
            "VALUES ($1, 1, $2, $3, 1, $4, $5)",
            guild_id, client.commander.commander_id, client.commander.name, [request.id], now_unix(),
        )
        _broadcast(client, guild_id, 62019, protobuf.SC_62019(
            id=request.id, user_id=client.commander.commander_id,
            has_capital=tpl.award_capital, has_tech_point=tpl.award_tech_exp,
        ))
    _, _, _ = client.send_message(62031, protobuf.SC_62031(donate_tasks=tasks))
    return 0, 62003, None


async def guild_buy_supply(buffer: bytes, client) -> tuple:
    request = protobuf.CS_62007()
    request.ParseFromString(buffer)
    response = protobuf.SC_62008(result=guildChunkResultFailure)
    if getattr(client, 'commander', None) is None or request.type != 0:
        return await client.send_message(62008, response)
    store = get_default_store()
    row = await store.afetchrow(
        "SELECT g.id, gm.duty FROM guilds g JOIN guild_members gm ON gm.guild_id = g.id WHERE gm.commander_id = $1",
        client.commander.commander_id,
    )
    if row is None:
        return await client.send_message(62008, response)
    if row["duty"] not in (1, 2):
        return await client.send_message(62008, response)
    cost = await load_game_set_uint("guild_award_consume")
    duration = await load_game_set_uint("guild_award_duration")
    finish_time = now_unix() + duration
    await store.aexecute(
        "UPDATE guilds SET capital = capital - $1 WHERE id = $2 AND capital >= $1",
        cost, row["id"],
    )
    await store.aexecute(
        "INSERT INTO guild_office_states (guild_id, benefit_finish_time, last_benefit_finish_time, tech_cancel_cnt) "
        "VALUES ($1, $2, 0, 0) "
        "ON CONFLICT (guild_id) DO UPDATE SET benefit_finish_time = $2",
        row["id"], finish_time,
    )
    await store.aexecute(
        "INSERT INTO guild_capital_logs (guild_id, category, member_id, name, event_type, event_target, time) "
        "VALUES ($1, 2, $2, $3, 2, $4, $5)",
        row["id"], client.commander.commander_id, client.commander.name, [cost], now_unix(),
    )
    response.result = guildChunkResultSuccess
    _, _, err = client.send_message(62008, response)
    if err:
        return 0, 62008, err
    _broadcast(client, row["id"], 62005, protobuf.SC_62005(benefit_finish_time=finish_time))
    return 0, 62008, None


async def guild_get_supply_award_command_response(buffer: bytes, client) -> tuple:
    request = protobuf.CS_62009()
    request.ParseFromString(buffer)
    response = protobuf.SC_62010(result=guildChunkResultFailure, drop_list=[])
    if getattr(client, 'commander', None) is None or request.type != 0:
        return await client.send_message(62010, response)
    store = get_default_store()
    row = await store.afetchrow(
        "SELECT g.id, gm.duty, gm.join_time FROM guilds g JOIN guild_members gm ON gm.guild_id = g.id WHERE gm.commander_id = $1",
        client.commander.commander_id,
    )
    if row is None:
        return await client.send_message(62010, response)
    if row["duty"] == 3:
        return await client.send_message(62010, response)
    today_start = int(datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    if row["join_time"] >= today_start:
        return await client.send_message(62010, response)
    office = await store.afetchrow(
        "SELECT benefit_finish_time FROM guild_office_states WHERE guild_id = $1",
        row["id"],
    )
    if office is None or office["benefit_finish_time"] == 0 or office["benefit_finish_time"] <= now_unix():
        return await client.send_message(62010, response)
    info = await store.afetchrow(
        "SELECT benefit_time FROM guild_user_infos WHERE commander_id = $1",
        client.commander.commander_id,
    )
    if info and info["benefit_time"] >= today_start:
        return await client.send_message(62010, response)
    reward_id = await load_game_set_uint("guild_award_drop")
    await store.aexecute(
        "UPDATE guild_user_infos SET benefit_time = $2 WHERE commander_id = $1",
        client.commander.commander_id, now_unix(),
    )
    await store.aexecute(
        "INSERT INTO guild_capital_logs (guild_id, category, member_id, name, event_type, event_target, time) "
        "VALUES ($1, 3, $2, $3, 3, $4, $5)",
        row["id"], client.commander.commander_id, client.commander.name, [reward_id], now_unix(),
    )
    response.result = guildChunkResultSuccess
    response.drop_list = [protobuf.DROPINFO(type=dropTypeItem, id=reward_id, number=1)]
    return await client.send_message(62010, response)


async def guild_fetch_capital_log_command_response(buffer: bytes, client) -> tuple:
    request = protobuf.CS_62011()
    request.ParseFromString(buffer)
    response = protobuf.SC_62012(result=guildChunkResultFailure, inclog=[], declog=[], otherlog=[])
    if getattr(client, 'commander', None) is None or request.type != 0:
        return await client.send_message(62012, response)
    store = get_default_store()
    row = await store.afetchrow(
        "SELECT g.id FROM guilds g JOIN guild_members gm ON gm.guild_id = g.id WHERE gm.commander_id = $1",
        client.commander.commander_id,
    )
    if row is None:
        return await client.send_message(62012, response)
    logs = await store.afetch(
        "SELECT category, member_id, name, event_type, event_target, time FROM guild_capital_logs "
        "WHERE guild_id = $1 ORDER BY time DESC LIMIT 120",
        row["id"],
    )
    inclog, declog, otherlog = [], [], []
    for log in logs:
        entry = protobuf.CAPITAL_LOG(member_id=log["member_id"], name=log["name"] or "", event_type=log["event_type"], event_target=log.get("event_target") or [], time=log["time"])
        cat = log["category"]
        if cat == 1:
            inclog.append(entry)
        elif cat == 2:
            declog.append(entry)
        else:
            otherlog.append(entry)
    response.result = guildChunkResultSuccess
    response.Inclog = inclog
    response.Declog = declog
    response.Otherlog = otherlog
    return await client.send_message(62012, response)


async def guild_select_weekly_task(buffer: bytes, client) -> tuple:
    request = protobuf.CS_62013()
    request.ParseFromString(buffer)
    response = protobuf.SC_62014(result=guildChunkResultFailure)
    if getattr(client, 'commander', None) is None or request.id == 0:
        return await client.send_message(62014, response)
    store = get_default_store()
    row = await store.afetchrow(
        "SELECT g.id, gm.duty FROM guilds g JOIN guild_members gm ON gm.guild_id = g.id WHERE gm.commander_id = $1",
        client.commander.commander_id,
    )
    if row is None or row["duty"] not in (1, 2):
        return await client.send_message(62014, response)
    _, ok = await load_guild_mission_template(request.id)
    if not ok:
        return await client.send_message(62014, response)
    current = await store.afetchrow(
        "SELECT task_id, progress, monday_0_clock FROM guild_weekly_task_states WHERE guild_id = $1",
        row["id"],
    )
    week_start = current_week_monday_0_clock()
    if current and current["task_id"] != 0 and current["monday_0_clock"] == week_start:
        return await client.send_message(62014, response)
    await store.aexecute(
        "INSERT INTO guild_weekly_task_states (guild_id, task_id, progress, monday_0_clock) "
        "VALUES ($1, $2, 0, $3) "
        "ON CONFLICT (guild_id) DO UPDATE SET task_id = $2, progress = 0, monday_0_clock = $3",
        row["id"], request.id, week_start,
    )
    response.result = guildChunkResultSuccess
    _, _, err = client.send_message(62014, response)
    if err:
        return 0, 62014, err
    _broadcast(client, row["id"], 62004, protobuf.SC_62004(
        this_weekly_tasks=protobuf.WEEKLY_TASK(id=request.id, progress=0, monday_0clock=week_start),
    ))
    return 0, 62014, None


async def guild_upgrade_technology_command_response(buffer: bytes, client) -> tuple:
    request = protobuf.CS_62015()
    request.ParseFromString(buffer)
    response = protobuf.SC_62016(result=guildChunkResultFailure)
    if getattr(client, 'commander', None) is None or request.id == 0:
        return await client.send_message(62016, response)
    store = get_default_store()
    guild_row = await store.afetchrow(
        "SELECT g.id FROM guilds g JOIN guild_members gm ON gm.guild_id = g.id WHERE gm.commander_id = $1",
        client.commander.commander_id,
    )
    if guild_row is None:
        response.result = guildResultGuildFrozen
        return await client.send_message(62016, response)
    tpl, ok = await load_guild_technology_template(request.id)
    if not ok or tpl.group == 0 or tpl.next_tech == 0:
        return await client.send_message(62016, response)
    current_tech = await store.fetchval(
        "SELECT tech_id FROM guild_user_technology_states WHERE commander_id = $1 AND tech_group = $2",
        client.commander.commander_id, tpl.group,
    )
    if current_tech and current_tech != 0 and current_tech != request.id:
        return await client.send_message(62016, response)
    coin_cost = tpl.contribution_consume
    if tpl.contribution_multiple > 1:
        coin_cost *= tpl.contribution_multiple
    if coin_cost > 0:
        if not await _consume_resource(client, guildCoinResourceID, coin_cost):
            return await client.send_message(62016, response)
    if tpl.gold_consume > 0:
        if not await _consume_resource(client, goldResourceID, tpl.gold_consume):
            return await client.send_message(62016, response)
    await store.aexecute(
        "INSERT INTO guild_user_technology_states (commander_id, tech_group, tech_id, updated_at) "
        "VALUES ($1, $2, $3, CURRENT_TIMESTAMP) "
        "ON CONFLICT (commander_id, tech_group) DO UPDATE SET tech_id = EXCLUDED.tech_id, updated_at = CURRENT_TIMESTAMP",
        client.commander.commander_id, tpl.group, tpl.next_tech,
    )
    response.result = guildChunkResultSuccess
    return await client.send_message(62016, response)


async def guild_start_tech_group_command_response(buffer: bytes, client) -> tuple:
    request = protobuf.CS_62020()
    request.ParseFromString(buffer)
    response = protobuf.SC_62021(result=guildChunkResultFailure)
    if getattr(client, 'commander', None) is None or request.id == 0:
        return await client.send_message(62021, response)
    store = get_default_store()
    row = await store.afetchrow(
        "SELECT g.id, gm.duty FROM guilds g JOIN guild_members gm ON gm.guild_id = g.id WHERE gm.commander_id = $1",
        client.commander.commander_id,
    )
    if row is None or row["duty"] not in (1, 2):
        return await client.send_message(62021, response)
    _, ok = await load_guild_technology_template(request.id)
    if not ok:
        return await client.send_message(62021, response)
    await store.aexecute("UPDATE guild_office_states SET tech_cancel_cnt = 0, active_tech_id = $2 WHERE guild_id = $1", row["id"], request.id)
    await store.aexecute(
        "INSERT INTO guild_capital_logs (guild_id, category, member_id, name, event_type, event_target, time) "
        "VALUES ($1, 3, $2, $3, 4, $4, $5)",
        row["id"], client.commander.commander_id, client.commander.name, [request.id], now_unix(),
    )
    response.result = guildChunkResultSuccess
    _, _, err = client.send_message(62021, response)
    if err:
        return 0, 62021, err
    _broadcast(client, row["id"], 62018, protobuf.SC_62018(id=request.id))
    return 0, 62021, None


async def guild_fetch_weekly_task_progress_command_response(buffer: bytes, client) -> tuple:
    request = protobuf.CS_62022()
    request.ParseFromString(buffer)
    response = protobuf.SC_62023(result=guildChunkResultFailure, progress=0)
    if getattr(client, 'commander', None) is None or request.type != 0:
        return await client.send_message(62023, response)
    store = get_default_store()
    row = await store.afetchrow(
        "SELECT g.id FROM guilds g JOIN guild_members gm ON gm.guild_id = g.id WHERE gm.commander_id = $1",
        client.commander.commander_id,
    )
    if row is None:
        return await client.send_message(62023, response)
    state = await store.afetchrow(
        "SELECT task_id, progress, monday_0_clock FROM guild_weekly_task_states WHERE guild_id = $1",
        row["id"],
    )
    if state is None:
        return await client.send_message(62023, response)
    tpl, ok = await load_guild_mission_template(state["task_id"])
    if not ok:
        return await client.send_message(62023, response)
    progress = state["progress"]
    if progress > tpl.max_num:
        progress = tpl.max_num
        await store.aexecute(
            "UPDATE guild_weekly_task_states SET progress = $2 WHERE guild_id = $1",
            row["id"], progress,
        )
    response.result = guildChunkResultSuccess
    response.Progress = progress
    return await client.send_message(62023, response)


async def guild_fetch_capital_command_response(buffer: bytes, client) -> tuple:
    request = protobuf.CS_62024()
    request.ParseFromString(buffer)
    response = protobuf.SC_62025(result=guildChunkResultFailure, capital=0)
    if getattr(client, 'commander', None) is None or request.type != 0:
        return await client.send_message(62025, response)
    store = get_default_store()
    row = await store.afetchrow(
        "SELECT g.capital FROM guilds g JOIN guild_members gm ON gm.guild_id = g.id WHERE gm.commander_id = $1",
        client.commander.commander_id,
    )
    if row is None:
        return await client.send_message(62025, response)
    guild_id = row["id"] if "id" in row else None
    response.result = guildChunkResultSuccess
    response.Capital = row["capital"]
    return await client.send_message(62025, response)


async def guild_get_rank_command_response(buffer: bytes, client) -> tuple:
    request = protobuf.CS_62029()
    request.ParseFromString(buffer)
    response = protobuf.SC_62030(list=[])
    if getattr(client, 'commander', None) is None:
        return await client.send_message(62030, response)
    type_id = request.type
    if type_id < 1 or type_id > 3:
        return await client.send_message(62030, response)
    store = get_default_store()
    row = await store.afetchrow(
        "SELECT g.id FROM guilds g JOIN guild_members gm ON gm.guild_id = g.id WHERE gm.commander_id = $1",
        client.commander.commander_id,
    )
    if row is None:
        return await client.send_message(62030, response)
    for period in (1, 2, 3):
        ranks = await store.afetch(
            "SELECT user_id, count FROM guild_member_ranks WHERE guild_id = $1 AND period = $2 AND type_id = $3 ORDER BY count DESC LIMIT 50",
            row["id"], period, type_id,
        )
        users = [protobuf.RANK_USER_INFO(user_id=r["user_id"], count=r["count"]) for r in ranks]
        response.List.append(protobuf.RANK_INFO_P62(period=period, rankuserinfo=users))
    return await client.send_message(62030, response)


async def _consume_resource(client, res_id: int, amount: int) -> bool:
    store = get_default_store()
    row = await store.afetchrow(
        "UPDATE owned_resources SET amount = amount - $1 WHERE commander_id = $2 AND resource_id = $3 AND amount >= $1 RETURNING amount",
        amount, client.commander.commander_id, res_id,
    )
    return row is not None


async def _consume_item(client, item_id: int, amount: int) -> bool:
    store = get_default_store()
    row = await store.afetchrow(
        "UPDATE commander_items SET count = count - $1 WHERE commander_id = $2 AND item_id = $3 AND count >= $1 RETURNING count",
        amount, client.commander.commander_id, item_id,
    )
    return row is not None


def _broadcast(client, _guild_id: int, packet_id: int, message):
    if client is None or getattr(client, 'server', None) is None:
        return
    for connected in client.server.list_clients():
        if connected is None or getattr(connected, 'commander', None) is None:
            continue
        _, _, _ = connected.send_message(packet_id, message)
