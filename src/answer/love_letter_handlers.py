import asyncio
import json
from typing import Optional

from src.consts.drop_types import (
    DROP_TYPE_ICON_FRAME,
    DROP_TYPE_CHAT_FRAME,
    DROP_TYPE_COMBAT_UI_STYLE,
    DROP_TYPE_RESOURCE,
    DROP_TYPE_ITEM,
    DROP_TYPE_EQUIP,
    DROP_TYPE_SHIP,
    DROP_TYPE_FURNITURE,
    DROP_TYPE_SKIN,
    DROP_TYPE_LOVE_LETTER,
)
from src.connection.client import Client
from src.protobuf import protobuf
from src.orm import (
    list_config_entries,
    get_or_create_commander_love_letter_state,
    save_commander_love_letter_state,
    CommanderLoveLetterStateData,
    LoveLetterMedalState,
    LoveLetterLetterState,
    LoveLetterConvertedItem,
)

LOVE_LETTER_RESULT_SUCCESS = 0
LOVE_LETTER_RESULT_FAILED = 1

LOVE_LETTER_CHARACTER_TEMPLATE_CATEGORY = "ShareCfg/lover_character_template.json"
LOVE_LETTER_CONTENT_TEMPLATE_CATEGORY = "ShareCfg/lover_letter_content.json"
LOVE_LETTER_REWARD_TEMPLATE_CATEGORY = "ShareCfg/lover_reward.json"
LOVE_LETTER_LEGACY_TEMPLATE_CATEGORY = "ShareCfg/loveletter_2018_2021.json"
LOVE_LETTER_TEXT_TEMPLATE_CATEGORY = "ShareCfg/lover_letter_text.json"


class LoveLetterCharacterConfig:
    def __init__(self, id=0, exp_up=0, exp_upper_limit=0, relate_group_id=None):
        self.id = id
        self.exp_up = exp_up
        self.exp_upper_limit = exp_upper_limit
        self.relate_group_id = relate_group_id or []

    @classmethod
    def from_dict(cls, d):
        return cls(
            id=d.get("id", 0),
            exp_up=d.get("exp_up", 0),
            exp_upper_limit=d.get("exp_upper_limit", 0),
            relate_group_id=d.get("relate_group_id", []) or [],
        )


class LoveLetterContentConfig:
    def __init__(self, id=0, ship_group=0, year=0, love_item=None, content=""):
        self.id = id
        self.ship_group = ship_group
        self.year = year
        self.love_item = love_item or []
        self.content = content

    @classmethod
    def from_dict(cls, d):
        return cls(
            id=d.get("id", 0),
            ship_group=d.get("ship_group", 0),
            year=d.get("year", 0),
            love_item=d.get("love_item", []) or [],
            content=d.get("content", ""),
        )


class LoveLetterRewardConfig:
    def __init__(self, id=0, total_level=0, show_reward=None):
        self.id = id
        self.total_level = total_level
        self.show_reward = show_reward or []

    @classmethod
    def from_dict(cls, d):
        return cls(
            id=d.get("id", 0),
            total_level=d.get("total_level", 0),
            show_reward=d.get("show_reward", []) or [],
        )


class LoveLetterLegacyConfig:
    def __init__(self, id=0, ship_group_id=0, year=0):
        self.id = id
        self.ship_group_id = ship_group_id
        self.year = year

    @classmethod
    def from_dict(cls, d):
        return cls(
            id=d.get("id", 0),
            ship_group_id=d.get("ship_group_id", 0),
            year=d.get("year", 0),
        )


class LoveLetterConfigBundle:
    def __init__(self):
        self.characters: dict[int, LoveLetterCharacterConfig] = {}
        self.contents: dict[int, LoveLetterContentConfig] = {}
        self.rewards: dict[int, LoveLetterRewardConfig] = {}
        self.group_letter_ids: dict[int, list[int]] = {}
        self.item_group_to_years: dict[str, dict[int, int]] = {}
        self.letter_by_group_year: dict[str, int] = {}
        self.letter_text_by_id: dict[int, str] = {}


class ResolvedConvertedItem:
    def __init__(self, item: LoveLetterConvertedItem, canonical_group: int = 0, letter_id: int = 0):
        self.item = item
        self.canonical_group = canonical_group
        self.letter_id = letter_id


