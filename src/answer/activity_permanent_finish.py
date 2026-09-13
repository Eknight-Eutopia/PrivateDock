import asyncio
from typing import Optional

from src.connection.client import Client
from src.connection.server import send_proto_message
from src.protobuf import protobuf


def _extract_typ(buffer: bytes) -> int:
    """CS_11208 carries both `activity_id` (field 1) and `typ` (finish=1 /
    stop=2) on the wire. Walk the raw wire format instead:
    the first varint field that is NOT field 1 is `typ`
    (the client message has exactly these two scalar fields)."""
    try:
        i = 0
        n = len(buffer)
        while i < n:
            key = 0
            shift = 0
            while True:
                b = buffer[i]
                i += 1
                key |= (b & 0x7F) << shift
                if not (b & 0x80):
                    break
                shift += 7
            field_num = key >> 3
            wire_type = key & 0x7
            if wire_type == 0:  # varint
                value = 0
                shift = 0
                while True:
                    b = buffer[i]
                    i += 1
                    value |= (b & 0x7F) << shift
                    if not (b & 0x80):
                        break
                    shift += 7
                if field_num != 1:
                    return int(value)
            elif wire_type == 1:  # fixed64
                i += 8
            elif wire_type == 2:  # length-delimited
                length = 0
                shift = 0
                while True:
                    b = buffer[i]
                    i += 1
                    length |= (b & 0x7F) << shift
                    if not (b & 0x80):
                        break
                    shift += 7
                i += length
            elif wire_type == 5:  # fixed32
                i += 4
            else:
                break
    except (IndexError, ValueError):
        pass
    return 1  # default = finish (legacy behavior when typ is absent)


def handle_activity_permanent_finish(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_11208()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 11209, e

    activity_id = payload.activity_id
    typ = _extract_typ(buffer)
    # typ=1 -> finish (activity completed, claimable -> mark finished)
    # typ=2 -> stop  (player abandons the current selection; the client sends
    #          this automatically when switching to another gallery activity)
    response = protobuf.SC_11209(result=1)

    if activity_id == 0:
        asyncio.create_task(send_proto_message(11209, client, response))
        return 0, 11209, None

    from src.orm.config_entry import get_config_entry
    from src.db.store import NotFoundError
    try:
        get_config_entry("ShareCfg/activity_task_permanent.json", str(activity_id))
    except (NotFoundError, Exception):
        asyncio.create_task(send_proto_message(11209, client, response))
        return 0, 11209, None

    from src.orm.activity_permanent_state import get_or_create_activity_permanent_state
    try:
        state_orm = get_or_create_activity_permanent_state(client.commander.commander_id)
        state = {c.name: getattr(state_orm, c.name) for c in state_orm.__table__.columns}
    except Exception as e:
        return 0, 11209, e

    current_id = int(state.get("current_activity_id", 0))
    if current_id != activity_id:
        asyncio.create_task(send_proto_message(11209, client, response))
        return 0, 11209, None

    if typ == 2:
        # Stop: drop the selection without marking the activity finished.
        state_orm.current_activity_id = 0
    else:
        finished_ids = [int(x) for x in state.get("finished_activity_ids", [])]
        if activity_id not in finished_ids:
            finished_ids.append(activity_id)
        state_orm.finished_activity_ids = finished_ids
        state_orm.current_activity_id = 0

    from src.orm.activity_permanent_state import save_activity_permanent_state
    try:
        save_activity_permanent_state(state_orm)
    except Exception as e:
        return 0, 11209, e

    # Leaving the activity (finish OR abandon) eliminates its tasks: each
    # gallery entry owns a private 35xxx task block, and the client renders
    # the sub-page from TaskProxy. Leftovers would pollute the commander's
    # SC_20001 sync forever and (for an abandoned run) would look like a
    # half-done progress bar next time the same activity is started. The
    # per-activity day state is dropped too, so a restart begins at day 1.
    _eliminate_gallery_tasks(client, client.commander.commander_id, activity_id)

    response.result = 0
    asyncio.create_task(send_proto_message(11209, client, response))
    return 0, 11209, None


def _eliminate_gallery_tasks(client, commander_id: int, activity_id: int) -> None:
    """Delete the activity's tasks (eliminate_task_id) from commander_tasks,
    push SC_20004 so the client's TaskProxy drops them, and reset the stored
    day. Called on both finish (typ=1) and stop/abandon (typ=2)."""
    try:
        from src.answer.activity_permanent_start import _gallery_task_ids
        ids = _gallery_task_ids(activity_id)
    except Exception:
        ids = []
    if not ids:
        return
    try:
        from src.orm.commander_task import delete_commander_tasks
        delete_commander_tasks(commander_id, ids)
        from src.db.store import get_default_store
        store = get_default_store()
        store.execute(
            "DELETE FROM activity_store_states WHERE commander_id=$1 AND activity_id=$2",
            commander_id, activity_id,
        )
        response = protobuf.SC_20004()
        response.id_list.extend(int(x) for x in ids)
        asyncio.create_task(send_proto_message(20004, client, response))
    except Exception:
        pass

