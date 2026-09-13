import json
from typing import Optional

from src.db.store import NotFoundError

COLORING_RESULT_SUCCESS = 0
COLORING_RESULT_FAILURE = 1
COLORING_TEMPLATE_CATEGORY = "sharecfgdata/activity_coloring_template.json"


def load_coloring_activity_pages(act_id: int) -> list:
    from .activity_templates import load_activity_template

    activity = load_activity_template(act_id)
    if activity.get("type") != 19:
        return []
    config_data = activity.get("config_data", [])
    if isinstance(config_data, str):
        config_data = json.loads(config_data)
    pages = []
    for raw in config_data:
        if isinstance(raw, list):
            entry = {"page_id": raw[0]}
            if len(raw) > 1:
                entry["reward_spec"] = raw[1:]
            pages.append(entry)
        elif isinstance(raw, (int, float)) and raw > 0:
            pages.append({"page_id": int(raw), "reward_spec": []})
    return pages


def load_coloring_template(page_id: int) -> Optional[dict]:
    from src.orm.config_entry import get_config_entry
    try:
        entry = get_config_entry(COLORING_TEMPLATE_CATEGORY, str(page_id))
    except NotFoundError:
        return None
    raw = entry.get("data") if isinstance(entry, dict) else entry
    if isinstance(raw, str):
        raw = json.loads(raw)
    return raw


def build_coloring_cell_template_lookup(template: dict) -> dict:
    lookup = {}
    for raw in template.get("cells", []):
        if len(raw) < 2:
            continue
        cell = {"row": raw[0], "column": raw[1]}
        if len(raw) > 2:
            cell["required"] = raw[2]
        else:
            cell["required"] = 0
        lookup[coloring_cell_key(cell["row"], cell["column"])] = cell
    return lookup


def coloring_cell_key(row: int, column: int) -> str:
    return f"{row}_{column}"


def get_or_create_coloring_state(commander_id: int, act_id: int) -> dict:
    import time
    from src.orm.commander_coloring_state import get_or_create_commander_coloring_state
    now = int(time.time())
    return get_or_create_commander_coloring_state(commander_id, act_id, now)


def coloring_is_page_claimed(state: dict, page_id: int) -> bool:
    for award in state.get("awards", []):
        if award.get("page_id") == page_id:
            return True
    return False


def coloring_get_page_fills(state: dict, page_id: int) -> dict:
    fills = {}
    for cell in state.get("cells", []):
        if cell.get("page_id") != page_id:
            continue
        fills[coloring_cell_key(cell.get("row", 0), cell.get("column", 0))] = cell
    return fills


def coloring_set_cell(state: dict, page_id: int, row: int, column: int, color: int):
    key = coloring_cell_key(row, column)
    cells = state.get("cells", [])
    for i, cell in enumerate(cells):
        if cell.get("page_id") != page_id:
            continue
        if coloring_cell_key(cell.get("row", 0), cell.get("column", 0)) != key:
            continue
        if color == 0:
            state["cells"] = cells[:i] + cells[i + 1:]
            return
        cells[i]["color"] = color
        return
    if color == 0:
        return
    cells.append({"page_id": page_id, "row": row, "column": column, "color": color})
    state["cells"] = cells


def coloring_clear_page(state: dict, page_id: int):
    cells = state.get("cells", [])
    if not cells:
        return
    next_cells = [c for c in cells if c.get("page_id") != page_id]
    state["cells"] = next_cells


def coloring_is_page_complete(template: dict, fills: dict) -> bool:
    if template.get("blank", 0) == 1:
        return True
    lookup = build_coloring_cell_template_lookup(template)
    for key in lookup:
        if key not in fills:
            return False
    return True


def coloring_current_page_id(state: dict, pages: list) -> int:
    if not pages:
        return 0
    current = pages[0]["page_id"]
    for idx, page in enumerate(pages):
        if coloring_is_page_claimed(state, page["page_id"]):
            if idx + 1 < len(pages):
                current = pages[idx + 1]["page_id"]
            else:
                current = pages[idx]["page_id"]
            continue
        current = page["page_id"]
        break
    return current


def coloring_resolve_claim_drops(spec: list) -> list:
    if not spec:
        return []
    if len(spec) == 1:
        if spec[0] == 0:
            return []
        return [{"type": 2, "id": spec[0], "number": 1}]
    if len(spec) >= 3:
        if spec[2] == 0:
            return []
        return [{"type": spec[0], "id": spec[1], "number": spec[2]}]
    if spec[0] == 0 or spec[1] == 0:
        return []
    return [{"type": spec[0], "id": spec[1], "number": 1}]


def coloring_drops_to_state(drops: list) -> list:
    out = []
    for drop in drops:
        if not drop:
            continue
        out.append({"type": drop.get("type", 0), "id": drop.get("id", 0), "number": drop.get("number", 0)})
    return out


def coloring_drops_from_state(drops: list) -> list:
    out = []
    for drop in drops:
        out.append({"type": drop.get("type", 0), "id": drop.get("id", 0), "number": drop.get("number", 0)})
    return out


def coloring_build_cell_list_for_page(state: dict, page_id: int) -> list:
    lst = []
    for cell in state.get("cells", []):
        if cell.get("page_id") != page_id:
            continue
        lst.append({
            "row": cell.get("row", 0),
            "column": cell.get("column", 0),
            "color": cell.get("color", 0),
        })
    lst.sort(key=lambda x: (x["row"], x["column"]))
    return lst


def coloring_build_award_list(state: dict) -> list:
    lst = []
    for award in state.get("awards", []):
        drops = coloring_drops_from_state(award.get("drops", []))
        drops.sort(key=lambda x: (x.get("type", 0), x.get("id", 0)))
        lst.append({"id": award.get("page_id", 0), "award_list": drops})
    lst.sort(key=lambda x: x["id"])
    return lst


def coloring_add_claim(state: dict, page_id: int, drops: list):
    for i, award in enumerate(state.get("awards", [])):
        if award.get("page_id") == page_id:
            state["awards"][i]["drops"] = coloring_drops_to_state(drops)
            return
    state.setdefault("awards", []).append({"page_id": page_id, "drops": coloring_drops_to_state(drops)})


def coloring_build_color_list(client_color_counts: dict) -> list:
    ids = sorted(client_color_counts.keys())
    lst = []
    for item_id in ids:
        lst.append({"id": item_id, "number": client_color_counts[item_id]})
    return lst


def coloring_apply_drops(commander_id: int, drops: list):
    drop_map = {}
    for drop in drops:
        if not drop:
            continue
        key = f"{drop.get('type', 0)}_{drop.get('id', 0)}"
        existing = drop_map.get(key)
        if existing is not None:
            existing["number"] = existing.get("number", 0) + drop.get("number", 0)
            continue
        drop_map[key] = {"type": drop.get("type", 0), "id": drop.get("id", 0), "number": drop.get("number", 0)}
    from src.orm.item import upsert_item_count
    from src.orm.resource import upsert_resource_amount
    for drop in drop_map.values():
        drop_type = drop.get("type", 0)
        drop_id = drop.get("id", 0)
        number = drop.get("number", 0)
        if drop_type in (14, 15, 31):
            from src.orm.commander_attire import grant_commander_attire_drop_sync
            grant_commander_attire_drop_sync(commander_id, drop_type, drop_id, number)
        elif drop_type == 1:
            upsert_resource_amount(commander_id, drop_id, number)
        elif drop_type == 2:
            upsert_item_count(commander_id, drop_id, number)