def _item_group_key(item_id: int, group_id: int) -> str:
    return f"{item_id}_{group_id}"


def _group_year_key(group_id: int, year: int) -> str:
    return f"{group_id}_{year}"


def _load_json_config(entry_data) -> Optional[dict]:
    if isinstance(entry_data, dict):
        return entry_data
    if isinstance(entry_data, str):
        return json.loads(entry_data)
    return None


def _is_json_map(data) -> bool:
    if isinstance(data, (dict,)):
        return True
    if isinstance(data, str):
        return data.strip().startswith("{")
    return False


def _load_config_dict(category: str, cls_factory) -> dict:
    result = {}
    for entry in list_config_entries(category):
        data = _load_json_config(entry)
        if data is None or not _is_json_map(data):
            continue
        try:
            obj = cls_factory(data)
        except Exception:
            continue
        if obj.id != 0:
            result[obj.id] = obj
    return result


def _load_love_letter_config_bundle() -> LoveLetterConfigBundle:
    bundle = LoveLetterConfigBundle()
    bundle.characters = _load_config_dict(LOVE_LETTER_CHARACTER_TEMPLATE_CATEGORY, LoveLetterCharacterConfig.from_dict)
    bundle.contents = _load_config_dict(LOVE_LETTER_CONTENT_TEMPLATE_CATEGORY, LoveLetterContentConfig.from_dict)
    bundle.rewards = _load_config_dict(LOVE_LETTER_REWARD_TEMPLATE_CATEGORY, LoveLetterRewardConfig.from_dict)

    legacy_mappings = _load_config_dict(LOVE_LETTER_LEGACY_TEMPLATE_CATEGORY, LoveLetterLegacyConfig.from_dict)

    for content_config in bundle.contents.values():
        if content_config.ship_group not in bundle.group_letter_ids:
            bundle.group_letter_ids[content_config.ship_group] = []
        bundle.group_letter_ids[content_config.ship_group].append(content_config.id)
        bundle.letter_by_group_year[_group_year_key(content_config.ship_group, content_config.year)] = content_config.id
        if content_config.content:
            bundle.letter_text_by_id[content_config.id] = content_config.content

        groups = [content_config.ship_group]
        if content_config.ship_group in bundle.characters:
            groups.extend(bundle.characters[content_config.ship_group].relate_group_id)

        for item_id in content_config.love_item:
            for group_id in groups:
                key = _item_group_key(item_id, group_id)
                if key not in bundle.item_group_to_years:
                    bundle.item_group_to_years[key] = {}
                bundle.item_group_to_years[key][content_config.year] = content_config.ship_group

    for group_id in bundle.group_letter_ids:
        bundle.group_letter_ids[group_id].sort()

    for legacy_config in legacy_mappings.values():
        key = _item_group_key(legacy_config.id, legacy_config.ship_group_id)
        if key not in bundle.item_group_to_years:
            bundle.item_group_to_years[key] = {}
        if legacy_config.year not in bundle.item_group_to_years[key]:
            bundle.item_group_to_years[key][legacy_config.year] = legacy_config.ship_group_id

    for entry in list_config_entries(LOVE_LETTER_TEXT_TEMPLATE_CATEGORY):
        data = _load_json_config(entry)
        if data is None or not _is_json_map(data):
            continue
        content = data.get("content", "")
        if not content:
            continue
        try:
            letter_id = int(entry["key"]) if isinstance(entry, dict) and "key" in entry else 0
        except (ValueError, TypeError):
            continue
        if letter_id:
            bundle.letter_text_by_id[letter_id] = content

    return bundle


def _resolve_converted_item(item: LoveLetterConvertedItem, bundle: LoveLetterConfigBundle) -> tuple:
    if item.item_id == 0 or item.group_id == 0 or item.year == 0:
        return 0, 0, False
    year_map = bundle.item_group_to_years.get(_item_group_key(item.item_id, item.group_id))
    if year_map is None:
        return 0, 0, False
    canonical_group = year_map.get(item.year)
    if canonical_group is None:
        return 0, 0, False
    letter_id = bundle.letter_by_group_year.get(_group_year_key(canonical_group, item.year), 0)
    if letter_id == 0:
        return 0, 0, False
    return canonical_group, letter_id, True


