import json
import time

from src.answer.educate.helpers import (
    educateResultOK, educateResultFailed,
    educateFlagHomeEventBase, educateFlagSpecialEventBase,
    educateFlagDiscountBase, educateFlagTargetAwardBase,
    educateUnsupportedTypeResult, educatePlanValidationFailedResult,
    legacyEducateResultOK, legacyEducateResultFailure,
    childSiteCategory, childSiteOptionCategory,
    childSiteOptionBranchCategory, childTaskCategory,
    childTargetSetCategory, childEndingCategory, secretarySpecialShipCategory,
    EducateShopGoodsState, load_educate_special_events, load_educate_events,
    load_educate_shop_configs, load_educate_target_and_task_configs,
    load_educate_site_options, load_legacy_config_by_id, legacy_config_exists,
    load_legacy_child_data, legacy_site_has_option,
    has_educate_flag, set_educate_flag,
    to_child_drop, apply_educate_child_drop,
    choose_educate_target_id, ensure_educate_shop_state,
    populate_educate_snapshot,
    is_valid_legacy_call_name, build_legacy_child_drop,
    get_or_create_legacy_educate_state, save_legacy_educate_state,
    bool_to_uint32, append_unique_uint32, contains_uint32,
    educate_flag_id,
)
from src.config.config import current as get_config
from src.db.store import get_default_store
from src.protobuf import protobuf


# ── EducateRequest (27001) ──

async def EducateRequest(_buffer: bytes, client) -> tuple:
    state = await get_or_create_legacy_educate_state(client.commander.commander_id)
    if state is None:
        response = protobuf.SC_27001(
            result=0,
            child=protobuf.CHILD_INFO(
                tid=1, mood=0, money=0, site_number=0,
                cur_time=protobuf.CHILD_TIME(month=2, day=7, week=4),
                favor=protobuf.CHILD_FAVOR(lv=0, exp=0),
                attrs=[], items=[], plan_history=[], memorys=[],
                plans=[], polaroids=[], target=0, tasks=[],
                realized_wish=[], buffs=[], user_name="",
                spec_events=[], can_trigger_home_event=0, home_events=[],
                discount_event_id=[], shop=[], option_records=[],
                favor_award_history=[], is_ending=0, new_game_plus_count=0,
                had_target_stage_award=0, had_adjustment=0,
                is_special_secretary_valid=0, ending_buy_count=0,
                memory_buy_count=0, polaroid_buy_count=0,
            ),
        )
        return await client.send_message(27001, response)

    attrs = [
        protobuf.CHILD_ATTR(id=201, val=state["attrs"].get("201", 0)),
        protobuf.CHILD_ATTR(id=202, val=state["attrs"].get("202", 0)),
        protobuf.CHILD_ATTR(id=203, val=state["attrs"].get("203", 0)),
    ]
    tasks = []
    for task_id, progress in state["task_progress"].items():
        tasks.append(protobuf.CHILD_TASK(id=int(task_id), progress=int(progress)))
    option_records = []
    for option_id, count in state["option_records"].items():
        option_records.append(protobuf.CHILD_OPTION_RECORD(id=int(option_id), count=int(count)))

    response = protobuf.SC_27001(
        result=0,
        child=protobuf.CHILD_INFO(
            tid=1, mood=0, money=0, site_number=0,
            cur_time=protobuf.CHILD_TIME(month=2, day=7, week=4),
            favor=protobuf.CHILD_FAVOR(lv=state["favor_lv"], exp=state["favor_exp"]),
            attrs=attrs,
            items=[],
            plan_history=[],
            memorys=[],
            plans=[],
            polaroids=[],
            target=state["target_id"],
            tasks=tasks,
            realized_wish=[],
            buffs=[],
            user_name=state["call_name"],
            spec_events=[],
            can_trigger_home_event=0,
            home_events=[],
            discount_event_id=[],
            shop=[],
            option_records=option_records,
            favor_award_history=[],
            is_ending=0,
            new_game_plus_count=0,
            had_target_stage_award=0,
            had_adjustment=bool_to_uint32(state["had_adjustment"]),
            is_special_secretary_valid=0,
            ending_buy_count=0,
            memory_buy_count=0,
            polaroid_buy_count=0,
        ),
    )
    if client.commander is not None:
        err = await populate_educate_snapshot(client.commander.commander_id, response.child)
        if err:
            return 0, 27001, err
    return await client.send_message(27001, response)


