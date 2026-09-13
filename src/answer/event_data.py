from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.protobuf import protobuf


def handle_event_data(
    _buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    from src.answer.gameroom import load_game_room_template_ids, load_game_room_state as load_sync_game_room_state, list_game_room_scores as list_sync_game_room_scores
    from datetime import datetime, timezone

    try:
        room_ids = load_game_room_template_ids()
    except Exception as e:
        return 0, 26120, e
    try:
        state = load_sync_game_room_state(client.commander.commander_id, datetime.now(timezone.utc))
    except Exception as e:
        return 0, 26120, e
    try:
        scores = list_sync_game_room_scores(client.commander.commander_id)
    except Exception as e:
        return 0, 26120, e

    score_by_room = {s["room_id"]: s["max_score"] for s in scores}

    response = protobuf.SC_26120()
    response.weekly_free = 0 if state.get("weekly_claimed", False) else 1
    response.monthly_ticket = state.get("monthly_ticket", 0)
    response.pay_coin_count = state.get("pay_coin_count", 0)
    response.first_enter = 1 if state.get("first_enter_claimed", False) else 0
    for room_id in room_ids:
        room = protobuf.GAMEROOM()
        room.roomid = room_id
        room.max_score = score_by_room.get(room_id, 0)
        response.rooms.append(room)

    data = response.SerializeToString()
    header = generate_packet_header(26120, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 26120, None
