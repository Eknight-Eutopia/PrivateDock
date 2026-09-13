from __future__ import annotations

import asyncio
import math
import time
from typing import Optional

from src.connection.client import Client
from src.logger.logger import log_event, LOG_LEVEL_ERROR, LOG_LEVEL_INFO
from src.protobuf import protobuf
from src.orm.chapter_auto import (
    get_chapter_auto_record,
    get_chapter_auto_tickets,
    consume_chapter_auto_tickets,
    refund_chapter_auto_tickets,
    get_active_chapter_auto_battles,
    set_chapter_auto_battles,
    clear_chapter_auto_battles,
    apply_chapter_auto_daily_reset,
    add_chapter_auto_daily_cost_time,
    reduce_chapter_auto_daily_cost_time,
    add_chapter_auto_daily_extra_time,
    add_chapter_auto_oil_bank,
    consume_chapter_auto_oil_bank,
)
from .helpers import (
    load_chapter_auto_statistics,
    load_chapter_auto_time_limits,
)


def handle_start_chapter_auto(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    commander = client.commander
    if commander is None:
        asyncio.create_task(client.send_message(13013, protobuf.SC_13013(result=1)))
        return 0, 13013, None

    payload = protobuf.CS_13012()
    try:
        payload.ParseFromString(buffer)
    except Exception as e:
        asyncio.create_task(client.send_message(13013, protobuf.SC_13013(result=1)))
        return 0, 13013, e

    type_ = payload.type or 1
    chapter_id = payload.id
    num = payload.num
    ticket_num = payload.ticket_num or 0

    if num <= 0 or chapter_id <= 0 or ticket_num < 0 or ticket_num > num:
        asyncio.create_task(client.send_message(13013, protobuf.SC_13013(result=1)))
        return 0, 13013, None

    # Check stage clear record
    rec = get_chapter_auto_record(commander.commander_id, type_, chapter_id)
    if rec is None or rec.seconds <= 0:
        log_event("ChapterAuto", "StartFail", f"stage {chapter_id} not unlocked for commander {commander.commander_id}", LOG_LEVEL_INFO)
        asyncio.create_task(client.send_message(13013, protobuf.SC_13013(result=1)))
        return 0, 13013, None

    stat = load_chapter_auto_statistics(chapter_id)
    if not stat:
        log_event("ChapterAuto", "StartFail", f"statistics missing for chapter {chapter_id}", LOG_LEVEL_ERROR)
        asyncio.create_task(client.send_message(13013, protobuf.SC_13013(result=1)))
        return 0, 13013, None

    time_rate = stat.get("time_rate", 1)
    time_corr = stat.get("time_correction", 0)
    record_seconds = int(math.floor(rec.seconds * time_rate) + time_corr)
    if record_seconds <= 0:
        record_seconds = rec.seconds
    oil_limit = int(stat.get("oil_limit", 0))

    # Daily time limit check
    daily = apply_chapter_auto_daily_reset(commander.commander_id)
    base_limit, _, _ = load_chapter_auto_time_limits()
    max_time = base_limit + (daily.extra_time_max or 0)
    remain_time = max_time - (daily.time_acc or 0)

    # Client condition: GetRemainTime() <= 0 or remain_time <= record_seconds * (num - 1)
    if remain_time <= 0 or remain_time < record_seconds * (num - 1):
        log_event("ChapterAuto", "StartFail", f"not enough time: remain={remain_time}, needed={record_seconds * (num - 1)}", LOG_LEVEL_INFO)
        asyncio.create_task(client.send_message(13013, protobuf.SC_13013(result=1)))
        return 0, 13013, None

    # Check tickets
    if ticket_num > 0:
        tickets = get_chapter_auto_tickets(commander.commander_id, ticket_type=1)
        total_tickets = sum(t.count for t in tickets)
        if total_tickets < ticket_num:
            log_event("ChapterAuto", "StartFail", f"not enough tickets: avail={total_tickets}, need={ticket_num}", LOG_LEVEL_INFO)
            asyncio.create_task(client.send_message(13013, protobuf.SC_13013(result=1)))
            return 0, 13013, None

    # Check oil
    total_oil_needed = oil_limit * ticket_num
    oil_from_bank = min(daily.oil_bank or 0, total_oil_needed)
    oil_from_player = total_oil_needed - oil_from_bank

    if oil_from_player > 0:
        from src.orm.resource import get_owned_resource_amount, consume_resource
        cur_oil = get_owned_resource_amount(commander.commander_id, 2)
        if cur_oil < oil_from_player:
            log_event("ChapterAuto", "StartFail", f"not enough oil: cur={cur_oil}, need={oil_from_player}", LOG_LEVEL_INFO)
            asyncio.create_task(client.send_message(13013, protobuf.SC_13013(result=1)))
            return 0, 13013, None

    # Deduct resources
    if oil_from_bank > 0:
        consume_chapter_auto_oil_bank(commander.commander_id, oil_from_bank)
    if oil_from_player > 0:
        from src.orm.resource import consume_resource
        consume_resource(commander.commander_id, 2, oil_from_player)

    consumed_tickets: list[tuple[int, int]] = []
    if ticket_num > 0:
        consumed_tickets = consume_chapter_auto_tickets(commander.commander_id, 1, ticket_num)

    total_seconds_spent = record_seconds * num
    add_chapter_auto_daily_cost_time(commander.commander_id, total_seconds_spent)

    # Build queue of battles
    ticket_expiries: list[int] = []
    for exp_t, cnt in consumed_tickets:
        ticket_expiries.extend([exp_t] * cnt)

    now_ts = int(time.time())
    battles = []
    response = protobuf.SC_13013()
    response.result = 0

    for i in range(1, num + 1):
        fin_t = now_ts + record_seconds * i
        t_t = ticket_expiries[i - 1] if (i - 1) < len(ticket_expiries) else 0
        b_dict = {
            "type": type_,
            "chapter_id": chapter_id,
            "finish_time": fin_t,
            "ticket_time": t_t,
            "seconds": record_seconds,
        }
        battles.append(b_dict)

        b_proto = protobuf.CHAPTER_AUTO_BATTLE()
        b_proto.type = type_
        b_proto.id = chapter_id
        b_proto.time = fin_t
        b_proto.ticket_time = t_t
        b_proto.seconds = record_seconds
        response.chapter_auto_battle_list.append(b_proto)

    set_chapter_auto_battles(commander.commander_id, battles)

    asyncio.create_task(client.send_message(13013, response))
    return 0, 13013, None


def handle_end_chapter_auto(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    commander = client.commander
    if commander is None:
        asyncio.create_task(client.send_message(13015, protobuf.SC_13015(result=1)))
        return 0, 13015, None

    payload = protobuf.CS_13014()
    try:
        payload.ParseFromString(buffer)
    except Exception as e:
        asyncio.create_task(client.send_message(13015, protobuf.SC_13015(result=1)))
        return 0, 13015, e

    battles = get_active_chapter_auto_battles(commander.commander_id)
    if not battles:
        asyncio.create_task(client.send_message(13015, protobuf.SC_13015(result=1)))
        return 0, 13015, None

    now_ts = int(time.time())
    finished_count = sum(1 for b in battles if b.finish_time <= now_ts)
    claimed_count = min(finished_count, payload.num) if payload.num > 0 else 0

    completed_battles = battles[:claimed_count]
    unfinished_battles = battles[claimed_count:]

    first_b = battles[0]
    stat = load_chapter_auto_statistics(first_b.chapter_id) or {}
    base_class_exp = int(stat.get("base_class_exp", 0))
    drop_expbook = int(stat.get("drop_expbook", 0))
    oil_limit = int(stat.get("oil_limit", 0))
    boss_exp_ids = stat.get("boss_expedition_id", [])
    boss_exp_id = boss_exp_ids[0] if boss_exp_ids else 0

    # Awards for completed battles
    total_class_exp = base_class_exp * claimed_count
    accumulated_drops: list[dict] = []

    for b in completed_battles:
        if b.ticket_time > 0:
            try:
                from src.answer.chapter.helpers import load_chapter_template
                from src.answer.battle_session import _build_chapter_award_drops, _apply_drop_list
                tpl = load_chapter_template(b.chapter_id, 0)
                d = _build_chapter_award_drops(
                    tpl, chapter_id=b.chapter_id, boss_defeated=True, score=3, expedition_id=boss_exp_id
                )
                if d:
                    _apply_drop_list(client, d)
                    for item in d.values():
                        accumulated_drops.append(item)
            except Exception as e:
                log_event("ChapterAuto", "DropError", f"error generating drops for battle: {e}", LOG_LEVEL_ERROR)

            if drop_expbook > 0:
                try:
                    commander.add_item(16501, drop_expbook)
                    accumulated_drops.append({"type": 2, "id": 16501, "number": drop_expbook})
                except Exception:
                    pass

    if total_class_exp > 0:
        try:
            from src.orm.resource import add_resource
            add_resource(commander.commander_id, 10, total_class_exp)
        except Exception as e:
            log_event("ChapterAuto", "ProficiencyError", f"error adding class proficiency: {e}", LOG_LEVEL_ERROR)

    # Refunds for unfinished battles
    unused_seconds = sum(b.seconds for b in unfinished_battles)
    if unused_seconds > 0:
        reduce_chapter_auto_daily_cost_time(commander.commander_id, unused_seconds)

    ticket_refunds: dict[int, int] = {}
    unfinished_ticket_count = 0
    for b in unfinished_battles:
        if b.ticket_time > 0:
            unfinished_ticket_count += 1
            ticket_refunds[b.ticket_time] = ticket_refunds.get(b.ticket_time, 0) + 1

    refunded_oil = oil_limit * unfinished_ticket_count
    if refunded_oil > 0:
        add_chapter_auto_oil_bank(commander.commander_id, refunded_oil)

    refunded_tickets_list: list[protobuf.CHAPTER_AUTO_TICKET] = []
    if ticket_refunds:
        refund_list = list(ticket_refunds.items())
        refund_chapter_auto_tickets(commander.commander_id, 1, refund_list)
        for exp_t, cnt in refund_list:
            t_proto = protobuf.CHAPTER_AUTO_TICKET()
            t_proto.type = 1
            t_proto.time = exp_t
            t_proto.num = cnt
            refunded_tickets_list.append(t_proto)

    clear_chapter_auto_battles(commander.commander_id)

    response = protobuf.SC_13015()
    response.result = 0
    response.oil = refunded_oil
    response.seconds = unused_seconds
    response.world_ap = 0
    response.class_exp = total_class_exp

    for t in refunded_tickets_list:
        response.chapter_auto_ticket_list.append(t)

    # Deduplicate/merge drops for clean proto display
    merged_drops: dict[tuple[int, int], int] = {}
    for d in accumulated_drops:
        key = (d.get("type", 0), d.get("id", 0))
        merged_drops[key] = merged_drops.get(key, 0) + d.get("number", 0)

    for (dtype, did), count in merged_drops.items():
        dp = protobuf.DROPINFO()
        dp.type = dtype
        dp.id = did
        dp.number = count
        response.drop_list.append(dp)

    asyncio.create_task(client.send_message(13015, response))
    return 0, 13015, None


def handle_add_chapter_auto_time(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    commander = client.commander
    if commander is None:
        asyncio.create_task(client.send_message(13017, protobuf.SC_13017(result=1)))
        return 0, 13017, None

    payload = protobuf.CS_13016()
    try:
        payload.ParseFromString(buffer)
    except Exception as e:
        asyncio.create_task(client.send_message(13017, protobuf.SC_13017(result=1)))
        return 0, 13017, e

    t1 = payload.ticket_num_1 or 0
    t3 = payload.ticket_num_3 or 0

    if t1 <= 0 and t3 <= 0:
        asyncio.create_task(client.send_message(13017, protobuf.SC_13017(result=1)))
        return 0, 13017, None

    consumed1: list[tuple[int, int]] = []
    if t1 > 0:
        consumed1 = consume_chapter_auto_tickets(commander.commander_id, 1, t1)
        if not consumed1:
            asyncio.create_task(client.send_message(13017, protobuf.SC_13017(result=1)))
            return 0, 13017, None

    consumed3: list[tuple[int, int]] = []
    if t3 > 0:
        consumed3 = consume_chapter_auto_tickets(commander.commander_id, 3, t3)
        if not consumed3:
            if consumed1:
                refund_chapter_auto_tickets(commander.commander_id, 1, consumed1)
            asyncio.create_task(client.send_message(13017, protobuf.SC_13017(result=1)))
            return 0, 13017, None

    _, sec1, sec3 = load_chapter_auto_time_limits()
    added_seconds = t1 * sec1 + t3 * sec3
    add_chapter_auto_daily_extra_time(commander.commander_id, added_seconds)

    response = protobuf.SC_13017()
    response.result = 0
    asyncio.create_task(client.send_message(13017, response))
    return 0, 13017, None
