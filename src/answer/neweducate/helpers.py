import json

from src.db.store import get_default_store
from src.orm.config_entry import fetch_config_entries_data, fetch_config_entry_data
from src.protobuf import protobuf

# ── Constants ──

newEducateRoundCategory = "ShareCfg/child2_round.json"
newEducateSiteNormalCategory = "ShareCfg/child2_site_normal.json"
newEducateSiteEventGroupCategory = "ShareCfg/child2_site_event_group.json"
newEducateSiteCharacterCategory = "ShareCfg/child2_site_character.json"
newEducateShopCategory = "ShareCfg/child2_shop.json"
newEducateResourceCategory = "ShareCfg/child2_resource.json"

newEducateDropTypeAttr = 1
newEducateDropTypeRes = 2
newEducateRoundTypeNormal = 1

newEducateSystemEvent = 1
newEducateSystemTalent = 2
newEducateSystemTopic = 3
newEducateSystemMap = 4
newEducateSystemPlan = 5
newEducateSystemAssess = 6
newEducateSystemPhase = 7
newEducateSystemEnding = 8
newEducateSystemMind = 9

newEducateSiteStateEvent = 1
newEducateSiteStateNormal = 2
newEducateSiteStateShip = 3

# ── Config types ──

class NewEducateRoundConfig:
    def __init__(self, id=0, character=0, round=0, round_type=0, is_hard_mode=0, benefit_select=None, map_mobility=0, refresh_refill=0):
        self.id = id
        self.character = character
        self.round = round
        self.round_type = round_type
        self.is_hard_mode = is_hard_mode
        self.benefit_select = benefit_select
        self.map_mobility = map_mobility
        self.refresh_refill = refresh_refill

class NewEducateSiteNormalConfig:
    def __init__(self, id=0, cost=None):
        self.id = id
        self.cost = cost or []

class NewEducateSiteEventGroupConfig:
    def __init__(self, id=0, event_cost=None):
        self.id = id
        self.event_cost = event_cost or []

class NewEducateSiteCharacterConfig:
    def __init__(self, id=0, group=0, level=0, cost=None):
        self.id = id
        self.group = group
        self.level = level
        self.cost = cost or []

class NewEducateShopConfig:
    def __init__(self, id=0, resource_type=0, resource_num=0):
        self.id = id
        self.resource_type = resource_type
        self.resource_num = resource_num

class NewEducateResourceConfig:
    def __init__(self, id=0, type=0):
        self.id = id
        self.type = type

# ── Helper functions ──

def load_new_educate_config_by_id(category, id):
    # config_entries.data is JSONB on PG (auto-parsed) but TEXT on SQLite;
    # src.orm.config_entry normalises both.
    data = fetch_config_entry_data(category, id)
    if data is None:
        return None, False, None
    return data, True, None

def list_new_educate_configs(category):
    return fetch_config_entries_data(category)

def load_current_new_educate_round_config(info):
    rounds = list_new_educate_configs(newEducateRoundCategory)
    for round_data in rounds:
        if (round_data.get("character", 0) == info.id and
            round_data.get("round", 0) == info.round.round and
            round_data.get("is_hard_mode", 0) == info.difficulty and
            round_data.get("round_type", 0) == newEducateRoundTypeNormal):
            return NewEducateRoundConfig(**round_data), True, None
    return None, False, None

def parse_new_educate_uint32_list(raw):
    if not raw or raw == "" or raw == "null":
        return []
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        return json.loads(raw)
    return raw

def choose_new_educate_talent_candidate(current, refreshed, available, old_talent):
    blocked = set(current) | set(refreshed)
    for candidate in available:
        if candidate != old_talent and candidate not in blocked:
            return candidate
    return old_talent

def apply_new_educate_config_drops(state, drops, multiplier):
    if multiplier == 0:
        return
    for drop in drops:
        if len(drop) < 3:
            continue
        delta = -drop[2] * multiplier
        if drop[0] == newEducateDropTypeAttr:
            state.info.res.attrs = upsert_kvdata_with_delta(state.info.res.attrs, drop[1], delta)
        elif drop[0] == newEducateDropTypeRes:
            state.info.res.resource = upsert_kvdata_with_delta(state.info.res.resource, drop[1], delta)