# ── EducateExecutePlans (27003) ──

async def EducateExecutePlans(buffer: bytes, client) -> tuple:
    request = protobuf.CS_27002()
    request.ParseFromString(buffer)
    response = protobuf.SC_27003(result=0, plan_results=[], events=[])
    if request.type != 1:
        response.result = educateUnsupportedTypeResult
    return await client.send_message(27003, response)


# ── EducateGetEvents (27015) ──

async def EducateGetEvents(buffer: bytes, client) -> tuple:
    request = protobuf.CS_27014()
    request.ParseFromString(buffer)
    response = protobuf.SC_27015(result=educateResultOK, events=[])
    if client.commander is None or request.type != 0:
        response.result = educateResultFailed
        return await client.send_message(27015, response)
    special_events = await load_educate_special_events()
    events = []
    for row in special_events.values():
        if row.id == 0 or row.show == 0:
            continue
        consumed = await has_educate_flag(client.commander.commander_id, educate_flag_id(educateFlagHomeEventBase, row.id))
        if consumed:
            continue
        events.append(row.id)
    events.sort()
    response.events.extend(events)
    return await client.send_message(27015, response)


# ── EducateGetPlans (27013) ──

def validate_educate_plan_cells(cells) -> bool:
    for cell in cells:
        if cell is None:
            return False
        if cell.day < 1 or cell.day > 6:
            return False
        if cell.index < 1 or cell.index > 3:
            return False
        values = cell.value
        if not values:
            return False
        for value in values:
            if not validate_educate_plan_value(value):
                return False
    return True

def validate_educate_plan_value(value) -> bool:
    if value is None:
        return False
    non_zero = 0
    if value.PlanId != 0:
        non_zero += 1
    if value.EventId != 0:
        non_zero += 1
    if value.SpecEventId != 0:
        non_zero += 1
    return non_zero == 1

async def EducateGetPlans(buffer: bytes, client) -> tuple:
    request = protobuf.CS_27012()
    request.ParseFromString(buffer)
    response = protobuf.SC_27013(result=0)
    if not validate_educate_plan_cells(request.plans):
        response.result = educatePlanValidationFailedResult
        response.ClearField('plans')
        return await client.send_message(27013, response)
    response.plans.extend(request.plans)
    return await client.send_message(27013, response)


# ── EducateGetTargetAward (27036) ──

async def EducateGetTargetAward(buffer: bytes, client) -> tuple:
    request = protobuf.CS_27035()
    request.ParseFromString(buffer)
    response = protobuf.SC_27036(result=educateResultFailed, drops=[])
    if client.commander is None or request.type != 0:
        return await client.send_message(27036, response)
    targets, tasks = await load_educate_target_and_task_configs()
    target_id = choose_educate_target_id(targets)
    if target_id == 0:
        return await client.send_message(27036, response)
    target = targets[target_id]
    claimed_flag = educate_flag_id(educateFlagTargetAwardBase, target_id)
    claimed = await has_educate_flag(client.commander.commander_id, claimed_flag)
    if claimed:
        return await client.send_message(27036, response)

    from src.orm.commander_task import afetch_commander_task_progress_map
    task_progress_by_id = await afetch_commander_task_progress_map(
        client.commander.commander_id
    )

    progress = 0
    for task_id in target.ids:
        task = tasks.get(task_id)
        if task and task_progress_by_id.get(task_id, 0) >= task.task_target_progress:
            progress += task.task_target_progress
    if progress < target.target_progress:
        return await client.send_message(27036, response)

    drop = to_child_drop(target.drop_display)
    if drop is not None:
        err = await apply_educate_child_drop(client, drop)
        if err:
            return 0, 27036, err
        response.drops.append(drop)
    await set_educate_flag(client.commander.commander_id, claimed_flag)
    response.result = educateResultOK
    return await client.send_message(27036, response)


# ── EducateUpgradeFavor (27007) ──

