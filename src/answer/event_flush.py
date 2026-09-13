import time
from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header

from src.orm import event_collection as ec
from src.answer.event_collection_spawn import refresh_commissions_sync


def handle_event_flush(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    from src.protobuf import protobuf

    flush_type = 0
    try:
        req = protobuf.CS_13009()
        req.ParseFromString(buffer)
        flush_type = req.type
    except Exception:
        pass

    try:
        # Top up the daily/urgent pools (urgent gets (re)spawned when empty).
        refresh_commissions_sync(client)
        rows = ec.list_commissions_sync(client.commander.commander_id)
    except Exception as e:
        return 0, 13010, e

    now = int(time.time())
    response = protobuf.SC_13010(result=0)
    for row in rows:
        over_time = row.expires_at or 0
        finish_time = row.finish_time or 0
        # Derive "ready" state from finish_time for in-progress commissions
        # (a completed-but-uncollected commission is still stored as STATE_STARTED
        # until the client collects it, so the ready status is computed here).
        if row.state == ec.STATE_STARTED and finish_time > 0 and now >= finish_time:
            state = ec.STATE_READY
        else:
            state = row.state
        ci = protobuf.COLLECTIONINFO(
            id=row.commission_id,
            finish_time=finish_time,
            over_time=over_time,
        )
        for sid in (row.ship_ids or []):
            ci.ship_id_list.append(int(sid))
        if hasattr(ci, "state"):
            ci.state = state
        response.collection_list.append(ci)

    data = response.SerializeToString()
    header = generate_packet_header(13010, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 13010, None


def _load_collection_template(collection_id: int):
    from src.orm.config_entry import get_config_entry
    from src.db.store import NotFoundError
    try:
        raw = get_config_entry("ShareCfg/collection_template.json", str(collection_id))
    except NotFoundError:
        return None
    except Exception:
        return None
    if isinstance(raw, dict):
        return raw
    return None