def upsert_kvdata_with_delta(values, key, delta):
    for entry in values:
        if entry.key == key:
            entry.value = apply_uint32_delta(entry.value, delta)
            return values
    values.append(protobuf.KVDATA(key=key, value=apply_uint32_delta(0, delta)))
    return values

def apply_uint32_delta(current, delta):
    if delta >= 0:
        return current + delta
    if -delta >= current:
        return 0
    return current - (-delta)

def resolve_new_educate_resource_id(state, resource_type):
    resources = list_new_educate_configs(newEducateResourceCategory)
    for resource in resources:
        if resource.get("type", 0) != resource_type:
            continue
        rid = resource.get("id", 0)
        for entry in state.info.res.resource:
            if entry.key == rid:
                return rid, True
    for resource in resources:
        if resource.get("type", 0) == resource_type:
            return resource.get("id", 0), True
    return 0, False

def remove_uint32(values, target):
    return [v for v in values if v != target]

# ── Placeholder functions ──

def tb_info_placeholder():
    return protobuf.TBINFO(
        id=0,
        personality_id=0,
        fsm=protobuf.TBFSM(
            system_no=0,
            current_node=0,
            priority_fsm=[],
            tarot_selects=[],
            cache=[protobuf.TBFSMCACHE(
                cache_plan=[protobuf.TBFSMCACHEPLAN(cur_index=0, plans=[])],
                cache_talent=[protobuf.TBFSMCACHETALENT(finished=0, talents=[], retalents=[])],
                cache_site=[protobuf.TBFSMCACHESITE(
                    events=[], shops=[], buys=[],
                    state=protobuf.KVDATA(key=0, value=0),
                    character_this_round=[], refresh_count=0,
                )],
                cache_chat=[protobuf.TBFSMCACHECHAT(finished=0, chats=[])],
                cache_end=[protobuf.TBFSMCACHEEND(ends=[], select=0)],
                cache_mind=[protobuf.TBFSMCACHEMIND()],
                cache_nin1=[],
                cache_affix_up=[],
                cache_tarot=[],
                cache_eval=[],
        )],
        ),
        round=protobuf.TBROUND(round=1, in_temp=0, temp_round=0),
        res=protobuf.TBRES(attrs=[], resource=[]),
        talent=protobuf.TBTALENT(talents=[]),
        plan=protobuf.TBPLAN(plan_upgrade=[]),
        site=protobuf.TBSITE(characters=[], work_counter=[], works=[], event_counter=[]),
        evaluations=[],
        name="",
        favor_lv=0,
        benefit=protobuf.TBBENEFIT(actives=[]),
        difficulty=0,
        eval_fail=0,
        display=empty_tb_display(),
    )

def tb_permanent_placeholder():
    return protobuf.TBPERMANENT(
        ng_plus_count=1,
        polaroids=[],
        endings=[],
        active_endings=[],
        tarot_archive=[],
        max_round=0,
    )

def empty_tb_display():
    return protobuf.TBDISPLAY(
        benefit_display=[],
        dollar_num_display=[],
        counter=[],
    )

# ── State management ──

class EducateState:
    def __init__(self, entry=None, info=None, permanent=None):
        self.entry = entry
        self.info = info
        self.permanent = permanent

def load_educate_state(client, tb_id):
    store = get_default_store()
    row = store.fetchrow(
        "SELECT commander_id, state, permanent FROM commander_tbs WHERE commander_id = $1",
        client.commander.commander_id
    )
    if row is None:
        info = ensure_tb_info_defaults(tb_info_placeholder())
        permanent = ensure_tb_permanent_defaults(tb_permanent_placeholder())
        info.id = tb_id
        state_bytes = info.SerializeToString()
        permanent_bytes = permanent.SerializeToString()
        store.execute(
            "INSERT INTO commander_tbs (commander_id, state, permanent) VALUES ($1, $2, $3) ON CONFLICT (commander_id) DO UPDATE SET state=EXCLUDED.state, permanent=EXCLUDED.permanent",
            client.commander.commander_id, state_bytes, permanent_bytes
        )
        return EducateState(entry={"commander_id": client.commander.commander_id}, info=info, permanent=permanent)
    info = protobuf.TBINFO()
    info.ParseFromString(bytes(row["state"]))
    permanent = protobuf.TBPERMANENT()
    permanent.ParseFromString(bytes(row["permanent"]))
    info = ensure_tb_info_defaults(info)
    permanent = ensure_tb_permanent_defaults(permanent)
    info.id = tb_id
    return EducateState(entry=dict(row), info=info, permanent=permanent)

