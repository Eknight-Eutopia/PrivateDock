from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header

from src.answer.event_collection_spawn import refresh_commissions_sync
from src.orm import event_collection as ec


def handle_event_collection_info(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    from src.protobuf import protobuf
    from src.answer.event_collection_start import _max_commission_slots

    try:
        rows = refresh_commissions_sync(client)
    except Exception as e:
        return 0, 13002, e

    response = protobuf.SC_13002(max_team=_max_commission_slots(client))
    now = int(__import__("time").time())

    for row in rows:
        # The client computes commission state/countdown purely from
        # finish_time + over_time (see EN/model/vo/eventinfo.lua GetState /
        # GetCountDownTime). over_time MUST be an absolute future timestamp
        # (the commission's expiry), otherwise GetCountDownTime() is nil and the
        # urgent/night tab keeps flushing forever (checkNightEvent never sees a
        # night commission with a live countdown).
        over_time = row.expires_at or 0
        finish_time = row.finish_time or 0
        # Derive "ready" state from finish_time for in-progress commissions
        # (a completed-but-uncollected commission is still stored as STATE_STARTED
        # until collected, so the ready status is computed here).
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
        # Some clients expect a state/status field; set it if present.
        if hasattr(ci, "state"):
            ci.state = state
        response.collection_list.append(ci)

    data = response.SerializeToString()
    header = generate_packet_header(13002, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 13002, None


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
