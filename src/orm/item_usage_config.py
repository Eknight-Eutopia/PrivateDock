from __future__ import annotations

from src.orm.config_entry import get_config_entry
from src.db.store import NotFoundError


async def load_item_usage_exp(item_id: int) -> int:
    """Blueprint exp granted per unit of a shipyard strengthen item.

    Mirrors Go orm.LoadItemUsageExp: the value is the first element of the
    item's `usage_arg` in item_data_statistics (ShareCfg fallback). The previous
    port queried a non-existent `item_usage_exp` table and always failed, which
    silently broke shipyard blueprint exp gain (handler returned result=1).
    """
    try:
        entry = get_config_entry("sharecfgdata/item_data_statistics.json", str(item_id))
    except NotFoundError:
        try:
            entry = get_config_entry("ShareCfg/item_data_statistics.json", str(item_id))
        except NotFoundError:
            return 0
    except Exception:
        return 0

    if entry is None:
        return 0
    data = entry.data
    if not isinstance(data, dict):
        return 0
    usage_arg = data.get("usage_arg")
    if usage_arg is None:
        return 0
    if isinstance(usage_arg, list):
        for v in usage_arg:
            try:
                iv = int(v)
            except (ValueError, TypeError):
                continue
            if iv > 0:
                return iv
        return 0
    try:
        iv = int(usage_arg)
    except (ValueError, TypeError):
        return 0
    return iv if iv > 0 else 0