def save_educate_state(state):
    info_bytes = state.info.SerializeToString()
    permanent_bytes = state.permanent.SerializeToString()
    store = get_default_store()
    store.execute(
        "INSERT INTO commander_tbs (commander_id, state, permanent) VALUES ($1, $2, $3) ON CONFLICT (commander_id) DO UPDATE SET state=EXCLUDED.state, permanent=EXCLUDED.permanent",
        state.entry["commander_id"], info_bytes, permanent_bytes
    )

def ensure_tb_info_defaults(info):
    defaults = tb_info_placeholder()
    if info is None:
        return defaults
    if info.fsm is None:
        info.fsm = defaults.fsm
    if not info.fsm.cache:
        info.fsm.cache = defaults.fsm.cache
    cache = info.fsm.cache[0]
    if not cache.cache_plan:
        cache.cache_plan = defaults.fsm.cache[0].cache_plan
    if not cache.cache_talent:
        cache.cache_talent = defaults.fsm.cache[0].cache_talent
    if not cache.cache_site:
        cache.cache_site = defaults.fsm.cache[0].cache_site
    if not cache.cache_chat:
        cache.cache_chat = defaults.fsm.cache[0].cache_chat
    if not cache.cache_end:
        cache.cache_end = defaults.fsm.cache[0].cache_end
    if not cache.cache_mind:
        cache.cache_mind = defaults.fsm.cache[0].cache_mind
    if cache.cache_site[0].refresh_count is None:
        cache.cache_site[0].refresh_count = defaults.fsm.cache[0].cache_site[0].refresh_count
    if info.round is None:
        info.round = defaults.round
    if info.round.in_temp is None:
        info.round.in_temp = defaults.round.in_temp
    if info.round.temp_round is None:
        info.round.temp_round = defaults.round.temp_round
    if info.res is None:
        info.res = defaults.res
    if info.talent is None:
        info.talent = defaults.talent
    if info.plan is None:
        info.plan = defaults.plan
    if info.site is None:
        info.site = defaults.site
    if info.benefit is None:
        info.benefit = defaults.benefit
    if info.difficulty is None:
        info.difficulty = defaults.difficulty
    if info.eval_fail is None:
        info.eval_fail = defaults.eval_fail
    if info.display is None:
        info.display = defaults.display
    if info.evaluations is None:
        info.evaluations = []
    if not info.HasField('personality_id'):
        info.personality_id = 0
    return info

def ensure_tb_permanent_defaults(permanent):
    if permanent is None:
        return tb_permanent_placeholder()
    if permanent.polaroids is None:
        permanent.polaroids = []
    if permanent.endings is None:
        permanent.endings = []
    if permanent.active_endings is None:
        permanent.active_endings = []
    if permanent.tarot_archive is None:
        permanent.tarot_archive = []
    if permanent.max_round is None:
        permanent.max_round = 0
    return permanent

def empty_tb_drops():
    return protobuf.TBDROPS(
        base_drop=[],
        benefit_drop=[],
        display=empty_tb_display(),
    )

def ensure_educate_cache(info):
    info = ensure_tb_info_defaults(info)
    return info.fsm.cache[0]

def default_educate_state(commander_id, tb_id):
    info = ensure_tb_info_defaults(tb_info_placeholder())
    permanent = ensure_tb_permanent_defaults(tb_permanent_placeholder())
    info.id = tb_id
    return EducateState(
        entry={"commander_id": commander_id},
        info=info,
        permanent=permanent,
    )
