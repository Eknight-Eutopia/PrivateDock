import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from .helpers import (
    load_educate_state, save_educate_state, default_educate_state,
    ensure_educate_cache, ensure_tb_info_defaults, tb_info_placeholder, empty_tb_drops,
    load_current_new_educate_round_config, parse_new_educate_uint32_list,
    choose_new_educate_talent_candidate, apply_new_educate_config_drops,
    load_new_educate_config_by_id, list_new_educate_configs,
    resolve_new_educate_resource_id, remove_uint32, upsert_kvdata_with_delta,
    newEducateSystemEvent, newEducateSystemTalent, newEducateSystemTopic,
    newEducateSystemMap, newEducateSystemPlan, newEducateSystemAssess,
    newEducateSystemEnding, newEducateSystemMind,
    newEducateSiteStateEvent, newEducateSiteStateNormal, newEducateSiteStateShip, newEducateSiteEventGroupCategory,
    newEducateShopCategory, newEducateSiteCharacterCategory, newEducateSiteNormalCategory,
)


def NewEducateRequest(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29001()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29002, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception:
        state = default_educate_state(client.commander.commander_id, payload.id)
    response = protobuf.SC_29002(result=0, tb=state.info, permanent=state.permanent)
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29002, e
    asyncio.create_task(client.send_message(29002, response))
    return 0, 29002, None


def NewEducateGetEndings(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29003()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29004, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29004, e
    endings = list(state.permanent.Endings)
    cache = ensure_educate_cache(state.info)
    cache.cache_end[0].ends = list(endings)
    cache.cache_end[0].select = 0
    state.info.Fsm.system_no = newEducateSystemEnding
    response = protobuf.SC_29004(result=0, endings=endings)
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29004, e
    asyncio.create_task(client.send_message(29004, response))
    return 0, 29004, None


def NewEducateSelectEnding(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29005()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29006, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29006, e
    state.permanent.ActiveEndings = append_unique_uint32(state.permanent.ActiveEndings, payload.ending_id)
    cache = ensure_educate_cache(state.info)
    cache.cache_end[0].select = payload.ending_id
    response = protobuf.SC_29006(result=0)
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29006, e
    asyncio.create_task(client.send_message(29006, response))
    return 0, 29006, None


def NewEducateReset(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29007()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29008, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29008, e
    state.info = ensure_tb_info_defaults(tb_info_placeholder())
    state.info.Id = payload.id
    state.info.Difficulty = payload.difficulty
    state.permanent.NgPlusCount = state.permanent.ng_plus_count + 1
    response = protobuf.SC_29008(result=0, tb=state.info)
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29008, e
    asyncio.create_task(client.send_message(29008, response))
    return 0, 29008, None


def NewEducateSetCall(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29009()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29010, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29010, e
    state.info.Name = payload.name
    response = protobuf.SC_29010(result=0)
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29010, e
    asyncio.create_task(client.send_message(29010, response))
    return 0, 29010, None


def NewEducateMainEvent(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29011()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29012, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29012, e
    first_node = state.info.Fsm.current_node
    state.info.Fsm.system_no = newEducateSystemEvent
    response = protobuf.SC_29012(result=0, first_node=first_node)
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29012, e
    asyncio.create_task(client.send_message(29012, response))
    return 0, 29012, None


def NewEducateAssess(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29013()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29014, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29014, e
    round_no = state.info.Round.round
    state.info.Evaluations = upsert_kvdata(state.info.Evaluations, round_no, payload.rank)
    state.info.Fsm.system_no = newEducateSystemAssess
    first_node = state.info.Fsm.current_node
    response = protobuf.SC_29014(result=0, first_node=first_node, drop=empty_tb_drops())
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29014, e
    asyncio.create_task(client.send_message(29014, response))
    return 0, 29014, None


def NewEducateGetTopics(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29015()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29016, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29016, e
    cache = ensure_educate_cache(state.info)
    chats = cache.cache_chat[0].chats
    state.info.Fsm.system_no = newEducateSystemTopic
    response = protobuf.SC_29016(result=0, chats=chats)
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29016, e
    asyncio.create_task(client.send_message(29016, response))
    return 0, 29016, None


def NewEducateSelectTopic(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29017()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29018, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29018, e
    cache = ensure_educate_cache(state.info)
    cache.cache_chat[0].finished = 1
    cache.cache_chat[0].chats = append_unique_uint32(cache.cache_chat[0].chats, payload.chat_id)
    state.info.Fsm.system_no = newEducateSystemTopic
    state.info.Fsm.current_node = 0
    response = protobuf.SC_29018(result=0, first_node=0, drop=empty_tb_drops())
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29018, e
    asyncio.create_task(client.send_message(29018, response))
    return 0, 29018, None


def NewEducateGetTalents(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29019()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29020, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29020, e
    cache = ensure_educate_cache(state.info)
    if len(cache.cache_talent[0].talents) == 0:
        round_config, ok, err = load_current_new_educate_round_config(state.info)
        if err:
            return 0, 29020, err
        if ok:
            talents = parse_new_educate_uint32_list(round_config.benefit_select)
            cache.cache_talent[0].talents = list(talents)
    state.info.Fsm.system_no = newEducateSystemTalent
    response = protobuf.SC_29020(result=0, talents=cache.cache_talent[0].talents)
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29020, e
    asyncio.create_task(client.send_message(29020, response))
    return 0, 29020, None


def NewEducateRefreshTalent(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29021()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29022, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29022, e
    cache = ensure_educate_cache(state.info)
    new_talent = payload.talent
    round_config, ok, err = load_current_new_educate_round_config(state.info)
    if err:
        return 0, 29022, err
    if ok:
        available = parse_new_educate_uint32_list(round_config.benefit_select)
        new_talent = choose_new_educate_talent_candidate(
            cache.cache_talent[0].talents, cache.cache_talent[0].retalents,
            available, payload.talent
        )
    for idx, talent in enumerate(cache.cache_talent[0].talents):
        if talent == payload.talent:
            cache.cache_talent[0].talents[idx] = new_talent
            break
    cache.cache_talent[0].retalents = append_unique_uint32(cache.cache_talent[0].retalents, payload.talent)
    response = protobuf.SC_29022(result=0, talent=new_talent)
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29022, e
    asyncio.create_task(client.send_message(29022, response))
    return 0, 29022, None


def NewEducateSelectTalent(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29023()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29024, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29024, e
    state.info.Talent.talents = append_unique_uint32(state.info.Talent.talents, payload.talent)
    cache = ensure_educate_cache(state.info)
    cache.cache_talent[0].talents = append_unique_uint32(cache.cache_talent[0].talents, payload.talent)
    cache.cache_talent[0].finished = 1
    response = protobuf.SC_29024(result=0, drop=apply_new_educate_talent_selection(state, payload.talent))
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29024, e
    asyncio.create_task(client.send_message(29024, response))
    return 0, 29024, None


def NewEducateChangePhase(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29025()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29026, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29026, e
    advance_new_educate_round(state)
    response = protobuf.SC_29026(result=0, first_node=0, drop=empty_tb_drops())
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29026, e
    asyncio.create_task(client.send_message(29026, response))
    return 0, 29026, None


def NewEducateUpgradeFavor(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29027()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29028, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29028, e
    state.info.FavorLv = state.info.favor_lv + 1
    response = protobuf.SC_29028(result=0, drop=empty_tb_drops())
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29028, e
    asyncio.create_task(client.send_message(29028, response))
    return 0, 29028, None


def NewEducateTriggerNode(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29030()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29031, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29031, e
    state.info.Fsm.current_node = 0
    response = protobuf.SC_29031(result=0, next_node=0, drop=empty_tb_drops())
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29031, e
    asyncio.create_task(client.send_message(29031, response))
    return 0, 29031, None


def NewEducateClearNodeChain(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29032()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29033, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29033, e
    state.info.Fsm.current_node = 0
    response = protobuf.SC_29033(result=0, fsm=state.info.Fsm)
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29033, e
    asyncio.create_task(client.send_message(29033, response))
    return 0, 29033, None


def NewEducateSchedule(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29040()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29041, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29041, e
    cache = ensure_educate_cache(state.info)
    cache.cache_plan[0].plans = payload.plans
    cache.cache_plan[0].cur_index = 0
    state.info.Fsm.system_no = newEducateSystemPlan
    response = protobuf.SC_29041(result=0, plans=payload.plans, drop=empty_tb_drops())
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29041, e
    asyncio.create_task(client.send_message(29041, response))
    return 0, 29041, None


def NewEducateNextPlan(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29042()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29043, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29043, e
    cache = ensure_educate_cache(state.info)
    cur_index = cache.cache_plan[0].cur_index
    if cur_index < len(cache.cache_plan[0].plans):
        cache.cache_plan[0].cur_index = cur_index + 1
    response = protobuf.SC_29043(result=0, first_node=0, drop=empty_tb_drops())
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29043, e
    asyncio.create_task(client.send_message(29043, response))
    return 0, 29043, None


def NewEducateUpgradePlan(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29044()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29045, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29045, e
    for plan_id in payload.plan_ids:
        state.info.Plan.plan_upgrade = append_unique_uint32(state.info.Plan.plan_upgrade, plan_id)
    response = protobuf.SC_29045(result=0)
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29045, e
    asyncio.create_task(client.send_message(29045, response))
    return 0, 29045, None


def NewEducateScheduleSkip(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29046()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29047, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29047, e
    cache = ensure_educate_cache(state.info)
    cache.cache_plan[0].cur_index = len(cache.cache_plan[0].plans)
    response = protobuf.SC_29047(result=0, drop=empty_tb_drops())
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29047, e
    asyncio.create_task(client.send_message(29047, response))
    return 0, 29047, None


def NewEducateGetExtraDrop(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29048()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29049, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29049, e
    response = protobuf.SC_29049(result=0, drop=empty_tb_drops(), res=state.info.Res)
    asyncio.create_task(client.send_message(29049, response))
    return 0, 29049, None


def NewEducateGetMap(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29060()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29061, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29061, e
    cache = ensure_educate_cache(state.info)
    state.info.Fsm.system_no = newEducateSystemMap
    response = protobuf.SC_29061(result=0, fsm_site=cache.cache_site[0], characters=state.info.Site.characters, drop=empty_tb_drops())
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29061, e
    asyncio.create_task(client.send_message(29061, response))
    return 0, 29061, None


def NewEducateMapNormal(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29062()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29063, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29063, e
    config, ok, _ = load_new_educate_config_by_id(newEducateSiteNormalCategory, payload.work_id)
    if ok:
        if isinstance(config, dict):
            apply_new_educate_config_drops(state, config.get("cost", []), 1)
    cache = ensure_educate_cache(state.info)
    cache.cache_site[0].state = protobuf.KVDATA(key=newEducateSiteStateNormal, value=payload.work_id)
    state.info.Site.work_counter = upsert_kvdata_count(state.info.Site.work_counter, payload.work_id, 1)
    state.info.Fsm.system_no = newEducateSystemMap
    response = protobuf.SC_29063(result=0, first_node=0, drop=empty_tb_drops())
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29063, e
    asyncio.create_task(client.send_message(29063, response))
    return 0, 29063, None


def NewEducateMapEvent(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29064()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29065, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29065, e
    config, ok, _ = load_new_educate_config_by_id(newEducateSiteEventGroupCategory, payload.event)
    if ok and isinstance(config, dict):
        apply_new_educate_config_drops(state, config.get("event_cost", []), 1)
    cache = ensure_educate_cache(state.info)
    cache.cache_site[0].state = protobuf.KVDATA(key=newEducateSiteStateEvent, value=payload.event)
    cache.cache_site[0].events = remove_uint32(cache.cache_site[0].events, payload.event)
    state.info.Site.event_counter = upsert_kvdata_count(state.info.Site.event_counter, payload.event, 1)
    state.info.Fsm.system_no = newEducateSystemMap
    response = protobuf.SC_29065(result=0, first_node=0, drop=empty_tb_drops())
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29065, e
    asyncio.create_task(client.send_message(29065, response))
    return 0, 29065, None


def NewEducateShopping(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29066()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29067, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29067, e
    shop_config, ok, _ = load_new_educate_config_by_id(newEducateShopCategory, payload.shop)
    if ok and isinstance(shop_config, dict):
        resource_id, found = resolve_new_educate_resource_id(state, shop_config.get("resource_type", 0))
        if found:
            state.info.Res.resource = upsert_kvdata_with_delta(
                state.info.Res.resource, resource_id,
                -(shop_config.get("resource_num", 0) * payload.num)
            )
    cache = ensure_educate_cache(state.info)
    cache.cache_site[0].buys = upsert_kvdata_count(cache.cache_site[0].buys, payload.shop, payload.num)
    response = protobuf.SC_29067(result=0, drop=empty_tb_drops())
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29067, e
    asyncio.create_task(client.send_message(29067, response))
    return 0, 29067, None


def NewEducateMapShip(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29068()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29069, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29069, e
    next_character_id = 0
    config, ok, _ = load_new_educate_config_by_id(newEducateSiteCharacterCategory, payload.character)
    if ok and isinstance(config, dict):
        apply_new_educate_config_drops(state, config.get("cost", []), 1)
        characters = list_new_educate_configs(newEducateSiteCharacterCategory)
        cfg_group = config.get("group", 0)
        cfg_level = config.get("level", 0)
        for candidate in characters:
            if candidate.get("group", 0) == cfg_group and candidate.get("level", 0) == cfg_level + 1:
                next_character_id = candidate.get("id", 0)
                break
    cache = ensure_educate_cache(state.info)
    cache.cache_site[0].state = protobuf.KVDATA(key=newEducateSiteStateShip, value=payload.character)
    if next_character_id != 0:
        for idx, character_id in enumerate(state.info.Site.characters):
            if character_id == payload.character:
                state.info.Site.characters[idx] = next_character_id
                break
        cache.cache_site[0].character_this_round = append_unique_uint32(cache.cache_site[0].character_this_round, next_character_id)
    state.info.Fsm.system_no = newEducateSystemMap
    response = protobuf.SC_29069(result=0, first_node=0, drop=empty_tb_drops())
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29069, e
    asyncio.create_task(client.send_message(29069, response))
    return 0, 29069, None


def NewEducateUpgradeNormalSite(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29070()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29071, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29071, e
    state.info.Site.works = append_unique_uint32(state.info.Site.works, payload.work_id)
    response = protobuf.SC_29071(result=0)
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29071, e
    asyncio.create_task(client.send_message(29071, response))
    return 0, 29071, None


def NewEducateSelectMind(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29090()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29091, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29091, e
    state.info.Fsm.system_no = newEducateSystemMind
    response = protobuf.SC_29091(result=0, first_node=0, drop=empty_tb_drops())
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29091, e
    asyncio.create_task(client.send_message(29091, response))
    return 0, 29091, None


def NewEducateRefresh(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_29092()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 29093, e
    try:
        state = load_educate_state(client, payload.id)
    except Exception as e:
        return 0, 29093, e
    state.info.Difficulty = payload.difficulty
    response = protobuf.SC_29093(result=0, tb=state.info)
    try:
        save_educate_state(state)
    except Exception as e:
        return 0, 29093, e
    asyncio.create_task(client.send_message(29093, response))
    return 0, 29093, None


# ── Utility functions ──

from src.answer.educate.helpers import append_unique_uint32


def upsert_kvdata(values, key, value):
    for entry in values:
        if entry.key == key:
            entry.value = value
            return values
    values.append(protobuf.KVDATA(key=key, value=value))
    return values


def upsert_kvdata_count(values, key, increment):
    for entry in values:
        if entry.key == key:
            entry.value = entry.value + increment
            return values
    values.append(protobuf.KVDATA(key=key, value=increment))
    return values


def apply_new_educate_talent_selection(state, talent_id):
    if state.info.Benefit is None:
        state.info.Benefit = protobuf.TBBENEFIT(actives=[])
    state.info.Benefit.actives = upsert_tbbf(state.info.Benefit.actives, talent_id, state.info.Round.round, 0)
    state.permanent.TarotArchive = append_unique_uint32(state.permanent.TarotArchive, talent_id)
    return protobuf.TBDROPS(
        base_drop=[protobuf.TBDROP(type=4, id=talent_id, number=1)],
        benefit_drop=[],
        display=empty_tb_drops().display,
    )


def advance_new_educate_round(state):
    temp_rounds = state.info.Round.temp_round
    if temp_rounds > 0:
        state.info.Round.in_temp = 1
        state.info.Round.temp_round = temp_rounds - 1
    else:
        state.info.Round.in_temp = 0
        state.info.Round.round = state.info.Round.round + 1
    state.info.EvalFail = 0
    state.permanent.MaxRound = max_uint32(state.permanent.max_round, state.info.Round.round)
    state.info.Fsm = ensure_tb_info_defaults(tb_info_placeholder()).fsm
    del state.info.site.characters[:]


def upsert_tbbf(values, id, round_no, is_pending):
    for entry in values:
        if entry.id == id:
            entry.round = round_no
            entry.is_pending = is_pending
            return values
    values.append(protobuf.TBBF(id=id, round=round_no, is_pending=is_pending))
    return values


def max_uint32(left, right):
    return left if left > right else right
