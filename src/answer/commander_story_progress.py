from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.protobuf import protobuf
from src.orm.remaster import get_or_create_remaster_state, apply_remaster_daily_reset
from src.orm import list_chapter_progress


def handle_commander_story_progress(
    _buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    commander_id = client.commander.commander_id

    response = protobuf.SC_13001()
    response.oil = 0
    response.time_acc = 0
    response.extra_time_max = 0
    react = protobuf.REACTCHAPTER_INFO()
    react.count = 0
    react.active_timestamp = 0
    react.active_id = 0
    react.daily_count = 0

    try:
        state = get_or_create_remaster_state(commander_id)
        if state:
            react.count = state.ticket_count or 0
            ts = state.last_daily_reset_at
            if ts:
                react.active_timestamp = int(ts.timestamp())
            react.active_id = state.active_chapter_id or 0
            react.daily_count = state.daily_count or 0
    except Exception:
        pass

    try:
        rows = list_chapter_progress(commander_id)
        for r in rows:
            ch_id = r.chapter_id
            progress_val = r.progress
            kill_boss = r.kill_boss_count
            kill_enemy = r.kill_enemy_count
            take_box = r.take_box_count
            defeat_count = r.defeat_count
            today_defeat = r.today_defeat_count
            pass_count = r.pass_count

            if pass_count >= 3:
                try:
                    from src.answer.chapter import load_chapter_template
                    template = load_chapter_template(ch_id, 0)
                    if template:
                        num1 = template.get("num1", 0) if isinstance(template, dict) else getattr(template, "num1", 0)
                        num2 = template.get("num2", 0) if isinstance(template, dict) else getattr(template, "num2", 0)
                        num3 = template.get("num3", 0) if isinstance(template, dict) else getattr(template, "num3", 0)
                        if num1 > 0 and kill_boss < num1:
                            kill_boss = num1
                        if num2 > 0 and kill_enemy < num2:
                            kill_enemy = num2
                        if num3 > 0 and take_box < num3:
                            take_box = num3
                except Exception:
                    pass

            ch = protobuf.CHAPTERINFO()
            ch.id = ch_id
            ch.progress = progress_val
            ch.kill_boss_count = kill_boss
            ch.kill_enemy_count = kill_enemy
            ch.take_box_count = take_box
            ch.defeat_count = defeat_count
            ch.today_defeat_count = today_defeat
            ch.pass_count = pass_count
            response.chapter_list.append(ch)
    except Exception:
        pass

    try:
        fresh = apply_remaster_daily_reset(commander_id)
        if fresh:
            react.count = fresh.ticket_count or 0
            ts = fresh.last_daily_reset_at
            if ts:
                react.active_timestamp = int(ts.timestamp())
            react.daily_count = fresh.daily_count or 0
    except Exception:
        pass

    response.react_chapter.CopyFrom(react)

    try:
        from src.orm.chapter_auto import (
            get_chapter_auto_records,
            get_chapter_auto_tickets,
            get_active_chapter_auto_battles,
            apply_chapter_auto_daily_reset,
        )
        daily = apply_chapter_auto_daily_reset(commander_id)
        if daily:
            response.oil = daily.oil_bank or 0
            response.time_acc = daily.time_acc or 0
            response.extra_time_max = daily.extra_time_max or 0

        for r in get_chapter_auto_records(commander_id):
            rec_proto = protobuf.CHAPTER_AUTO_RECORD()
            rec_proto.type = r.type
            rec_proto.id = r.chapter_id
            rec_proto.seconds = r.seconds
            response.chapter_auto_record_list.append(rec_proto)

        for t in get_chapter_auto_tickets(commander_id, ticket_type=1):
            t_proto = protobuf.CHAPTER_AUTO_TICKET()
            t_proto.type = t.ticket_type
            t_proto.time = t.expire_time
            t_proto.num = t.count
            response.chapter_auto_ticket_list.append(t_proto)

        for b in get_active_chapter_auto_battles(commander_id):
            b_proto = protobuf.CHAPTER_AUTO_BATTLE()
            b_proto.type = b.type
            b_proto.id = b.chapter_id
            b_proto.time = b.finish_time
            b_proto.ticket_time = b.ticket_time
            b_proto.seconds = b.seconds
            response.chapter_auto_battle_list.append(b_proto)
    except Exception:
        pass

    try:
        from src.orm.chapter_elite_fleet import list_chapter_elite_fleets_sync
        elite_fleets = list_chapter_elite_fleets_sync(commander_id)
        for f in elite_fleets:
            fleet_proto = response.fleet_list.add()
            fleet_proto.id = f["formation_id"]
            for t in f.get("main_team", []):
                tm = fleet_proto.main_team.add()
                tm.id = t.get("id", 0)
                tm.ship_list.extend(t.get("ship_list", []))
                tm.commander_main = t.get("commander_main", 0)
                tm.commander_sub = t.get("commander_sub", 0)
            for t in f.get("submarine_team", []):
                tm = fleet_proto.submarine_team.add()
                tm.id = t.get("id", 0)
                tm.ship_list.extend(t.get("ship_list", []))
                tm.commander_main = t.get("commander_main", 0)
                tm.commander_sub = t.get("commander_sub", 0)
            for t in f.get("support_team", []):
                tm = fleet_proto.support_team.add()
                tm.id = t.get("id", 0)
                tm.ship_list.extend(t.get("ship_list", []))
                tm.commander_main = t.get("commander_main", 0)
                tm.commander_sub = t.get("commander_sub", 0)
    except Exception:
        pass

    data = response.SerializeToString()
    header = generate_packet_header(13001, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 13001, None
