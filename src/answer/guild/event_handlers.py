import json

from sqlalchemy import select, text

from src.answer.guild.helpers import (
    now_unix, guildEventResultSuccess, guildEventResultFailure,
    guildEventResultNoActiveOperation,
    guildChunkResultSuccess, active_guild_event_context, load_game_set_uint, load_guild_operation_template,
    build_operation_response, build_event_base,
    default_guild_boss_event,
)
from src.db.session import get_session
from src.db.store import NotFoundError
from src.protobuf import protobuf
from src.orm.guild_core import Guild
from src.orm.guild_membership import GuildMembership
from src.orm.guild_event_operation import (
    GuildOperationState, GuildOperationEvent, GuildReport, GuildReportNode, GuildOperationParticipant,
)
from src.orm.guild_assault_fleet import (
    GuildAssaultFleetSlot, GuildAssaultRecommendation, GuildBossMissionFleet,
)
from src.orm.guild_operation_boss_state import (
    GuildOperationBossState, GuildOperationBossRank,
)
from src.orm.owned_ship import OwnedShip


async def guild_active_event_command_response(buffer: bytes, client) -> tuple:
    payload = protobuf.CS_61001()
    payload.ParseFromString(buffer)
    response = protobuf.SC_61002(result=guildEventResultFailure)
    if getattr(client, 'commander', None) is None or payload.chapter_id == 0:
        return await client.send_message(61002, response)
    async with get_session() as session:
        result = await session.execute(
            select(Guild.id, Guild.level, GuildMembership.duty)
            .join(GuildMembership, GuildMembership.guild_id == Guild.id)
            .where(GuildMembership.commander_id == client.commander.commander_id)
        )
        row = result.fetchone()
        if row is None or row.duty not in (1, 2):
            return await client.send_message(61002, response)
        chapter = await load_guild_operation_template(payload.chapter_id)
        if chapter is None:
            return await client.send_message(61002, response)
        if row.level < chapter.unlock_guild_level:
            return await client.send_message(61002, response)
        duration = await load_game_set_uint("operation_duration_time")
        now = now_unix()
        session.add(GuildOperationState(
            guild_id=row.id,
            chapter_id=payload.chapter_id,
            start_time=now,
            end_time=now + duration,
        ))
        await session.commit()
    response.result = guildEventResultSuccess
    return await client.send_message(61002, response)


async def get_my_assault_fleet_command_response(_buffer: bytes, client) -> tuple:
    response = protobuf.SC_61010(result=guildEventResultFailure)
    if getattr(client, 'commander', None) is None:
        return await client.send_message(61010, response)
    try:
        ctx = await active_guild_event_context(client.commander.commander_id)
    except NotFoundError:
        return await client.send_message(61010, response)
    async with get_session() as session:
        result = await session.execute(
            select(GuildAssaultFleetSlot).where(
                GuildAssaultFleetSlot.guild_id == ctx.guild_id,
                GuildAssaultFleetSlot.commander_id == client.commander.commander_id,
            )
        )
        slots = result.scalars().all()
        person_ships = []
        for slot in slots:
            ship = await session.get(OwnedShip, slot.ship_id)
            if ship:
                person_ships.append(protobuf.SHIPID_POS_INFO(
                    pos=slot.pos,
                    ship=protobuf.SHIPINFO(id=ship.id, template_id=ship.ship_id, level=ship.level, exp=ship.exp),
                    last_time=slot.last_time,
                ))
    response.result = guildEventResultSuccess
    response.PersonShips = person_ships
    return await client.send_message(61010, response)