async def EducateUpgradeFavor(buffer: bytes, client) -> tuple:
    request = protobuf.CS_27006()
    request.ParseFromString(buffer)
    response = protobuf.SC_27007(result=legacyEducateResultFailure, drops=[])
    state = await get_or_create_legacy_educate_state(client.commander.commander_id)
    max_favor = 0
    child_data, ok = await load_legacy_child_data()
    if ok and child_data is not None:
        max_favor = child_data.favor_level
    if max_favor > 0 and state["favor_lv"] >= max_favor:
        return await client.send_message(27007, response)
    state["favor_lv"] += 1
    await save_legacy_educate_state(state)
    response.result = legacyEducateResultOK
    return await client.send_message(27007, response)


# ── EducateTriggerEnd (27009) ──

async def EducateTriggerEnd(buffer: bytes, client) -> tuple:
    request = protobuf.CS_27008()
    request.ParseFromString(buffer)
    response = protobuf.SC_27009(result=legacyEducateResultFailure)
    ending_id = request.ending_id
    if ending_id == 0:
        return await client.send_message(27009, response)
    exists = await legacy_config_exists(childEndingCategory, ending_id)
    if not exists:
        return await client.send_message(27009, response)
    state = await get_or_create_legacy_educate_state(client.commander.commander_id)
    state["endings"] = append_unique_uint32(state["endings"], ending_id)
    for qualified_id in request.qualified_id:
        state["qualifieds"] = append_unique_uint32(state["qualifieds"], qualified_id)
    await save_legacy_educate_state(state)
    response.result = legacyEducateResultOK
    return await client.send_message(27009, response)


# ── EducateGetEndings (27011) ──

async def EducateGetEndings(buffer: bytes, client) -> tuple:
    request = protobuf.CS_27010()
    request.ParseFromString(buffer)
    state = await get_or_create_legacy_educate_state(client.commander.commander_id)
    response = protobuf.SC_27011(
        endings=list(state["endings"]),
        qualifieds=list(state["qualifieds"]),
    )
    return await client.send_message(27011, response)


# ── EducateSetTarget (27020) ──

async def EducateSetTarget(buffer: bytes, client) -> tuple:
    request = protobuf.CS_27019()
    request.ParseFromString(buffer)
    response = protobuf.SC_27020(result=legacyEducateResultFailure)
    target_id = request.id
    if target_id == 0:
        return await client.send_message(27020, response)
    data, ok = await load_legacy_config_by_id(childTargetSetCategory, target_id)
    if not ok or data is None:
        return await client.send_message(27020, response)
    state = await get_or_create_legacy_educate_state(client.commander.commander_id)
    state["target_id"] = target_id
    await save_legacy_educate_state(state)
    response.result = legacyEducateResultOK
    return await client.send_message(27020, response)


# ── EducateSubmitTask (27024) ──

async def EducateSubmitTask(buffer: bytes, client) -> tuple:
    request = protobuf.CS_27023()
    request.ParseFromString(buffer)
    response = protobuf.SC_27024(result=legacyEducateResultFailure, awards=[])
    task_id = request.id
    if task_id == 0 or request.system == 0:
        return await client.send_message(27024, response)
    task_config, ok = await load_legacy_config_by_id(childTaskCategory, task_id)
    if not ok or task_config is None or task_config.type_1 != request.system:
        return await client.send_message(27024, response)
    state = await get_or_create_legacy_educate_state(client.commander.commander_id)
    if state["task_progress"].get(str(task_id), 0) < task_config.arg:
        return await client.send_message(27024, response)
    state["task_progress"].pop(str(task_id), None)
    await save_legacy_educate_state(state)
    response.result = legacyEducateResultOK
    if len(task_config.drop_display) >= 3:
        response.awards.append(
            build_legacy_child_drop(
                task_config.drop_display[0],
                task_config.drop_display[1],
                int(task_config.drop_display[2]),
            )
        )
    return await client.send_message(27024, response)


# ── EducateSetCall (27032) ──

