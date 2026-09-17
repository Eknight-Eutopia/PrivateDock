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

    if entry is not None:
        data = entry.data
        if isinstance(data, str):
            import json
            try:
                data = json.loads(data)
            except Exception:
                data = None
        if isinstance(data, dict):
            usage_arg = data.get("usage_arg")
            if isinstance(usage_arg, list):
                for v in usage_arg:
                    try:
                        iv = int(v)
                    except (ValueError, TypeError):
                        continue
                    if iv > 0:
                        return iv
            elif usage_arg is not None:
                try:
                    iv = int(usage_arg)
                    if iv > 0:
                        return iv
                except (ValueError, TypeError):
                    pass

    # Fallback to gameset technology_catchup_itemid for catchup items (e.g. 20101 -> 10000)
    try:
        gameset = get_config_entry("ShareCfg/gameset.json", "technology_catchup_itemid")
    except Exception:
        gameset = None
    if gameset is not None:
        data = gameset.data
        if isinstance(data, str):
            import json
            try:
                data = json.loads(data)
            except Exception:
                data = None
        if isinstance(data, dict):
            for pair in data.get("description") or []:
                if isinstance(pair, list) and len(pair) >= 2 and int(pair[0] or 0) == item_id:
                    return int(pair[1] or 0)

    return 0