async def guild_get_activation_event_command_response(buffer: bytes, client) -> tuple:
    payload = protobuf.CS_61005()
    payload.ParseFromString(buffer)
    if getattr(client, 'commander', None) is None:
        return await client.send_message(61006, protobuf.SC_61006(result=guildEventResultNoActiveOperation))
    async with get_session() as session:
        result = await session.execute(
            select(GuildOperationState)
            .join(GuildMembership, GuildMembership.guild_id == GuildOperationState.guild_id)
            .where(
                GuildMembership.commander_id == client.commander.commander_id,
                GuildOperationState.end_time > now_unix(),
            )
            .order_by(GuildOperationState.start_time.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return await client.send_message(61006, protobuf.SC_61006(result=guildEventResultNoActiveOperation))
        response = protobuf.SC_61006(result=guildEventResultSuccess, operation=build_operation_response(row))
    return await client.send_message(61006, response)


async def guild_get_assault_fleet_command_response(_buffer: bytes, client) -> tuple:
    response = protobuf.SC_61012(result=guildEventResultFailure)
    if getattr(client, 'commander', None) is None:
        return await client.send_message(61012, response)
    try:
        ctx = await active_guild_event_context(client.commander.commander_id)
    except NotFoundError:
        return await client.send_message(61012, response)
    async with get_session() as session:
        members_result = await session.execute(
            select(GuildMembership.commander_id).where(GuildMembership.guild_id == ctx.guild_id)
        )
        members = members_result.fetchall()
        slots_result = await session.execute(
            select(GuildAssaultFleetSlot).where(GuildAssaultFleetSlot.guild_id == ctx.guild_id)
        )
        all_slots = slots_result.scalars().all()
        slots_by_cid = {}
        for slot in all_slots:
            slots_by_cid.setdefault(slot.commander_id, []).append(slot)
        ships = []
        for member in members:
            member_slots = slots_by_cid.get(member.commander_id, [])
            member_ships = []
            for slot in member_slots:
                ship_obj = await session.get(OwnedShip, slot.ship_id)
                if ship_obj and ship_obj.owner_id == member.commander_id:
                    member_ships.append(protobuf.SHIPINFO(id=ship_obj.id, template_id=ship_obj.ship_id, level=ship_obj.level, exp=ship_obj.exp))
            ships.append(protobuf.TEAM_CHUNK(user_id=member.commander_id, ships=member_ships))
        recommends_result = await session.execute(
            select(GuildAssaultRecommendation).where(GuildAssaultRecommendation.guild_id == ctx.guild_id)
        )
        recommends = [
            protobuf.TEAM_CELL(user_id=r.commander_id, ship_id=r.ship_id)
            for r in recommends_result.scalars().all()
        ]
    response.result = guildEventResultSuccess
    response.Ships = ships
    response.Recommends = recommends
    return await client.send_message(61012, response)


async def guild_get_boss_info_command_response(buffer: bytes, client) -> tuple:
    payload = protobuf.CS_61027()
    payload.ParseFromString(buffer)
    response = protobuf.SC_61028(result=guildEventResultFailure, boss_event=default_guild_boss_event())
    if getattr(client, 'commander', None) is None:
        response.result = guildEventResultNoActiveOperation
        return await client.send_message(61028, response)
    if payload.type != 0:
        return await client.send_message(61028, response)
    async with get_session() as session:
        result = await session.execute(
            select(GuildOperationState)
            .join(GuildMembership, GuildMembership.guild_id == GuildOperationState.guild_id)
            .where(
                GuildMembership.commander_id == client.commander.commander_id,
                GuildOperationState.end_time > now_unix(),
            )
            .order_by(GuildOperationState.start_time.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            response.result = guildEventResultNoActiveOperation
            return await client.send_message(61028, response)
        boss_result = await session.execute(
            select(GuildOperationBossState).where(
                GuildOperationBossState.guild_id == row.guild_id,
                GuildOperationBossState.operation_id == row.chapter_id,
            )
        )
        boss = boss_result.scalar_one_or_none()
        if boss is None:
            response.result = guildEventResultSuccess
            return await client.send_message(61028, response)
    response.result = guildEventResultSuccess
    response.BossEvent = protobuf.EVENT_BOSS(boss_id=boss.boss_id, damage=boss.damage, hp=boss.hp)
    return await client.send_message(61028, response)


async def guild_get_boss_rank_command_response(buffer: bytes, client) -> tuple:
    payload = protobuf.CS_61029()
    payload.ParseFromString(buffer)
    response = protobuf.SC_61030(list=[])
    if getattr(client, 'commander', None) is None or payload.type != 0:
        return await client.send_message(61030, response)
    async with get_session() as session:
        state_result = await session.execute(
            select(GuildOperationState)
            .join(GuildMembership, GuildMembership.guild_id == GuildOperationState.guild_id)
            .where(
                GuildMembership.commander_id == client.commander.commander_id,
                GuildOperationState.end_time > now_unix(),
            )
            .order_by(GuildOperationState.start_time.desc())
            .limit(1)
        )
        row = state_result.scalar_one_or_none()
        if row is None:
            return await client.send_message(61030, response)
        boss_result = await session.execute(
            select(GuildOperationBossState).where(
                GuildOperationBossState.guild_id == row.guild_id,
                GuildOperationBossState.operation_id == row.chapter_id,
            )
        )
        boss = boss_result.scalar_one_or_none()
        if boss is None:
            return await client.send_message(61030, response)
        ranks_result = await session.execute(
            select(GuildOperationBossRank).where(
                GuildOperationBossRank.guild_id == row.guild_id,
                GuildOperationBossRank.operation_id == row.chapter_id,
                GuildOperationBossRank.boss_id == boss.boss_id,
            ).order_by(GuildOperationBossRank.damage.desc())
        )
        ranks = ranks_result.scalars().all()
    response.List = [protobuf.RANK_INFO_P61(user_id=r.user_id, damage=r.damage) for r in ranks]
    return await client.send_message(61030, response)


async def guild_get_report_rank_command_response(buffer: bytes, client) -> tuple:
    payload = protobuf.CS_61037()
    payload.ParseFromString(buffer)
    response = protobuf.SC_61038(list=[])
    if getattr(client, 'commander', None) is None or payload.id == 0:
        return await client.send_message(61038, response)
    async with get_session() as session:
        result = await session.execute(
            select(Guild.id)
            .join(GuildMembership, GuildMembership.guild_id == Guild.id)
            .where(GuildMembership.commander_id == client.commander.commander_id)
        )
        row = result.fetchone()
        if row is None:
            return await client.send_message(61038, response)
        ranks_result = await session.execute(
            text("SELECT user_id, damage FROM guild_report_ranks WHERE guild_id = :gid AND report_id = :rid ORDER BY damage DESC"),
            {"gid": row.id, "rid": payload.id},
        )
        rank_rows = ranks_result.fetchall()
    response.List = [protobuf.RANK_INFO_P61(user_id=r[0], damage=r[1]) for r in rank_rows]
    return await client.send_message(61038, response)


async def guild_get_reports_command_response(buffer: bytes, client) -> tuple:
    payload = protobuf.CS_61017()
    payload.ParseFromString(buffer)
    if getattr(client, 'commander', None) is None:
        return await client.send_message(61018, protobuf.SC_61018(reports=[]))
    async with get_session() as session:
        result = await session.execute(
            select(Guild.id)
            .join(GuildMembership, GuildMembership.guild_id == Guild.id)
            .where(GuildMembership.commander_id == client.commander.commander_id)
        )
        row = result.fetchone()
        if row is None:
            return await client.send_message(61018, protobuf.SC_61018(reports=[]))
        reports_result = await session.execute(
            select(GuildReport).where(
                GuildReport.guild_id == row.id,
                GuildReport.id > payload.index,
            ).order_by(GuildReport.id.desc()).limit(50)
        )
        report_rows = reports_result.scalars().all()
        proto_reports = []
        for r in report_rows:
            nodes_result = await session.execute(
                select(GuildReportNode).where(
                    GuildReportNode.guild_id == row.id,
                    GuildReportNode.report_id == r.id,
                ).order_by(GuildReportNode.node_id.asc())
            )
            node_rows = nodes_result.scalars().all()
            nodes = [protobuf.REPORT_NODE(id=n.node_id, status=n.status) for n in node_rows]
            proto_reports.append(protobuf.REPORT(
                id=r.id, event_id=r.event_id, event_type=r.event_type,
                score=r.score, nodes=nodes, status=r.status,
            ))
    return await client.send_message(61018, protobuf.SC_61018(reports=proto_reports))


async def guild_join_event_command_response(buffer: bytes, client) -> tuple:
    payload = protobuf.CS_61031()
    payload.ParseFromString(buffer)
    response = protobuf.SC_61032(result=guildEventResultFailure)
    if getattr(client, 'commander', None) is None or payload.type != 0:
        return await client.send_message(61032, response)
    max_join = await load_game_set_uint("efficiency_param_times")
    liveness_gain = await load_game_set_uint("operation_event_guild_active")
    now = now_unix()
    async with get_session() as session:
        membership_result = await session.execute(
            select(GuildMembership).where(
                GuildMembership.commander_id == client.commander.commander_id,
            )
        )
        membership = membership_result.scalar_one_or_none()
        if membership is None:
            return await client.send_message(61032, response)
        state_result = await session.execute(
            select(GuildOperationState.end_time).where(
                GuildOperationState.guild_id == membership.guild_id,
            )
        )
        end_time = state_result.scalar_one_or_none()
        if end_time is None or end_time <= now:
            return await client.send_message(61032, response)
        participant_result = await session.execute(
            select(GuildOperationParticipant).where(
                GuildOperationParticipant.guild_id == membership.guild_id,
                GuildOperationParticipant.commander_id == client.commander.commander_id,
            )
        )
        participant = participant_result.scalar_one_or_none()
        if participant is None:
            session.add(GuildOperationParticipant(
                guild_id=membership.guild_id,
                commander_id=client.commander.commander_id,
                join_times=1,
                is_participant=1,
            ))
        else:
            current_join = participant.join_times
            if current_join >= max_join:
                await session.execute(
                    text("UPDATE guild_user_infos SET extra_operation = extra_operation - 1 WHERE commander_id = :cid AND extra_operation > 0"),
                    {"cid": client.commander.commander_id},
                )
            else:
                participant.join_times = current_join + 1
                participant.is_participant = 1
        membership.liveness = membership.liveness + liveness_gain
        await session.commit()
    response.result = guildEventResultSuccess
    return await client.send_message(61032, response)


async def guild_join_mission_command_response(buffer: bytes, client) -> tuple:
    payload = protobuf.CS_61007()
    payload.ParseFromString(buffer)
    response = protobuf.SC_61008(result=guildEventResultFailure)
    if getattr(client, 'commander', None) is None or payload.event_tid == 0:
        return await client.send_message(61008, response)
    ship_ids = list(payload.ship_ids)
    if len(ship_ids) == 0 or len(ship_ids) > 4:
        return await client.send_message(61008, response)
    async with get_session() as session:
        guild_result = await session.execute(
            select(Guild.id)
            .join(GuildMembership, GuildMembership.guild_id == Guild.id)
            .where(GuildMembership.commander_id == client.commander.commander_id)
        )
        row = guild_result.fetchone()
        if row is None:
            return await client.send_message(61008, response)
        event_result = await session.execute(
            select(GuildOperationEvent).where(
                GuildOperationEvent.guild_id == row.id,
                GuildOperationEvent.event_tid == payload.event_tid,
            )
        )
        event = event_result.scalar_one_or_none()
        if event is None or event.completed:
            return await client.send_message(61008, response)
        seen = set()
        for sid in ship_ids:
            if sid == 0 or sid in seen:
                return await client.send_message(61008, response)
            seen.add(sid)
            ship_obj = await session.get(OwnedShip, sid)
            if ship_obj is None or ship_obj.owner_id != client.commander.commander_id:
                return await client.send_message(61008, response)
        person = json.dumps([{"page_id": 1, "ship_ids": list(ship_ids)}])
        event_result = await session.execute(
            text("UPDATE guild_operation_events SET personship = :ps, formation_time = :ft WHERE guild_id = :gid AND event_tid = :etid"),
            {"gid": row.id, "etid": payload.event_tid, "ps": person, "ft": now_unix()},
        )
        await session.commit()
    response.result = guildEventResultSuccess
    return await client.send_message(61008, response)


async def guild_refresh_assault_recommendations_command_response(buffer: bytes, client) -> tuple:
    payload = protobuf.CS_61035()
    payload.ParseFromString(buffer)
    response = protobuf.SC_61036(recommends=[])
    if getattr(client, 'commander', None) is None or payload.type != 0:
        return await client.send_message(61036, response)
    try:
        ctx = await active_guild_event_context(client.commander.commander_id)
    except NotFoundError:
        return await client.send_message(61036, response)
    async with get_session() as session:
        result = await session.execute(
            select(GuildAssaultRecommendation).where(GuildAssaultRecommendation.guild_id == ctx.guild_id)
        )
        rows = result.scalars().all()
    response.Recommends = [protobuf.TEAM_CELL(user_id=r.commander_id, ship_id=r.ship_id) for r in rows]
    return await client.send_message(61036, response)


async def guild_refresh_mission_command_response(buffer: bytes, client) -> tuple:
    payload = protobuf.CS_61023()
    payload.ParseFromString(buffer)
    response = protobuf.SC_61024(result=guildEventResultFailure)
    if getattr(client, 'commander', None) is None or payload.event_tid == 0:
        return await client.send_message(61024, response)
    async with get_session() as session:
        state_result = await session.execute(
            select(GuildOperationState)
            .join(GuildMembership, GuildMembership.guild_id == GuildOperationState.guild_id)
            .where(
                GuildMembership.commander_id == client.commander.commander_id,
                GuildOperationState.end_time > now_unix(),
            )
            .order_by(GuildOperationState.start_time.desc())
            .limit(1)
        )
        row = state_result.scalar_one_or_none()
        if row is None:
            return await client.send_message(61024, response)
        events_result = await session.execute(
            select(GuildOperationEvent).where(GuildOperationEvent.guild_id == row.guild_id)
        )
        event_rows = events_result.scalars().all()
        event_obj = None
        completed = False
        for erow in event_rows:
            if erow.event_tid == payload.event_tid:
                event_obj = erow
                completed = erow.completed
                break
        if event_obj is None:
            return await client.send_message(61024, response)
        await session.execute(
            text("UPDATE guild_operation_events SET formation_time = :ft, personship = NULL WHERE guild_id = :gid AND event_tid = :etid"),
            {"gid": row.guild_id, "etid": payload.event_tid, "ft": now_unix()},
        )
        await session.commit()
    response.result = guildEventResultSuccess
    if completed:
        response.completed_info = protobuf.EVENT_BASE_COMPLETED(event_id=event_obj.event_tid, position=event_obj.position)
    else:
        response.event_info = build_event_base({
            "event_tid": event_obj.event_tid,
            "position": event_obj.position,
            "start_time": event_obj.start_time,
            "complete_time": event_obj.complete_time,
            "efficiency": event_obj.efficiency,
            "completed": event_obj.completed,
            "ship_in_event": event_obj.shipinevent,
            "attr_acc_list": event_obj.attr_acc_list,
            "attr_count_list": event_obj.attr_count_list,
            "event_nodes": event_obj.eventnodes,
            "person_ship": event_obj.personship,
            "formation_time": event_obj.formation_time,
        })
    return await client.send_message(61024, response)


async def guild_update_assault_fleet_command_response(buffer: bytes, client) -> tuple:
    payload = protobuf.CS_61003()
    payload.ParseFromString(buffer)
    response = protobuf.SC_61004(result=guildEventResultFailure)
    if getattr(client, 'commander', None) is None:
        return await client.send_message(61004, response)
    try:
        ctx = await active_guild_event_context(client.commander.commander_id)
    except NotFoundError:
        return await client.send_message(61004, response)
    async with get_session() as session:
        boss_row = (await session.execute(
            select(GuildBossMissionFleet).where(
                GuildBossMissionFleet.guild_id == ctx.guild_id,
                GuildBossMissionFleet.operation_id == ctx.operation_id,
            ).limit(1)
        )).scalar_one_or_none()
        if boss_row:
            return await client.send_message(61004, response)
        ship_updates = list(payload.ship_ids)
        if len(ship_updates) == 0 or len(ship_updates) > 2:
            return await client.send_message(61004, response)
        used_positions = set()
        used_ships = set()
        upserts = []
        for entry in ship_updates:
            if entry is None:
                return await client.send_message(61004, response)
            pos = entry.pos
            ship_id = entry.ship_id
            if pos < 1 or pos > 2 or ship_id == 0 or pos in used_positions or ship_id in used_ships:
                return await client.send_message(61004, response)
            ship_obj = await session.get(OwnedShip, ship_id)
            if ship_obj is None or ship_obj.owner_id != client.commander.commander_id:
                return await client.send_message(61004, response)
            used_positions.add(pos)
            used_ships.add(ship_id)
            upserts.append((pos, ship_id))
        now = now_unix()
        for pos, ship_id in upserts:
            slot_result = await session.execute(
                select(GuildAssaultFleetSlot).where(
                    GuildAssaultFleetSlot.guild_id == ctx.guild_id,
                    GuildAssaultFleetSlot.commander_id == client.commander.commander_id,
                    GuildAssaultFleetSlot.pos == pos,
                )
            )
            slot = slot_result.scalar_one_or_none()
            if slot:
                cooldown = await load_game_set_uint("operation_assault_team_cd")
                if now < slot.last_time + cooldown:
                    return await client.send_message(61004, response)
        for pos, ship_id in upserts:
            await session.execute(
                text("""
                    INSERT INTO guild_assault_fleet_slots (guild_id, commander_id, pos, ship_id, last_time, updated_at)
                    VALUES (:gid, :cid, :pos, :sid, :lt, CURRENT_TIMESTAMP)
                    ON CONFLICT (guild_id, commander_id, pos)
                    DO UPDATE SET ship_id = EXCLUDED.ship_id, last_time = EXCLUDED.last_time, updated_at = CURRENT_TIMESTAMP
                """),
                {"gid": ctx.guild_id, "cid": client.commander.commander_id, "pos": pos, "sid": ship_id, "lt": now},
            )
        await session.commit()
    response.result = guildEventResultSuccess
    return await client.send_message(61004, response)


async def guild_update_boss_mission_fleet_command_response(buffer: bytes, client) -> tuple:
    payload = protobuf.CS_61013()
    payload.ParseFromString(buffer)
    response = protobuf.SC_61014(result=guildEventResultFailure)
    if getattr(client, 'commander', None) is None:
        return await client.send_message(61014, response)
    try:
        ctx = await active_guild_event_context(client.commander.commander_id)
    except NotFoundError:
        return await client.send_message(61014, response)
    fleets = list(payload.fleet)
    if not fleets:
        return await client.send_message(61014, response)
    async with get_session() as session:
        members_result = await session.execute(
            select(GuildMembership.commander_id).where(GuildMembership.guild_id == ctx.guild_id)
        )
        member_set = {r.commander_id for r in members_result.fetchall()}
        for fleet in fleets:
            if fleet is None:
                return await client.send_message(61014, response)
            fleet_id = fleet.fleet_id
            if fleet_id not in (1, 11):
                return await client.send_message(61014, response)
            ships = list(fleet.ships)
            max_ships = 6 if fleet_id == 1 else 3
            if len(ships) > max_ships:
                return await client.send_message(61014, response)
            for ship in ships:
                if ship is None:
                    return await client.send_message(61014, response)
                user_id = ship.user_id
                ship_id = ship.ship_id
                if user_id == 0 or ship_id == 0 or user_id not in member_set:
                    return await client.send_message(61014, response)
                slot_result = await session.execute(
                    select(GuildAssaultFleetSlot).where(
                        GuildAssaultFleetSlot.guild_id == ctx.guild_id,
                        GuildAssaultFleetSlot.commander_id == user_id,
                        GuildAssaultFleetSlot.ship_id == ship_id,
                    ).limit(1)
                )
                slot_row = slot_result.scalar_one_or_none()
                if slot_row is None:
                    return await client.send_message(61014, response)
    response.result = guildEventResultSuccess
    return await client.send_message(61014, response)


async def guild_update_node_anim_flag_command_response(buffer: bytes, client) -> tuple:
    payload = protobuf.CS_61025()
    payload.ParseFromString(buffer)
    response = protobuf.SC_61026(result=guildChunkResultSuccess)
    return await client.send_message(61026, response)


async def mark_assault_ship_recommend_command_response(buffer: bytes, client) -> tuple:
    payload = protobuf.CS_61033()
    payload.ParseFromString(buffer)
    response = protobuf.SC_61034(result=guildEventResultFailure)
    if getattr(client, 'commander', None) is None:
        return await client.send_message(61034, response)
    try:
        ctx = await active_guild_event_context(client.commander.commander_id)
    except NotFoundError:
        return await client.send_message(61034, response)
    ship_id = payload.ship_id
    if ship_id == 0:
        return await client.send_message(61034, response)
    async with get_session() as session:
        ship_obj = await session.get(OwnedShip, ship_id)
        if ship_obj is None or ship_obj.owner_id != client.commander.commander_id:
            return await client.send_message(61034, response)
        await session.execute(
            text("""
                INSERT INTO guild_assault_recommendations (guild_id, commander_id, ship_id)
                VALUES (:gid, :cid, :sid)
                ON CONFLICT (guild_id, commander_id)
                DO UPDATE SET ship_id = EXCLUDED.ship_id
            """),
            {"gid": ctx.guild_id, "cid": client.commander.commander_id, "sid": ship_id},
        )
        recommends_result = await session.execute(
            select(GuildAssaultRecommendation).where(GuildAssaultRecommendation.guild_id == ctx.guild_id)
        )
        await session.commit()
    response.result = guildEventResultSuccess
    response.Recommends = [protobuf.TEAM_CELL(user_id=r.commander_id, ship_id=r.ship_id) for r in recommends_result.scalars().all()]
    return await client.send_message(61034, response)


async def guild_fetch_boss_command_response(_buffer: bytes, client) -> tuple:
    return await client.send_message(61016, protobuf.SC_61016(result=guildEventResultSuccess))