async def EducateSetCall(buffer: bytes, client) -> tuple:
    request = protobuf.CS_27031()
    request.ParseFromString(buffer)
    response = protobuf.SC_27032(result=legacyEducateResultFailure)
    name = request.name.strip()
    cfg = get_config()
    blacklist = cfg.create_player.name_blacklist
    illegal_pattern = cfg.create_player.name_illegal_pattern
    if not is_valid_legacy_call_name(name, blacklist, illegal_pattern):
        return await client.send_message(27032, response)
    state = await get_or_create_legacy_educate_state(client.commander.commander_id)
    state["call_name"] = name
    await save_legacy_educate_state(state)
    response.result = legacyEducateResultOK
    return await client.send_message(27032, response)


# ── EducateAddTaskProgress (27038) ──

async def EducateAddTaskProgress(buffer: bytes, client) -> tuple:
    request = protobuf.CS_27037()
    request.ParseFromString(buffer)
    response = protobuf.SC_27038(result=legacyEducateResultFailure)
    if request.type_1 < 1 or request.type_1 > 3 or not request.progresses:
        return await client.send_message(27038, response)
    state = await get_or_create_legacy_educate_state(client.commander.commander_id)
    updated_tasks = []
    for progress in request.progresses:
        if progress.task_id == 0 or progress.progress == 0:
            return await client.send_message(27038, response)
        task_config, ok = await load_legacy_config_by_id(childTaskCategory, progress.task_id)
        if not ok or task_config is None or task_config.type_1 != request.type_1:
            return await client.send_message(27038, response)
        new_progress = state["task_progress"].get(str(progress.task_id), 0) + progress.progress
        if task_config.arg > 0 and new_progress > task_config.arg:
            new_progress = task_config.arg
        state["task_progress"][str(progress.task_id)] = new_progress
        updated_tasks.append(protobuf.CHILD_TASK(id=progress.task_id, progress=new_progress))
    await save_legacy_educate_state(state)
    response.result = legacyEducateResultOK
    bytes_written, packet_id, err = await client.send_message(27038, response)
    if err:
        return bytes_written, packet_id, err
    if updated_tasks:
        _, _, err2 = await client.send_message(27025, protobuf.SC_27025(tasks=updated_tasks))
        if err2:
            return bytes_written, packet_id, err2
    return bytes_written, packet_id, None


# ── EducateAddExtraAttr (27040) ──

async def EducateAddExtraAttr(buffer: bytes, client) -> tuple:
    request = protobuf.CS_27039()
    request.ParseFromString(buffer)
    response = protobuf.SC_27040(result=legacyEducateResultFailure)
    child_data, ok = await load_legacy_child_data()
    if not ok or child_data is None:
        return await client.send_message(27040, response)
    if not contains_uint32(child_data.attr_2_list, request.attr_id):
        return await client.send_message(27040, response)
    state = await get_or_create_legacy_educate_state(client.commander.commander_id)
    if state["had_adjustment"]:
        return await client.send_message(27040, response)
    state["attrs"][str(request.attr_id)] = state["attrs"].get(str(request.attr_id), 0) + child_data.attr_2_add
    state["had_adjustment"] = True
    await save_legacy_educate_state(state)
    response.result = legacyEducateResultOK
    return await client.send_message(27040, response)


# ── ChangeEducateCharacter (27042) ──

async def ChangeEducateCharacter(buffer: bytes, client) -> tuple:
    request = protobuf.CS_27041()
    request.ParseFromString(buffer)
    response = protobuf.SC_27042(result=legacyEducateResultFailure)
    ending_id = request.ending_id
    if ending_id == 0:
        return await client.send_message(27042, response)
    config, ok = await load_legacy_config_by_id(secretarySpecialShipCategory, ending_id)
    if not ok or config is None:
        return await client.send_message(27042, response)
    state = await get_or_create_legacy_educate_state(client.commander.commander_id)
    if not contains_uint32(state["endings"], ending_id):
        return await client.send_message(27042, response)
    store = get_default_store()
    await store.aexecute(
        "UPDATE commanders SET child_display = $2 WHERE commander_id = $1",
        client.commander.commander_id, ending_id,
    )
    client.commander.child_display = ending_id
    response.result = legacyEducateResultOK
    return await client.send_message(27042, response)


# ── EducateMapSiteOperate (27005) ──

