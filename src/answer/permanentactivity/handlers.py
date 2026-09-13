from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.protobuf import protobuf


def handle_permanent_activities(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    # SC_11210 carries ONLY the player's Permanent-Activity GALLERY STATE, not
    # the gallery list itself (the client builds the card list from its own
    # bundled `activity_task_permanent`; `activity_group` 1000 => Mini-Event
    # gallery). Wire semantics (ActivityPermanentProxy.on(11210)):
    #   permanent_activity = ids the player has FINISHED   -> cards render Completed
    #   permanent_now       = the one currently selected    -> cards render Doing
    # Sending all gallery ids in `permanent_activity` marks every card Completed
    # and makes Mini-Event Gallery unusable (cannot select/rush another).
    from src.orm.activity_permanent_state import get_or_create_activity_permanent_state
    try:
        state_orm = get_or_create_activity_permanent_state(client.commander.commander_id)
    except Exception as e:
        return 0, 11210, e

    state = {c.name: getattr(state_orm, c.name) for c in state_orm.__table__.columns}
    finished = state.get("finished_activity_ids") or []
    if isinstance(finished, dict):
        finished = list(finished.keys())
    current = int(state.get("current_activity_id", 0) or 0)

    response = protobuf.SC_11210()
    response.permanent_activity.extend(int(x) for x in finished)
    response.permanent_now = current

    data = response.SerializeToString()
    header = generate_packet_header(11210, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 11210, None
