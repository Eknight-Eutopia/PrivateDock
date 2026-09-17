from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.orm.commander_box import ensure_commander_boxes
from src.orm.commander_box_daily import get_commander_box_daily_usage
from src.orm.commander_meow import list_commander_meows, populate_proto_commander_info
from src.protobuf import protobuf


def handle_meowfficers(
    _buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    cid = client.commander.commander_id
    usage_cnt = get_commander_box_daily_usage(cid)

    response = protobuf.SC_25001(usage_count=usage_cnt)

    try:
        boxes = ensure_commander_boxes(cid)
        active_boxes = []
        for b in boxes:
            p_id = b.get("pool_id", 0) if isinstance(b, dict) else getattr(b, "pool_id", 0)
            if p_id != 0:
                active_boxes.append(b)

        active_boxes.sort(key=lambda b: (
            b.get("begin_time", 0) if isinstance(b, dict) else getattr(b, "begin_time", 0),
            b.get("box_id", b.get("id", 0)) if isinstance(b, dict) else getattr(b, "box_id", getattr(b, "id", 0)),
        ))

        for b in active_boxes:
            entry = protobuf.COMMANDERBOXINFO()
            entry.id = b.get("box_id", b.get("id", 0)) if isinstance(b, dict) else getattr(b, "box_id", getattr(b, "id", 0))
            entry.poolId = b.get("pool_id", 0) if isinstance(b, dict) else getattr(b, "pool_id", 0)
            entry.begin_time = b.get("begin_time", 0) if isinstance(b, dict) else getattr(b, "begin_time", 0)
            entry.finish_time = b.get("finish_time", 0) if isinstance(b, dict) else getattr(b, "finish_time", 0)
            response.box.append(entry)
    except Exception:
        pass

    try:
        meows = list_commander_meows(cid)
        for m in meows:
            entry = protobuf.COMMANDERINFO()
            populate_proto_commander_info(entry, m)
            response.commanders.append(entry)
    except Exception:
        pass

    try:
        from src.orm.commander_prefab import list_commander_prefab_fleets
        prefabs = list_commander_prefab_fleets(cid)
        for p in prefabs:
            pf = response.presets.add()
            pf.id = p.get("prefab_id", 0)
            pf.name = p.get("name", "")
            for s in p.get("commander_slots", []):
                slot_info = pf.commandersid.add()
                slot_info.pos = s.get("pos", 0)
                slot_info.id = s.get("id", 0)
    except Exception:
        pass

    data = response.SerializeToString()
    header = generate_packet_header(25001, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 25001, None