def _resolve_converted_items_strict(items: list[LoveLetterConvertedItem], bundle: LoveLetterConfigBundle) -> list[ResolvedConvertedItem]:
    resolved = []
    for item in items:
        canonical_group, letter_id, ok = _resolve_converted_item(item, bundle)
        if not ok:
            raise ValueError(f"invalid converted item: {item.item_id}/{item.group_id}/{item.year}")
        resolved.append(ResolvedConvertedItem(item=item, canonical_group=canonical_group, letter_id=letter_id))
    return resolved


def _resolve_converted_items_lenient(items: list[LoveLetterConvertedItem], bundle: LoveLetterConfigBundle) -> list[ResolvedConvertedItem]:
    resolved = []
    for item in items:
        canonical_group, letter_id, ok = _resolve_converted_item(item, bundle)
        if not ok:
            continue
        resolved.append(ResolvedConvertedItem(item=item, canonical_group=canonical_group, letter_id=letter_id))
    return resolved


def _converted_count_by_group(items: list[ResolvedConvertedItem]) -> dict[int, int]:
    counts = {}
    for item in items:
        counts[item.canonical_group] = counts.get(item.canonical_group, 0) + 1
    return counts


def _converted_letter_set(items: list[ResolvedConvertedItem]) -> dict[int, set[int]]:
    letters = {}
    for item in items:
        if item.canonical_group not in letters:
            letters[item.canonical_group] = set()
        letters[item.canonical_group].add(item.letter_id)
    return letters


def _medals_to_map(medals: list[LoveLetterMedalState]) -> dict[int, LoveLetterMedalState]:
    return {m.group_id: LoveLetterMedalState(group_id=m.group_id, exp=m.exp, level=m.level) for m in medals}


def _medal_map_to_list(medal_map: dict[int, LoveLetterMedalState]) -> list[LoveLetterMedalState]:
    return [medal_map[gid] for gid in sorted(medal_map.keys())]


def _letter_states_to_set(states: list[LoveLetterLetterState]) -> dict[int, set[int]]:
    result = {}
    for state in states:
        if state.group_id not in result:
            result[state.group_id] = set()
        for letter_id in state.letter_id_list:
            result[state.group_id].add(letter_id)
    return result


def _letter_set_to_states(letter_set: dict[int, set[int]]) -> list[LoveLetterLetterState]:
    states = []
    for group_id in sorted(letter_set.keys()):
        letter_ids = sorted(letter_set[group_id])
        states.append(LoveLetterLetterState(group_id=group_id, letter_id_list=letter_ids))
    return states


def _merge_letter_sets(a: dict[int, set[int]], b: dict[int, set[int]]) -> dict[int, set[int]]:
    merged = {}
    for group_id, letter_set in a.items():
        merged[group_id] = set(letter_set)
    for group_id, letter_set in b.items():
        if group_id not in merged:
            merged[group_id] = set()
        merged[group_id].update(letter_set)
    return merged


def _total_display_level(medals: list[LoveLetterMedalState], bundle: LoveLetterConfigBundle) -> int:
    total = 0
    for medal in medals:
        display_level = medal.level
        char_cfg = bundle.characters.get(medal.group_id)
        if char_cfg is not None and char_cfg.exp_up > 0 and char_cfg.exp_upper_limit > 0:
            max_level = char_cfg.exp_upper_limit // char_cfg.exp_up
            if display_level > max_level:
                display_level = max_level
        total += display_level
    return total


def _build_love_letter_snapshot(state: CommanderLoveLetterStateData, bundle: LoveLetterConfigBundle) -> dict:
    resolved = _resolve_converted_items_lenient(state.converted_items, bundle)
    manual_set = _letter_states_to_set(state.manual_letters)
    gift_set = _converted_letter_set(resolved)
    merged = _merge_letter_sets(manual_set, gift_set)

    return {
        "converted_items": [LoveLetterConvertedItem(item_id=c.item_id, group_id=c.group_id, year=c.year) for c in state.converted_items],
        "rewarded_ids": list(state.rewarded_ids),
        "medals": [LoveLetterMedalState(group_id=m.group_id, exp=m.exp, level=m.level) for m in state.medals],
        "letters": _letter_set_to_states(merged),
        "converted_letters": _letter_set_to_states(gift_set),
    }


