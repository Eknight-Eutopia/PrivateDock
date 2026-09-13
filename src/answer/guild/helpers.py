import json
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from src.protobuf import protobuf
from src.db.store import get_default_store, NotFoundError
from src.orm.config_entry import afetch_config_entries_data, afetch_config_entry_data

# ── Constants ──

guildResultSuccess = 0
guildResultFailure = 1
guildResultNameInvalid = 2015
guildResultApplicantJoined = 1
guildResultApplicantWait = 4
guildResultGuildFrozen = 4305

guildMinNameLength = 1
guildMaxNameLength = 20

guildChunkResultSuccess = 0
guildChunkResultFailure = 1

guildCoinResourceID = 8
goldResourceID = 1

guildChatPlaceholderID = 0

guildEventResultSuccess = 0
guildEventResultFailure = 1
guildEventResultInsufficientCapital = 2
guildEventResultInternal = 3
guildEventResultNoActiveOperation = 20

guildApplyResultSuccess = 0
guildApplyResultFailure = 1
guildApplyResultJoinCD = 4
guildApplyResultMaxed = 6
guildApplyResultFrozen = 4305
guildApplyResultFull = 4306
guildApplyContentLimit = 20
guildApplyOutstandingLimit = 10

guildShopGetShop = 0
guildShopAutoRefresh = 1
guildShopManualRefresh = 2

guildStoreConfigCategory = "ShareCfg/guild_store.json"
guildShopGoodsTypeFixed = 1
guildShopGoodsTypeSelectable = 2
guildShopCoinResourceID = 8

guildShopPurchaseResultOK = 0
guildShopPurchaseResultInvalid = 1
guildShopPurchaseResultInsufficient = 2
guildShopPurchaseResultStock = 3
guildShopPurchaseResultUnsupported = 4
guildShopPurchaseResultDBError = 5

dropTypeItem = 3
dropTypeShip = 4
dropTypeResource = 5

# ── JSON entry structs ──

class guildGameSetEntry:
    def __init__(self, key_value: Any = None):
        self.key_value = key_value

class guildContributionTemplate:
    def __init__(self, id=0, consume=None, award_contribution=0, award_capital=0, award_tech_exp=0, guild_active=0):
        self.id = id
        self.consume = consume or []
        self.award_contribution = award_contribution
        self.award_capital = award_capital
        self.award_tech_exp = award_tech_exp
        self.guild_active = guild_active

class guildMissionTemplate:
    def __init__(self, id=0, max_num=0):
        self.id = id
        self.max_num = max_num

class guildTechnologyTemplate:
    def __init__(self, id=0, group=0, next_tech=0, gold_consume=0, contribution_consume=0, contribution_multiple=0, need_guild_active=0, level_max=0):
        self.id = id
        self.group = group
        self.next_tech = next_tech
        self.gold_consume = gold_consume
        self.contribution_consume = contribution_consume
        self.contribution_multiple = contribution_multiple
        self.need_guild_active = need_guild_active
        self.level_max = level_max

class guildOperationTemplateEntry:
    def __init__(self, consume=0, unlock_guild_level=0):
        self.consume = consume
        self.unlock_guild_level = unlock_guild_level

class guildPersonShipPage:
    def __init__(self, page_id=0, ship_ids=None):
        self.page_id = page_id
        self.ship_ids = ship_ids or []

class guildStorePurchaseEntry:
    def __init__(self, id=0, price=0, goods=None, goods_type=0, num=0, type=0,
                 order=0, ensure=0, weight=0, goods_icon="", goods_name="",
                 goods_rarity=0, goods_purchase_limit=0, **kwargs):
        self.id = id
        self.price = price
        self.goods = goods or []
        self.goods_type = goods_type
        self.num = num
        self.type = type
        self.order = order
        self.ensure = ensure
        self.weight = weight
        self.goods_icon = goods_icon
        self.goods_name = goods_name
        self.goods_rarity = goods_rarity
        self.goods_purchase_limit = goods_purchase_limit

class guildEventContext:
    def __init__(self, guild_id=0, commander_id=0, duty=0, operation_id=0):
        self.guild_id = guild_id
        self.commander_id = commander_id
        self.duty = duty
        self.operation_id = operation_id

# ── Time helpers ──

def now_unix() -> int:
    return int(time.time())

