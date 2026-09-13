import json
from typing import Optional


def add_trans_use_items(dst: dict[int, int], raw) -> Optional[Exception]:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not raw:
        return None
    if not isinstance(raw, list):
        return None
    for pair in raw:
        if not isinstance(pair, list) or len(pair) != 2:
            return None
        item_id, count = pair[0], pair[1]
        if item_id == 0 or count == 0:
            continue
        dst[item_id] = dst.get(item_id, 0) + count
    return None