def _accumulate_drop(drops: dict, drop_type: int, drop_id: int, count: int):
    key = f"{drop_type}_{drop_id}"
    if key in drops:
        drops[key].number += count
    else:
        d = protobuf.DROPINFO()
        d.type = drop_type
        d.id = drop_id
        d.number = count
        drops[key] = d


def _drop_map_to_sorted_list(drops: dict) -> list:
    lst = list(drops.values())
    lst.sort(key=lambda x: (x.type, x.id))
    return lst


async def _apply_love_letter_drops(client: Client, drops: dict):
    from src.orm.item import add_item
    from src.orm.owned_equipment import add_owned_equipment
    from src.orm.owned_ship import add_ship
    from src.orm.owned_skin import give_skin
    from src.orm.resource import add_resource
    from src.orm.commander_furniture import add_commander_furniture
    for drop in drops.values():
        drop_type = drop.type
        drop_id = drop.id
        drop_count = drop.number
        commander_id = client.commander.commander_id
        if drop_type in (DROP_TYPE_ICON_FRAME, DROP_TYPE_CHAT_FRAME, DROP_TYPE_COMBAT_UI_STYLE):
            from src.orm.commander_attire import grant_commander_attire_drop_sync
            grant_commander_attire_drop_sync(commander_id, drop_type, drop_id, drop_count)
        elif drop_type == DROP_TYPE_RESOURCE:
            add_resource(commander_id, drop_id, drop_count)
        elif drop_type in (DROP_TYPE_ITEM, DROP_TYPE_LOVE_LETTER):
            add_item(commander_id, drop_id, drop_count)
        elif drop_type == DROP_TYPE_EQUIP:
            add_owned_equipment(commander_id, drop_id, drop_count)
        elif drop_type == DROP_TYPE_SHIP:
            for _ in range(drop_count):
                add_ship(commander_id, drop_id)
        elif drop_type == DROP_TYPE_FURNITURE:
            add_commander_furniture(commander_id, drop_id, drop_count)
        elif drop_type == DROP_TYPE_SKIN:
            for _ in range(drop_count):
                give_skin(commander_id, drop_id)


# ── Handlers ──

async def _love_letter_get_all_data(client: Client):
    bundle = _load_love_letter_config_bundle()
    state = get_or_create_commander_love_letter_state(client.commander.commander_id)
    snapshot = _build_love_letter_snapshot(state, bundle)

    response = protobuf.SC_12407()
    for item in snapshot["converted_items"]:
        entry = response.converted_list.add()
        entry.item_id = item.item_id
        entry.group_id = item.group_id
        entry.year = item.year
    response.rewarded_list.extend(snapshot["rewarded_ids"])
    for medal in snapshot["medals"]:
        entry = response.medal_list.add()
        entry.group_id = medal.group_id
        entry.exp = medal.exp
        entry.level = medal.level
    for letter in snapshot["letters"]:
        entry = response.letter_list.add()
        entry.group_id = letter.group_id
        entry.letter_id_list.extend(letter.letter_id_list)
    for letter in snapshot["converted_letters"]:
        entry = response.converted_letter_list.add()
        entry.group_id = letter.group_id
        entry.letter_id_list.extend(letter.letter_id_list)

    await client.send_message(12407, response)