def current_week_monday_0_clock() -> int:
    now = datetime.now(timezone.utc)
    weekday = now.weekday()
    if weekday == 6:
        weekday = 7
    else:
        weekday += 1
    monday = now - timedelta(days=weekday - 1)
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(monday.timestamp())

# ── Slice helpers ──

def contains_uint32(lst: list[int], value: int) -> bool:
    return value in lst

# ── Config helpers ──
# Decoding lives in src.orm.config_entry: config_entries.data is JSONB on
# PostgreSQL (psycopg2 auto-parses) but plain TEXT on asyncpg/SQLite, so every
# reader needs the same normalisation.

async def load_game_set_uint(key: str) -> int:
    data = await afetch_config_entry_data("ShareCfg/gameset.json", key)
    if data is None:
        raise NotFoundError(f"config entry {key} not found")
    entry = guildGameSetEntry(**data) if isinstance(data, dict) else guildGameSetEntry(key_value=data.get("key_value"))
    return parse_config_uint(entry.key_value)

def parse_config_uint(value: Any) -> int:
    if isinstance(value, (int, float)):
        return max(0, int(value))
    return 0

async def load_guild_contribution_template(tid: int) -> tuple:
    data = await afetch_config_entry_data("ShareCfg/guild_contribution_template.json", str(tid))
    if data is None:
        return None, False
    tpl = guildContributionTemplate(**data)
    if tpl.id == 0:
        tpl.id = tid
    return tpl, True

async def load_default_guild_donate_tasks() -> list[int]:
    # The old query ordered by key, but the ids are sorted below anyway.
    rows = await afetch_config_entries_data("ShareCfg/guild_contribution_template.json")
    ids = []
    for data in rows:
        if not isinstance(data, dict):
            continue
        tpl = guildContributionTemplate(**data)
        if tpl.id:
            ids.append(tpl.id)
    ids.sort()
    return ids[:3]

async def load_guild_mission_template(tid: int) -> tuple:
    data = await afetch_config_entry_data("ShareCfg/guild_mission_template.json", str(tid))
    if data is None:
        return None, False
    tpl = guildMissionTemplate(**data)
    if tpl.id == 0:
        tpl.id = tid
    return tpl, True

async def load_guild_technology_template(tid: int) -> tuple:
    data = await afetch_config_entry_data("ShareCfg/guild_technology_template.json", str(tid))
    if data is None:
        return None, False
    tpl = guildTechnologyTemplate(**data)
    if tpl.id == 0:
        tpl.id = tid
    return tpl, True

async def load_guild_operation_template(chapter_id: int) -> Optional[guildOperationTemplateEntry]:
    data = await afetch_config_entry_data("ShareCfg/guild_operation_template.json", str(chapter_id))
    if data is None:
        return None
    return guildOperationTemplateEntry(**data)

def _match_guild_store_purchase_entry(data, goods_id: int) -> tuple:
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("id") == goods_id:
                return guildStorePurchaseEntry(**item), True
        return None, False
    if isinstance(data, dict):
        entry = guildStorePurchaseEntry(**data)
        if entry.id == goods_id:
            return entry, True
    return None, False

async def load_guild_store_purchase_entry(goods_id: int) -> tuple:
    data = await afetch_config_entry_data(guildStoreConfigCategory, str(goods_id))
    if data is not None:
        entry, ok = _match_guild_store_purchase_entry(data, goods_id)
        if ok:
            return entry, True
    for row in await afetch_config_entries_data(guildStoreConfigCategory):
        entry, ok = _match_guild_store_purchase_entry(row, goods_id)
        if ok:
            return entry, True
    return None, False

# ── Proto builders ──

def build_display_info(icon=0, skin=0, icon_frame=0, chat_frame=0, icon_theme=0) -> protobuf.DISPLAYINFO:
    return protobuf.DISPLAYINFO(
        icon=icon, skin=skin, icon_frame=icon_frame,
        chat_frame=chat_frame, icon_theme=icon_theme,
        marry_flag=0, transform_flag=0,
    )