async def EducateMapSiteOperate(buffer: bytes, client) -> tuple:
    request = protobuf.CS_27004()
    request.ParseFromString(buffer)
    response = protobuf.SC_27005(
        result=legacyEducateResultFailure,
        drops=[],
        event_drops=[],
        events=[],
        branch_id=0,
    )
    site, ok = await load_legacy_config_by_id(childSiteCategory, request.siteid)
    if not ok or site is None:
        return await client.send_message(27005, response)
    if not legacy_site_has_option(site, request.optionid):
        return await client.send_message(27005, response)
    option, ok = await load_legacy_config_by_id(childSiteOptionCategory, request.optionid)
    if not ok or option is None or option.type != 2:
        return await client.send_message(27005, response)
    state = await get_or_create_legacy_educate_state(client.commander.commander_id)
    if len(option.count_limit) >= 1:
        if state["option_records"].get(str(request.optionid), 0) >= option.count_limit[0]:
            return await client.send_message(27005, response)
    for cost in option.cost:
        if len(cost) < 3 or cost[0] != 2:
            continue
        if state["resources"].get(str(cost[1]), 0) < cost[2]:
            return await client.send_message(27005, response)
    branch_id = 0
    for candidate in option.result:
        if await legacy_config_exists(childSiteOptionBranchCategory, candidate):
            branch_id = candidate
            break
    if branch_id == 0:
        return await client.send_message(27005, response)
    for cost in option.cost:
        if len(cost) < 3 or cost[0] != 2:
            continue
        cost_key = str(cost[1])
        state["resources"][cost_key] = state["resources"].get(cost_key, 0) - cost[2]
    state["option_records"][str(request.optionid)] = state["option_records"].get(str(request.optionid), 0) + 1
    await save_legacy_educate_state(state)
    response.result = legacyEducateResultOK
    response.branch_id = branch_id
    return await client.send_message(27005, response)


# ── EducateRefresh (27048) ──

async def EducateRefresh(buffer: bytes, client) -> tuple:
    request = protobuf.CS_27047()
    request.ParseFromString(buffer)
    response = protobuf.SC_27048(result=0)
    return await client.send_message(27048, response)


# ── EducateReset (27030) ──

async def EducateReset(buffer: bytes, client) -> tuple:
    request = protobuf.CS_27029()
    request.ParseFromString(buffer)
    response = protobuf.SC_27030(result=0)
    return await client.send_message(27030, response)


# ── EducateRequestOption (27046) ──

async def EducateRequestOption(buffer: bytes, client) -> tuple:
    request = protobuf.CS_27045()
    request.ParseFromString(buffer)
    options = await load_educate_site_options()
    response = protobuf.SC_27046(result=0, opts=options)
    return await client.send_message(27046, response)


# ── EducateRequestShopData (27044) ──

async def EducateRequestShopData(buffer: bytes, client) -> tuple:
    request = protobuf.CS_27043()
    request.ParseFromString(buffer)
    response = protobuf.SC_27044(
        result=educateResultFailed,
        shop_data=protobuf.CHILD_SHOP_DATA(shop_id=request.shop_id, goods=[]),
    )
    if client.commander is None or request.shop_id == 0:
        return await client.send_message(27044, response)
    shops, templates = await load_educate_shop_configs()
    shop = shops.get(request.shop_id)
    if shop is None:
        return await client.send_message(27044, response)
    now = int(time.time())
    row = await ensure_educate_shop_state(client.commander.commander_id, shop, templates, now)
    goods_data = json.loads(row["goods"]) if isinstance(row["goods"], str) else (row.get("goods") or [])
    goods = [protobuf.CHILD_SHOP_GOODS(id=g["id"], num=g["num"]) for g in goods_data]
    response.result = educateResultOK
    response.shop_data = protobuf.CHILD_SHOP_DATA(shop_id=shop.id, goods=goods)
    return await client.send_message(27044, response)


# ── EducateShopping (27034) ──

