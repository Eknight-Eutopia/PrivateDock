import json
import time
from typing import Optional

from src.connection.client import Client
from src.consts.drop_types import (
    DROP_TYPE_EQUIP,
    DROP_TYPE_FURNITURE,
    DROP_TYPE_ITEM,
    DROP_TYPE_RESOURCE,
    DROP_TYPE_SHIP,
    DROP_TYPE_SKIN,
)
from src.protobuf import protobuf

STOREUP_TEMPLATE_CATEGORY = "ShareCfg/storeup_data_template.json"


def _load_storeup_data_template(
    storeup_id: int,
) -> tuple[Optional[dict], bool]:
    from src.orm.config_entry import get_config_entry, list_config_entries
    from src.db.store import NotFoundError
    try:
        raw = get_config_entry(STOREUP_TEMPLATE_CATEGORY, str(storeup_id))
        if raw is None:
            raise NotFoundError()
        data = getattr(raw, "data", None)
        template = data if isinstance(data, dict) else json.loads(data) if isinstance(data, str) else data
        if template is None:
            raise NotFoundError()
        if template.get("id", 0) == 0:
            template["id"] = storeup_id
        return template, True
    except NotFoundError:
        pass

    try:
        entries = list_config_entries(STOREUP_TEMPLATE_CATEGORY)
    except Exception:
        return None, False

    for entry in entries:
        data = entry.get("data", None) if isinstance(entry, dict) else getattr(entry, "data", None)
        if data is None:
            continue
        try:
            parsed = json.loads(data) if isinstance(data, str) else data
        except Exception:
            continue
        if isinstance(parsed, dict):
            if parsed.get("id") == storeup_id:
                if parsed.get("id", 0) == 0:
                    parsed["id"] = storeup_id
                return parsed, True
        elif isinstance(parsed, list):
            for item in parsed:
                if item.get("id") == storeup_id:
                    if item.get("id", 0) == 0:
                        item["id"] = storeup_id
                    return item, True

    return None, False


async def _storeup_star_count(commander_id: int, groups: list[int]) -> int:
    from src.db.store import get_default_store
    store = get_default_store()
    if store is None:
        return 0

    try:
        rows = await store.afetch("""
            SELECT s.ship_id / 10 AS group_id, MAX(sh.star) AS max_star
            FROM owned_ships s
            INNER JOIN ships sh ON s.ship_id = sh.template_id
            WHERE s.owner_id = $1
            GROUP BY group_id
        """, commander_id)
    except Exception:
        return 0
    lookup = {r["group_id"]: r["max_star"] for r in rows}
    return sum(lookup.get(g, 0) for g in groups)


async def handle_claim_collection_award(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_17005()
    payload.ParseFromString(buffer)
    result_invalid = 1
    result_not_eligible = 2
    result_wrong_tier = 3
    result_unsupported = 4
    result_db_error = 5

    storeup_id = payload.id
    award_index = payload.award_index
    if storeup_id == 0 or award_index == 0:
        await client.send_message(17006, protobuf.SC_17006(result=result_invalid))
        return 0, 17006, None

    template, ok = _load_storeup_data_template(storeup_id)
    if not ok:
        await client.send_message(17006, protobuf.SC_17006(result=result_invalid))
        return 0, 17006, None
    if template is None:
        await client.send_message(17006, protobuf.SC_17006(result=result_db_error))
        return 0, 17006, None

    award_display = template.get("award_display", [])
    level = template.get("level", [])
    if award_index > len(award_display) or award_index > len(level):
        await client.send_message(17006, protobuf.SC_17006(result=result_invalid))
        return 0, 17006, None

    char_list = template.get("char_list", [])
    star_count = await _storeup_star_count(client.commander.commander_id, char_list)

    drop = award_display[award_index - 1]
    if len(drop) < 3:
        await client.send_message(17006, protobuf.SC_17006(result=result_invalid))
        return 0, 17006, None

    drop_type, drop_id, drop_count = drop[0], drop[1], drop[2]
    if drop_count == 0:
        await client.send_message(17006, protobuf.SC_17006(result=result_invalid))
        return 0, 17006, None

    if level[award_index - 1] > star_count:
        await client.send_message(17006, protobuf.SC_17006(result=result_not_eligible))
        return 0, 17006, None

    from src.orm.commander_storeup_award_progress import try_advance_commander_storeup_award_index
    try:
        advanced = try_advance_commander_storeup_award_index(
            client.commander.commander_id, storeup_id, award_index,
        )
    except Exception as e:
        await client.send_message(17006, protobuf.SC_17006(result=result_db_error))
        return 0, 17006, e

    if not advanced:
        await client.send_message(17006, protobuf.SC_17006(result=result_wrong_tier))
        return 0, 17006, None

    from src.orm.item import add_item
    from src.orm.owned_equipment import add_owned_equipment
    from src.orm.owned_ship import add_ship
    from src.consts.drop_types import (DROP_TYPE_ICON_FRAME, DROP_TYPE_CHAT_FRAME, DROP_TYPE_COMBAT_UI_STYLE)
    from src.orm.owned_skin import give_skin
    from src.orm.resource import add_resource
    from src.orm.commander_furniture import add_commander_furniture
    now = int(time.time())

    try:
        if drop_type in (DROP_TYPE_ICON_FRAME, DROP_TYPE_CHAT_FRAME, DROP_TYPE_COMBAT_UI_STYLE):
            from src.orm.commander_attire import grant_commander_attire_drop_sync
            grant_commander_attire_drop_sync(client.commander.commander_id, drop_type, drop_id, drop_count)
        elif drop_type == DROP_TYPE_RESOURCE:
            add_resource(client.commander.commander_id, drop_id, drop_count)
        elif drop_type == DROP_TYPE_ITEM:
            add_item(client.commander.commander_id, drop_id, drop_count)
        elif drop_type == DROP_TYPE_EQUIP:
            add_owned_equipment(client.commander.commander_id, drop_id, drop_count)
        elif drop_type == DROP_TYPE_SHIP:
            for _ in range(drop_count):
                add_ship(client.commander.commander_id, drop_id)
        elif drop_type == DROP_TYPE_FURNITURE:
            add_commander_furniture(client.commander.commander_id, drop_id, drop_count, now)
        elif drop_type == DROP_TYPE_SKIN:
            for _ in range(drop_count):
                give_skin(client.commander.commander_id, drop_id)
        else:
            await client.send_message(17006, protobuf.SC_17006(result=result_unsupported))
            return 0, 17006, None
    except Exception as e:
        await client.send_message(17006, protobuf.SC_17006(result=result_db_error))
        return 0, 17006, e

    await client.send_message(17006, protobuf.SC_17006(result=0))
    return 0, 17006, None