def build_guild_base_info(guild) -> protobuf.GUILD_BASE_INFO:
    if guild is None:
        return protobuf.GUILD_BASE_INFO(id=0, policy=0, faction=0, name="", level=0, announce="", manifesto="", exp=0, member_count=0, change_faction_cd=0, kick_leader_cd=0)
    return protobuf.GUILD_BASE_INFO(
        id=guild.id, policy=guild.policy, faction=guild.faction,
        name=guild.name, level=guild.level, announce=guild.announce or "",
        manifesto=guild.manifesto or "", exp=guild.exp,
        member_count=guild.member_count, change_faction_cd=getattr(guild, 'change_faction_cd', 0),
        kick_leader_cd=getattr(guild, 'kick_leader_cd', 0),
    )

def build_guild_expansion_info(guild) -> protobuf.GUILD_EXPANSION_INFO:
    capital = guild.capital if guild else 0
    benefit_finish_time = 0
    last_benefit_finish_time = 0
    tech_cancel_cnt = 0
    weekly_task_obj = protobuf.WEEKLY_TASK(id=0, progress=0, monday_0clock=0)
    return protobuf.GUILD_EXPANSION_INFO(
        capital=capital, this_weekly_tasks=weekly_task_obj,
        benefit_finish_time=benefit_finish_time, retreat_cnt=0,
        tech_cancel_cnt=tech_cancel_cnt, last_benefit_finish_time=last_benefit_finish_time,
        active_event_cnt=0,
    )

def build_guild_member_info(member) -> protobuf.MEMBER_INFO:
    pre_online = getattr(member, 'pre_online_time', 0)
    if pre_online == 0 and hasattr(member, 'last_login') and member.last_login:
        pre_online = int(member.last_login.timestamp())
    return protobuf.MEMBER_INFO(
        liveness=getattr(member, 'liveness', 0), duty=getattr(member, 'duty', 0),
        id=getattr(member, 'commander_id', 0), name=getattr(member, 'commander_name', ""),
        lv=getattr(member, 'commander_level', 0), adv=getattr(member, 'manifesto', ""),
        online=0, pre_online_time=pre_online,
        display=build_display_info(
            icon=getattr(member, 'display_icon_id', 0),
            skin=getattr(member, 'display_skin_id', 0),
            icon_frame=getattr(member, 'icon_frame_id', 0),
            chat_frame=getattr(member, 'chat_frame_id', 0),
            icon_theme=getattr(member, 'icon_theme_id', 0),
        ),
        join_time=getattr(member, 'join_time', 0),
    )

def build_guild_chat_player(commander) -> protobuf.PLAYER_INFO_P60:
    return protobuf.PLAYER_INFO_P60(
        id=commander.commander_id, name=commander.name, lv=commander.level,
        display=build_display_info(
            icon=getattr(commander, 'display_icon_id', 0),
            skin=getattr(commander, 'display_skin_id', 0),
            icon_frame=getattr(commander, 'selected_icon_frame_id', 0),
            chat_frame=getattr(commander, 'selected_chat_frame_id', 0),
            icon_theme=getattr(commander, 'display_icon_theme_id', 0),
        ),
    )

def build_guild_simple_info(entry) -> protobuf.GUILD_SIMPLE_INFO:
    guild = entry.guild if hasattr(entry, 'guild') else entry
    leader = entry.leader if hasattr(entry, 'leader') else entry
    return protobuf.GUILD_SIMPLE_INFO(
        base=build_guild_base_info(guild),
        leader=build_guild_chat_player(leader),
        tech_seat=getattr(entry, 'tech_seat', 0),
    )

def build_guild_shop_goods(goods_list) -> list:
    return [protobuf.GOODS_INFO_P60(id=g.goods_id, count=g.count, index=g.index) for g in goods_list]

def build_event_base(event) -> protobuf.EVENT_BASE:
    ship_in_event = json.loads(event.ship_in_event) if isinstance(event.ship_in_event, str) else (event.ship_in_event or [])
    attr_acc = json.loads(event.attr_acc_list) if isinstance(event.attr_acc_list, str) else (event.attr_acc_list or [])
    attr_count = json.loads(event.attr_count_list) if isinstance(event.attr_count_list, str) else (event.attr_count_list or [])
    event_nodes = json.loads(event.event_nodes) if isinstance(event.event_nodes, str) else (event.event_nodes or [])
    person_ship = json.loads(event.person_ship) if isinstance(event.person_ship, str) else (event.person_ship or [])
    return protobuf.EVENT_BASE(
        event_id=event.event_tid, position=event.position, start_time=event.start_time,
        complete_time=event.complete_time, shipinevent=ship_in_event,
        attr_acc_list=attr_acc, attr_count_list=attr_count, eventnodes=event_nodes,
        efficiency=event.efficiency, personship=person_ship,
    )