async def EducateShopping(buffer: bytes, client) -> tuple:
    request = protobuf.CS_27033()
    request.ParseFromString(buffer)
    response = protobuf.SC_27034(result=educateResultFailed, drops=[])
    if client.commander is None or request.shop_id == 0 or not request.goods:
        return await client.send_message(27034, response)
    shops, templates = await load_educate_shop_configs()
    shop = shops.get(request.shop_id)
    if shop is None:
        return await client.send_message(27034, response)
    now = int(time.time())
    row = await ensure_educate_shop_state(client.commander.commander_id, shop, templates, now)
    goods_data = json.loads(row["goods"]) if isinstance(row["goods"], str) else (row.get("goods") or [])
    state_goods = [EducateShopGoodsState(id=g["id"], num=g["num"]) for g in goods_data]

    index = {}
    for i, g in enumerate(state_goods):
        index[g.id] = i

    resource_cost = {}
    drops = []
    for row_good in request.goods:
        if row_good.id == 0 or row_good.num == 0:
            return await client.send_message(27034, response)
        good_idx = index.get(row_good.id)
        if good_idx is None:
            return await client.send_message(27034, response)
        if state_goods[good_idx].num < row_good.num:
            return await client.send_message(27034, response)
        tpl = templates.get(row_good.id)
        if tpl is None or tpl.resource == 0:
            return await client.send_message(27034, response)
        resource_cost[tpl.resource] = resource_cost.get(tpl.resource, 0) + tpl.resource_num * row_good.num
        state_goods[good_idx].num -= row_good.num
        n = int(tpl.buy_num * row_good.num)
        drops.append(protobuf.CHILD_DROP(type=2, id=tpl.item_id, number=n))

    if not drops:
        return await client.send_message(27034, response)

    store = get_default_store()
    for res_id, amount in resource_cost.items():
        row = await store.afetchrow(
            "SELECT amount FROM owned_resources WHERE commander_id = $1 AND resource_id = $2",
            client.commander.commander_id, res_id,
        )
        if row is None or row["amount"] < amount:
            return await client.send_message(27034, response)

    async with store.transaction():
        for res_id, amount in resource_cost.items():
            await store.aexecute(
                "UPDATE owned_resources SET amount = amount - $3 WHERE commander_id = $1 AND resource_id = $2",
                client.commander.commander_id, res_id, amount,
            )
        for drop in drops:
            err = await apply_educate_child_drop(client, drop)
            if err:
                return 0, 27034, err
        goods_json = json.dumps([{"id": g.id, "num": g.num} for g in state_goods])
        await store.aexecute(
            "UPDATE educate_shop_states SET goods = $3 WHERE commander_id = $1 AND shop_id = $2",
            client.commander.commander_id, shop.id, goods_json,
        )

    response.result = educateResultOK
    response.drops.extend(drops)
    return await client.send_message(27034, response)


# ── EducateTriggerEvent (27017) ──

async def EducateTriggerEvent(buffer: bytes, client) -> tuple:
    request = protobuf.CS_27016()
    request.ParseFromString(buffer)
    response = protobuf.SC_27017(result=educateResultFailed, drops=[])
    if client.commander is None or request.eventid == 0:
        return await client.send_message(27017, response)
    events = await load_educate_events()
    if request.eventid not in events:
        return await client.send_message(27017, response)
    await set_educate_flag(client.commander.commander_id, educate_flag_id(educateFlagHomeEventBase, request.eventid))
    response.result = educateResultOK
    return await client.send_message(27017, response)


# ── EducateTriggerSpecEvent (27028) ──

async def EducateTriggerSpecEvent(buffer: bytes, client) -> tuple:
    request = protobuf.CS_27027()
    request.ParseFromString(buffer)
    response = protobuf.SC_27028(result=educateResultFailed, drops=[])
    if client.commander is None or request.spec_events_id == 0:
        return await client.send_message(27028, response)
    events = await load_educate_special_events()
    event = events.get(request.spec_events_id)
    if event is None:
        return await client.send_message(27028, response)
    finish_flag = educate_flag_id(educateFlagSpecialEventBase, request.spec_events_id)
    already_done = await has_educate_flag(client.commander.commander_id, finish_flag)
    if already_done:
        return await client.send_message(27028, response)
    drop = to_child_drop(event.drop_display)
    if drop is not None:
        err = await apply_educate_child_drop(client, drop)
        if err:
            return 0, 27028, err
        response.drops.append(drop)
    await set_educate_flag(client.commander.commander_id, finish_flag)
    if event.type == 3:
        await set_educate_flag(client.commander.commander_id, educate_flag_id(educateFlagDiscountBase, request.spec_events_id))
    response.result = educateResultOK
    return await client.send_message(27028, response)
