from typing import Optional
from src.connection.client import Client
from src.connection.server import generate_packet_header


def handle_equiped_special_weapons(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    from src.protobuf import protobuf
    from src.orm.config_entry import list_config_entries
    spweapon_bag_size = 0
    try:
        entries = list_config_entries("ShareCfg/spweapon_data_statistics.json")
        spweapon_bag_size = len(entries) if entries else 0
    except Exception:
        pass
    response = protobuf.SC_14001(spweapon_bag_size=spweapon_bag_size)
    equip_map = getattr(client.commander, "owned_equipment_map", None) or {}
    for eq_id, owned in equip_map.items():
        count = owned.get("count", 0) if isinstance(owned, dict) else getattr(owned, "count", 0)
        if count == 0:
            continue
        ei = protobuf.EQUIPINFO()
        ei.id = eq_id if isinstance(eq_id, int) else (owned.get("equipment_id", eq_id) if isinstance(owned, dict) else 0)
        ei.count = count
        response.equip_list.append(ei)

    from src.orm.spweapon import to_proto_owned_sp_weapon
    owned_sp = getattr(client.commander, "owned_sp_weapons", []) or []
    for sp in owned_sp:
        if sp is not None:
            proto_sp = to_proto_owned_sp_weapon(sp)
            if proto_sp is not None:
                response.spweapon_list.append(proto_sp)

    data = response.SerializeToString()
    header = generate_packet_header(14001, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 14001, None


def list_special_weapons(commander) -> dict:
    from src.orm.config_entry import list_config_entries

    try:
        entries = list_config_entries("ShareCfg/spweapon_data_statistics.json")
    except Exception:
        entries = []

    owned_sp = getattr(commander, "owned_sp_weapons", {})
    spweapon_list = []
    for sp_id, sp_data in owned_sp.items():
        if isinstance(sp_data, dict):
            spweapon_list.append(sp_data)
        else:
            spweapon_list.append(getattr(sp_data, "__dict__", {"id": sp_id}))

    owned_equip = getattr(commander, "owned_equipment_map", {})
    equip_list = []
    for eq_id, owned in owned_equip.items():
        count = owned.get("count", 0) if isinstance(owned, dict) else getattr(owned, "count", 0)
        if count == 0:
            continue
        equip_list.append({
            "id": eq_id,
            "count": count,
        })

    return {
        "spweapon_bag_size": len(entries),
        "spweapon_list": spweapon_list,
        "equip_list": equip_list,
    }
