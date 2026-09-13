import json


def dorm_static_map_size(level: int) -> dict:
    min_val = 12
    if level > 1:
        min_val = 12 - (level - 1) * 4
    return {"min_x": min_val, "min_y": min_val, "max_x": 23, "max_y": 23}


def load_furniture_template(furniture_id: int) -> dict:
    from src.orm.config_entry import get_config_entry
    entry = get_config_entry("ShareCfg/furniture_data_template.json", str(furniture_id))
    data = entry.data if hasattr(entry, 'data') else entry
    if isinstance(data, str):
        data = json.loads(data)
    tpl = data
    if tpl.get("id", 0) == 0:
        tpl["id"] = furniture_id
    return tpl


def resolve_furniture_template_id(raw_id: int) -> int:
    try:
        load_furniture_template(raw_id)
        return raw_id
    except Exception:
        pass
    if raw_id >= 100:
        base = raw_id // 100
        try:
            load_furniture_template(base)
            return base
        except Exception:
            pass
    for i in range(100):
        if raw_id < i:
            break
        base = raw_id - i
        try:
            tpl = load_furniture_template(base)
            if tpl.get("count", 0) > i:
                return base
        except Exception:
            continue
    if raw_id > 10000000:
        base = raw_id // 10000000
        idx = raw_id % 10
        try:
            tpl = load_furniture_template(base)
            if tpl.get("count", 0) > idx:
                return base
        except Exception:
            pass
    return 0


def _is_mat_or_paper(tpl: dict) -> bool:
    return tpl.get("type", 0) in (1, 4, 5, 10)


def _footprint(tpl: dict, direction: int) -> tuple:
    size = tpl.get("size", [])
    if len(size) < 2:
        return 0, 0
    if direction == 1:
        return size[0], size[1]
    return size[1], size[0]


def _val(obj, key, default=0):
    """Get value from dict (.get) or protobuf (getattr) object."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def validate_furniture_put_list(furniture_list: list, floor: int, map_size: dict) -> None:
    items = []
    by_tpl: dict[int, list] = {}

    for f in furniture_list:
        raw_id = int(_val(f, "id", "0"))
        tpl_id = resolve_furniture_template_id(raw_id)
        if tpl_id == 0:
            raise ValueError(f"unknown furniture template id {raw_id}")
        tpl = load_furniture_template(tpl_id)
        direction = _val(f, "dir", 0)
        if direction > 2:
            raise ValueError(f"invalid dir {direction}")

        child_ids = []
        child_list = _val(f, "child", [])
        for c in child_list:
            child_ids.append(int(_val(c, "id", "0")))

        item = {
            "raw_id": raw_id,
            "tpl_id": tpl_id,
            "tpl": tpl,
            "x": _val(f, "x", 0),
            "y": _val(f, "y", 0),
            "dir": direction,
            "parent": _val(f, "parent", 0),
            "child_id": child_ids,
        }
        items.append(item)
        by_tpl.setdefault(tpl_id, []).append(item)

    def _base(ref: int) -> int:
        return resolve_furniture_template_id(ref) if ref else 0

    occupied = {}
    for item in items:
        if item["tpl"].get("belong", 0) != 1:
            continue
        if _is_mat_or_paper(item["tpl"]):
            continue
        if item["parent"] != 0:
            continue
        size_x, size_y = _footprint(item["tpl"], item["dir"])
        for x in range(item["x"], item["x"] + size_x):
            if x not in occupied:
                occupied[x] = {}
            for y in range(item["y"], item["y"] + size_y):
                if occupied[x].get(y, False):
                    raise ValueError("incorrect position")
                occupied[x][y] = True

    for item in items:
        if floor == 0:
            raise ValueError("floor should exist")

        if item["parent"] != 0:
            candidates = by_tpl.get(_base(item["parent"]), [])
            found = False
            ibase = item["tpl_id"]
            for cand in candidates:
                for cid in cand.get("child_id", []):
                    if _base(cid) == ibase:
                        found = True
                        break
                if found:
                    break
            if not found:
                raise ValueError("incorrect [parent -> child] relation")

        for cid in item.get("child_id", []):
            candidates = by_tpl.get(_base(cid), [])
            ok = False
            ibase = item["tpl_id"]
            for cand in candidates:
                if _base(cand.get("parent", 0)) == ibase:
                    ok = True
                    break
            if not ok:
                raise ValueError("incorrect [child -> parent] relation")

        if item["tpl"].get("belong", 0) == 1 and item["tpl"].get("type", 0) not in (1, 4) and item["parent"] == 0:
            size_x, size_y = _footprint(item["tpl"], item["dir"])
            for x in range(item["x"], item["x"] + size_x):
                for y in range(item["y"], item["y"] + size_y):
                    if x < map_size["min_x"] or y < map_size["min_y"] or x > map_size["max_x"] or y > map_size["max_y"]:
                        raise ValueError("out side")

        if item["tpl"].get("belong", 0) == 3 and item["x"] >= map_size["max_x"] + 1:
            raise ValueError("out side")
        if item["tpl"].get("belong", 0) == 4 and item["y"] >= map_size["max_y"] + 1:
            raise ValueError("out side")
