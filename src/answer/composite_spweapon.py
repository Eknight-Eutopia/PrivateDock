import asyncio
from collections import Counter
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from src.orm.spweapon import create_owned_sp_weapon, remove_owned_sp_weapon, to_proto_owned_sp_weapon


def handle_composite_sp_weapon(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 14210
    payload = protobuf.CS_14209()
    payload.ParseFromString(buffer)

    template_id = payload.template_id
    response = protobuf.SC_14210(result=1)

    if template_id == 0 or client.commander is None:
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    commander = client.commander

    # 1. Consume material items
    item_counts = Counter(payload.item_id_list)
    for item_id, count in item_counts.items():
        if item_id > 0 and count > 0:
            commander.consume_item(item_id, count)

    # 2. Consume material spweapons (fodder)
    for spw_id in payload.spweapon_id_list:
        if spw_id > 0:
            remove_owned_sp_weapon(commander.commander_id, spw_id)
            if hasattr(commander, "owned_sp_weapons") and commander.owned_sp_weapons is not None:
                commander.owned_sp_weapons = [
                    s for s in commander.owned_sp_weapons
                    if (s.get("id") if isinstance(s, dict) else getattr(s, "id", 0)) != spw_id
                ]
            if hasattr(commander, "owned_sp_weapons_map") and commander.owned_sp_weapons_map is not None:
                commander.owned_sp_weapons_map.pop(spw_id, None)

    # 3. Deduct gold cost from config if available
    try:
        from src.orm.config_entry import get_config_entry_sync
        stat_entry = get_config_entry_sync("ShareCfg/spweapon_data_statistics.json", str(template_id))
        if stat_entry and stat_entry.data:
            upgrade_id = stat_entry.data.get("upgrade_id", 0)
            if upgrade_id > 0:
                up_entry = get_config_entry_sync("ShareCfg/spweapon_upgrade.json", str(upgrade_id))
                if up_entry and up_entry.data:
                    gold_cost = int(up_entry.data.get("create_use_gold", 0))
                    if gold_cost > 0 and commander.has_enough_gold(gold_cost):
                        commander.consume_resource(1, gold_cost)
    except Exception:
        pass

    # 4. Create new spweapon
    try:
        entry = create_owned_sp_weapon(commander.commander_id, template_id)
    except Exception as e:
        return 0, packet_id, e

    # 5. Update commander collections
    owned = list(getattr(commander, "owned_sp_weapons", []) or [])
    owned.append(entry)
    commander.owned_sp_weapons = owned
    if hasattr(commander, "owned_sp_weapons_map"):
        if commander.owned_sp_weapons_map is None:
            commander.owned_sp_weapons_map = {}
        commander.owned_sp_weapons_map[entry.id] = entry

    response.result = 0
    response.spweapon.CopyFrom(to_proto_owned_sp_weapon(entry))
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None