def handle_love_letter_get_all_data(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    asyncio.create_task(_love_letter_get_all_data(client))
    return 0, 12407, None


async def _love_letter_unlock(client: Client, payload: protobuf.CS_12400):
    bundle = _load_love_letter_config_bundle()
    letter_config = bundle.contents.get(payload.id)
    if letter_config is None:
        await client.send_message(12401, protobuf.SC_12401(result=LOVE_LETTER_RESULT_FAILED))
        return

    state = get_or_create_commander_love_letter_state(client.commander.commander_id)
    medal_map = _medals_to_map(state.medals)
    manual_set = _letter_states_to_set(state.manual_letters)
    resolved = _resolve_converted_items_lenient(state.converted_items, bundle)
    gift_set = _converted_letter_set(resolved)
    merged = _merge_letter_sets(manual_set, gift_set)

    if letter_config.ship_group in merged and payload.id in merged[letter_config.ship_group]:
        await client.send_message(12401, protobuf.SC_12401(result=LOVE_LETTER_RESULT_FAILED))
        return

    medal = medal_map.get(letter_config.ship_group)
    if medal is None:
        medal = LoveLetterMedalState(group_id=letter_config.ship_group)
        medal_map[letter_config.ship_group] = medal

    group_letters = bundle.group_letter_ids.get(letter_config.ship_group, [])
    index = 0
    for i, lid in enumerate(group_letters):
        if lid == payload.id:
            index = i + 1
            break
    if index == 0 or index > medal.level:
        await client.send_message(12401, protobuf.SC_12401(result=LOVE_LETTER_RESULT_FAILED))
        return

    if letter_config.ship_group not in manual_set:
        manual_set[letter_config.ship_group] = set()
    manual_set[letter_config.ship_group].add(payload.id)

    state.manual_letters = _letter_set_to_states(manual_set)
    state.medals = _medal_map_to_list(medal_map)
    save_commander_love_letter_state(state)
    await client.send_message(12401, protobuf.SC_12401(result=LOVE_LETTER_RESULT_SUCCESS))


def handle_love_letter_unlock(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_12400()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 12401, e
    asyncio.create_task(_love_letter_unlock(client, payload))
    return 0, 12401, None


async def _love_letter_claim_rewards(client: Client, payload: protobuf.CS_12402):
    reward_ids = list(payload.id_list)
    if not reward_ids:
        await client.send_message(12403, protobuf.SC_12403(result=LOVE_LETTER_RESULT_FAILED))
        return

    bundle = _load_love_letter_config_bundle()
    state = get_or_create_commander_love_letter_state(client.commander.commander_id)

    level_all = _total_display_level(state.medals, bundle)
    rewarded_set = set(state.rewarded_ids)
    request_set = set()
    drops = {}

    for reward_id in reward_ids:
        if reward_id in request_set:
            await client.send_message(12403, protobuf.SC_12403(result=LOVE_LETTER_RESULT_FAILED))
            return
        request_set.add(reward_id)
        if reward_id in rewarded_set:
            await client.send_message(12403, protobuf.SC_12403(result=LOVE_LETTER_RESULT_FAILED))
            return
        reward_config = bundle.rewards.get(reward_id)
        if reward_config is None or level_all < reward_config.total_level:
            await client.send_message(12403, protobuf.SC_12403(result=LOVE_LETTER_RESULT_FAILED))
            return
        for drop_entry in reward_config.show_reward:
            if len(drop_entry) < 3:
                await client.send_message(12403, protobuf.SC_12403(result=LOVE_LETTER_RESULT_FAILED))
                return
            _accumulate_drop(drops, drop_entry[0], drop_entry[1], drop_entry[2])

    await _apply_love_letter_drops(client, drops)
    state.rewarded_ids.extend(reward_ids)
    state.rewarded_ids.sort()
    save_commander_love_letter_state(state)

    drop_list = _drop_map_to_sorted_list(drops)
    response = protobuf.SC_12403(result=LOVE_LETTER_RESULT_SUCCESS)
    for d in drop_list:
        entry = response.drop_list.add()
        entry.type = d.type
        entry.id = d.id
        entry.number = d.number
    await client.send_message(12403, response)


def handle_love_letter_claim_rewards(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_12402()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 12403, e
    asyncio.create_task(_love_letter_claim_rewards(client, payload))
    return 0, 12403, None


async def _love_letter_realize_gift(client: Client, payload: protobuf.CS_12404):
    converted_items = []
    for item in payload.item_list:
        if item.item_id is None or item.group_id is None or item.year is None:
            await client.send_message(12405, protobuf.SC_12405(result=LOVE_LETTER_RESULT_FAILED))
            return
        converted_items.append(LoveLetterConvertedItem(item_id=item.item_id, group_id=item.group_id, year=item.year))

    bundle = _load_love_letter_config_bundle()
    try:
        resolved_new = _resolve_converted_items_strict(converted_items, bundle)
    except ValueError:
        await client.send_message(12405, protobuf.SC_12405(result=LOVE_LETTER_RESULT_FAILED))
        return

    state = get_or_create_commander_love_letter_state(client.commander.commander_id)
    resolved_old = _resolve_converted_items_lenient(state.converted_items, bundle)
    old_counts = _converted_count_by_group(resolved_old)
    new_counts = _converted_count_by_group(resolved_new)

    medal_map = _medals_to_map(state.medals)

    for group_id, new_count in new_counts.items():
        old_count = old_counts.get(group_id, 0)
        if new_count == old_count:
            continue
        char_cfg = bundle.characters.get(group_id)
        if char_cfg is None or char_cfg.exp_up == 0:
            await client.send_message(12405, protobuf.SC_12405(result=LOVE_LETTER_RESULT_FAILED))
            return
        if group_id not in medal_map:
            medal_map[group_id] = LoveLetterMedalState(group_id=group_id)
        medal = medal_map[group_id]
        if new_count > old_count:
            delta = new_count - old_count
            medal.exp += delta * char_cfg.exp_up
            medal.level += delta
        else:
            delta = old_count - new_count
            exp_delta = delta * char_cfg.exp_up
            if medal.exp > exp_delta:
                medal.exp -= exp_delta
            else:
                medal.exp = 0
            if medal.level > delta:
                medal.level -= delta
            else:
                medal.level = 0

    for group_id, old_count in old_counts.items():
        if group_id in new_counts:
            continue
        char_cfg = bundle.characters.get(group_id)
        if char_cfg is None or char_cfg.exp_up == 0:
            continue
        medal = medal_map.get(group_id)
        if medal is None:
            continue
        exp_delta = old_count * char_cfg.exp_up
        if medal.exp > exp_delta:
            medal.exp -= exp_delta
        else:
            medal.exp = 0
        if medal.level > old_count:
            medal.level -= old_count
        else:
            medal.level = 0

    state.converted_items = converted_items
    state.medals = _medal_map_to_list(medal_map)
    save_commander_love_letter_state(state)
    await client.send_message(12405, protobuf.SC_12405(result=LOVE_LETTER_RESULT_SUCCESS))


def handle_love_letter_realize_gift(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_12404()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 12405, e
    asyncio.create_task(_love_letter_realize_gift(client, payload))
    return 0, 12405, None


async def _love_letter_level_up(client: Client, payload: protobuf.CS_12408):
    bundle = _load_love_letter_config_bundle()
    char_cfg = bundle.characters.get(payload.group_id)
    if char_cfg is None or char_cfg.exp_up == 0:
        await client.send_message(12409, protobuf.SC_12409(ret=LOVE_LETTER_RESULT_FAILED))
        return

    state = get_or_create_commander_love_letter_state(client.commander.commander_id)
    medal_map = _medals_to_map(state.medals)
    medal = medal_map.get(payload.group_id)
    if medal is None:
        medal = LoveLetterMedalState(group_id=payload.group_id)
        medal_map[payload.group_id] = medal

    threshold = (medal.level + 1) * char_cfg.exp_up
    if medal.exp < threshold:
        await client.send_message(12409, protobuf.SC_12409(ret=LOVE_LETTER_RESULT_FAILED))
        return

    medal.level = medal.exp // char_cfg.exp_up
    state.medals = _medal_map_to_list(medal_map)
    save_commander_love_letter_state(state)
    await client.send_message(12409, protobuf.SC_12409(ret=LOVE_LETTER_RESULT_SUCCESS))


def handle_love_letter_level_up(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_12408()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 12409, e
    asyncio.create_task(_love_letter_level_up(client, payload))
    return 0, 12409, None


async def _love_letter_get_content(client: Client, payload: protobuf.CS_12410):
    bundle = _load_love_letter_config_bundle()
    state = get_or_create_commander_love_letter_state(client.commander.commander_id)

    content = state.letter_contents.get(payload.letter_id)
    if content is None:
        content = bundle.letter_text_by_id.get(payload.letter_id, "")

    await client.send_message(12411, protobuf.SC_12411(content=content))


def handle_love_letter_get_content(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_12410()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 12411, e
    asyncio.create_task(_love_letter_get_content(client, payload))
    return 0, 12411, None