def build_operation_response(state) -> protobuf.CURRENT_OPERATION:
    base_events = []
    completed_events = []
    formation_time = []
    for event in state.events:
        if getattr(event, 'completed', False):
            completed_events.append(protobuf.EVENT_BASE_COMPLETED(event_id=event.event_tid, position=event.position))
        else:
            base_events.append(build_event_base(event))
            formation_time.append(protobuf.KEYVALUE_P61(key=event.event_tid, value=getattr(event, 'formation_time', 0)))
    perfs = [protobuf.EVENT_PERFORMANCE(event_id=p.event_tid, index=p.index) for p in getattr(state, 'perfs', [])]
    boss_fleets = []
    return protobuf.CURRENT_OPERATION(
        operation_id=state.chapter_id, start_time=state.start_time,
        base_events=base_events, boss_event=None, perfs=perfs,
        formation_time=formation_time, completed_events=completed_events,
        daily_count=0, fleets=boss_fleets,
        join_times=getattr(state, 'join_times', 0), is_participant=getattr(state, 'is_participant', 0),
    )

def default_guild_boss_event() -> protobuf.EVENT_BOSS:
    return protobuf.EVENT_BOSS(boss_id=0, damage=0, hp=0)

# ── Guild context ──

async def active_guild_event_context(commander_id: int):
    store = get_default_store()
    row = await store.afetchrow(
        "SELECT g.id as guild_id, gm.duty, gos.chapter_id "
        "FROM guild_members gm "
        "JOIN guilds g ON g.id = gm.guild_id "
        "LEFT JOIN guild_operation_states gos ON gos.guild_id = g.id AND gos.end_time > $1 "
        "WHERE gm.commander_id = $2",
        now_unix(), commander_id,
    )
    if row is None:
        raise NotFoundError("no active guild event")
    return guildEventContext(
        guild_id=row["guild_id"], commander_id=commander_id,
        duty=row["duty"], operation_id=row["chapter_id"],
    )

def is_guild_admin_duty(duty: int) -> bool:
    return duty in (1, 2)  # Commander=1, Deputy=2

def is_guild_event_context_error(err: Exception) -> bool:
    return isinstance(err, NotFoundError)

def is_valid_guild_name(name: str) -> bool:
    length = len(name)
    return guildMinNameLength <= length <= guildMaxNameLength

def is_valid_guild_faction(faction: int) -> bool:
    return faction in (1, 2)

def is_valid_guild_policy(policy: int) -> bool:
    return policy in (1, 2)

def clamp_guild_apply_content(content: str) -> str:
    if len(content) <= guildApplyContentLimit:
        return content
    return content[:guildApplyContentLimit]

def normalize_guild_shop_selection(config, selected) -> tuple:
    if config.goods_type not in (guildShopGoodsTypeFixed, guildShopGoodsTypeSelectable):
        return {}, 0, False
    rewards = {}
    total_units = 0
    if not selected:
        if config.goods_type != guildShopGoodsTypeFixed:
            return {}, 0, False
        for gid in config.goods:
            if gid == 0:
                return {}, 0, False
            rewards[gid] = rewards.get(gid, 0) + 1
        return rewards, 1, True
    if config.goods_type == guildShopGoodsTypeFixed:
        return {}, 0, False
    for pick in selected:
        pid = pick.get("id", 0) if isinstance(pick, dict) else getattr(pick, "id", 0)
        count = pick.get("count", 0) if isinstance(pick, dict) else getattr(pick, "count", 0)
        if pid == 0 or count == 0:
            return {}, 0, False
        if pid not in config.goods:
            return {}, 0, False
        rewards[pid] = rewards.get(pid, 0) + count
        total_units += count
    if total_units == 0:
        return {}, 0, False
    return rewards, total_units, True

def map_guild_shop_drop_type(config_type: int) -> tuple:
    # guild_store.json `type` uses the same values as DROPINFO types:
    # 2 = item, 4 = ship (see consts.drop_types)
    mapping = {2: (2, True), 4: (4, True)}
    return mapping.get(config_type, (0, False))

def must_marshal_json(value) -> bytes:
    try:
        return json.dumps(value).encode("utf-8")
    except Exception:
        return b"[]"
