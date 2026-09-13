import asyncio
import re
import threading
import time
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

SHIP_EVALUATION_COMMENT_MAX_RUNES = 80
SHIP_EVALUATION_DAILY_COMMENT_MAX = 5
SHIP_EVALUATION_COMMENT_MIN_LEVEL = 1


class ShipDiscussState:
    def __init__(self, ship_group_id: int):
        self.ship_group_id = ship_group_id
        self.day_key = ""
        self.next_discuss_id = 0
        self.discuss_count = 0
        self.daily_discuss_count = 0
        self.discuss_list = []
        self.reviewed_discuss_by_commander = None
        self.lock = threading.Lock()


_ship_discuss_store: dict[int, ShipDiscussState] = {}
_ship_discuss_store_lock = threading.Lock()


def _get_ship_discuss_state(ship_group_id: int) -> ShipDiscussState:
    now = time.time()
    day_key = time.strftime("%Y-%m-%d", time.gmtime(now))

    with _ship_discuss_store_lock:
        state = _ship_discuss_store.get(ship_group_id)
        if state is None:
            state = ShipDiscussState(ship_group_id)
            _ship_discuss_store[ship_group_id] = state

    with state.lock:
        if state.day_key != day_key:
            state.day_key = day_key
            state.daily_discuss_count = 0
            state.reviewed_discuss_by_commander = None

    return state


def _comment_contains_banned_word(comment: str) -> bool:
    from src.config.config import current
    cfg = current()
    create_cfg = cfg.create_player
    if create_cfg.name_blacklist:
        lower = comment.lower()
        for blocked in create_cfg.name_blacklist:
            blocked = blocked.strip()
            if not blocked:
                continue
            if blocked.lower() in lower:
                return True
    if create_cfg.name_illegal_pattern:
        try:
            if re.search(create_cfg.name_illegal_pattern, comment):
                return True
        except re.error:
            pass
    return False


def _count_ship_hearts() -> int:
    return 0


def _send_eval_result(client, result: int, ship_discuss=None, need_level: int = 0):
    resp = protobuf.SC_17104(result=result)
    if need_level:
        resp.need_level = need_level
    if ship_discuss is not None:
        resp.ship_discuss.CopyFrom(ship_discuss)
    asyncio.create_task(client.send_message(17104, resp))


def handle_post_ship_evaluation_comment(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    import json
    payload = json.loads(buffer.decode("utf-8", errors="replace"))

    if client.commander is None:
        _send_eval_result(client, 1)
        return 0, 17104, None

    comment = payload.get("context", "")
    if not comment.strip():
        _send_eval_result(client, 1)
        return 0, 17104, None

    if len(comment) > SHIP_EVALUATION_COMMENT_MAX_RUNES:
        _send_eval_result(client, 2011)
        return 0, 17104, None

    if _comment_contains_banned_word(comment):
        _send_eval_result(client, 2013)
        return 0, 17104, None

    ship_group_id = payload.get("ship_group_id", 0)
    if ship_group_id == 0:
        _send_eval_result(client, 1)
        return 0, 17104, None

    if client.commander.level < SHIP_EVALUATION_COMMENT_MIN_LEVEL:
        _send_eval_result(client, 41, need_level=SHIP_EVALUATION_COMMENT_MIN_LEVEL)
        return 0, 17104, None

    state = _get_ship_discuss_state(ship_group_id)
    heart_count = _count_ship_hearts()

    with state.lock:
        if state.daily_discuss_count >= SHIP_EVALUATION_DAILY_COMMENT_MAX:
            _send_eval_result(client, 1)
            return 0, 17104, None

        state.next_discuss_id += 1

        state.discuss_list.append({
            "id": state.next_discuss_id,
            "nick_name": client.commander.name,
            "context": comment,
            "good_count": 0,
            "bad_count": 0,
        })
        state.discuss_count += 1
        state.daily_discuss_count += 1

        discuss_list_copy = list(state.discuss_list)

    ship_discuss = protobuf.SHIP_DISCUSS_INFO(
        ship_group_id=ship_group_id,
        discuss_count=state.discuss_count,
        heart_count=heart_count,
        daily_discuss_count=state.daily_discuss_count,
    )
    for entry in discuss_list_copy:
        ship_discuss.discuss_list.append(protobuf.DISCUSS_INFO(
            id=entry["id"],
            nick_name=entry["nick_name"],
            context=entry["context"],
            good_count=entry["good_count"],
            bad_count=entry["bad_count"],
        ))

    _send_eval_result(client, 0, ship_discuss=ship_discuss)
    return 0, 17104, None
