import json
import math
import random
from dataclasses import dataclass
from typing import Optional

from src.orm.chapter import delete_chapter_state as _sync_delete_chapter_state, get_chapter_drops as _sync_get_chapter_drops, ensure_chapter_progress as _sync_ensure_chapter_progress
from src.orm.config_entry import fetch_config_entries_data, fetch_config_entry_data
from src.orm.equipment import list_owned_ship_equipment as _sync_list_owned_ship_equipment
from src.orm import get_chapter_state as _sync_get_chapter_state, upsert_chapter_state as _sync_upsert_chapter_state, get_owned_ship_transforms as _sync_get_owned_ship_transforms

CHAPTER_CHANCE_BASE = 10000

CHAPTER_OP_RETREAT = 0
CHAPTER_OP_MOVE = 1
CHAPTER_OP_AMBUSH = 4
CHAPTER_OP_SUPPLY = 7
CHAPTER_OP_REPAIR = 6
CHAPTER_OP_STRATEGY = 5
CHAPTER_OP_ENEMY_ROUND = 8
CHAPTER_OP_SUB_STATE = 9
CHAPTER_OP_SUB_TELEPORT = 19
CHAPTER_OP_REQUEST = 49

CHAPTER_ATTACH_BORN = 1
CHAPTER_ATTACH_BOX = 2
CHAPTER_ATTACH_SUPPLY = 3
CHAPTER_ATTACH_BORN_SUB = 16
CHAPTER_ATTACH_BOSS = 8
CHAPTER_ATTACH_ELITE = 4
CHAPTER_ATTACH_AMBUSH = 5
CHAPTER_ATTACH_ENEMY = 6
CHAPTER_ATTACH_TORPEDO_ENEMY = 7
CHAPTER_ATTACH_CHAMPION = 12
CHAPTER_ATTACH_TRANSPORT = 17
CHAPTER_ATTACH_TRANSPORT_DST = 18
CHAPTER_ATTACH_BOMB_ENEMY = 24
CHAPTER_ATTACH_LANDBASE = 100

# Box (AttachBox = 2) outcome types -- mirror client ChapterConst box types.
BOX_BARRIER = 0
BOX_DROP = 1
BOX_STRATEGY = 2
BOX_AIRSTRIKE = 4
BOX_ENEMY = 5
BOX_SUPPLY = 6
BOX_TORPEDO = 7

CHAPTER_CELL_ACTIVE = 0
CHAPTER_CELL_DISABLED = 1
CHAPTER_CELL_AMBUSH = 2

SHIP_ATTR_INDEX_AIR = 4
SHIP_ATTR_INDEX_DODGE = 8

CHAPTER_TEMPLATE_CATEGORY = "sharecfgdata/chapter_template.json"
CHAPTER_TEMPLATE_LOOP_CATEGORY = "sharecfgdata/chapter_template_loop.json"
ITEM_DATA_STATS_CATEGORY = "sharecfgdata/item_data_statistics.json"
BENEFIT_BUFF_CATEGORY = "ShareCfg/benefit_buff_template.json"
FRIENDLY_DATA_CATEGORY = "ShareCfg/friendly_data_template.json"
FRIENDLY_DATA_SHARE_CATEGORY = "sharecfgdata/friendly_data_template.json"

ELITE_FLEET_STATE_FIELD = 1001

chapter_ambush_rand = random.Random()


@dataclass
class ChapterPos:
    row: int = 0
    column: int = 0


@dataclass
class ChapterGrid:
    row: int = 0
    column: int = 0
    walkable: bool = False
    attachment: int = 0


@dataclass
class ChapterTemplate:
    id: int = 0
    grids: list = None
    box_list: list = None
    random_box_list: list = None
    land_based: list = None
    friendly_id: int = 0
    ammo_total: int = 0
    ammo_submarine: int = 0
    group_num: int = 0
    submarine_num: int = 0
    support_group_num: int = 0
    is_ambush: int = 0
    investigation_ratio: int = 0
    avoid_ratio: int = 0
    avoid_require: int = 0
    ambush_ratio_extra: list = None
    chapter_strategy: list = None
    boss_expedition_id: list = None
    enemy_refresh: list = None
    boss_refresh: int = 0
    expedition_weight: list = None
    elite_expeditions: list = None
    ambush_expeditions: list = None
    guarder_expeditions: list = None
    awards: list = None
    star_require_1: int = 0
    star_require_2: int = 0
    star_require_3: int = 0
    num_1: int = 0
    num_2: int = 0
    num_3: int = 0
    progress_boss: int = 0
    oil: int = 0
    time: int = 0
    # Loop-chapter oil cap (client chapter.lua GetLimitOilCost): index 1 =
    # normal stage, 2 = boss stage, 3 = submarine fleet. Absent/empty -> no cap.
    use_oil_limit: list = None


@dataclass
class ShipDataStatisticsEntry:
    id: int = 0
    attrs: list = None
    attrs_growth: list = None
    attrs_growth_extra: list = None


@dataclass
class EquipDataStatisticsEntry:
    id: int = 0
    attribute_1: Optional[str] = None
    value_1: any = None
    attribute_2: Optional[str] = None
    value_2: any = None
    attribute_3: Optional[str] = None
    value_3: any = None
    equip_parameters: dict = None


@dataclass
class IntimacyTemplateEntry:
    id: int = 0
    lower_bound: int = 0
    upper_bound: int = 0
    attr_bonus: int = 0


@dataclass
class TransformDataEntry:
    id: int = 0
    effect: list = None


_get_config_entry = fetch_config_entry_data
_list_config_entries = fetch_config_entries_data


def load_chapter_template(chapter_id: int, loop_flag: int) -> Optional[ChapterTemplate]:
    if loop_flag == 0:
        entry = _get_config_entry(CHAPTER_TEMPLATE_CATEGORY, str(chapter_id))
        if entry is None:
            return None
        return _parse_chapter_template(entry)
    base = _get_config_entry(CHAPTER_TEMPLATE_CATEGORY, str(chapter_id))
    loop = _get_config_entry(CHAPTER_TEMPLATE_LOOP_CATEGORY, str(chapter_id))
    if loop is None:
        if base is None:
            return None
        return _parse_chapter_template(base)
    merged = dict(base) if isinstance(base, dict) else {}
    if isinstance(loop, dict):
        for key, value in loop.items():
            if value is not None:
                merged[key] = value
    return _parse_chapter_template(merged)


def _parse_chapter_template(data: dict) -> ChapterTemplate:
    t = ChapterTemplate()
    t.id = data.get("id", 0)
    t.grids = data.get("grids") or []
    t.box_list = data.get("box_list") or []
    t.random_box_list = data.get("random_box_list") or []
    t.land_based = data.get("land_based") or []
    t.friendly_id = data.get("friendly_id", 0)
    t.ammo_total = data.get("ammo_total", 0)
    t.ammo_submarine = data.get("ammo_submarine", 0)
    t.group_num = data.get("group_num", 0)
    t.submarine_num = data.get("submarine_num", 0)
    t.support_group_num = data.get("support_group_num", 0)
    t.is_ambush = data.get("is_ambush", 0)
    t.investigation_ratio = data.get("investigation_ratio", 0)
    t.avoid_ratio = data.get("avoid_ratio", 0)
    t.avoid_require = data.get("avoid_require", 0)
    t.ambush_ratio_extra = data.get("ambush_ratio_extra") or []
    t.chapter_strategy = data.get("chapter_strategy") or []
    t.boss_expedition_id = data.get("boss_expedition_id") or []
    t.enemy_refresh = data.get("enemy_refresh") or []
    t.boss_refresh = data.get("boss_refresh", 0)
    t.expedition_weight = data.get("expedition_id_weight_list") or []
    t.elite_expeditions = data.get("elite_expedition_list") or []
    t.ambush_expeditions = data.get("ambush_expedition_list") or []
    t.guarder_expeditions = data.get("guarder_expedition_list") or []
    t.awards = data.get("awards") or []
    t.star_require_1 = data.get("star_require_1", 0)
    t.star_require_2 = data.get("star_require_2", 0)
    t.star_require_3 = data.get("star_require_3", 0)
    t.num_1 = data.get("num_1", 0)
    t.num_2 = data.get("num_2", 0)
    t.num_3 = data.get("num_3", 0)
    t.progress_boss = data.get("progress_boss", 0)
    t.oil = data.get("oil", 0)
    t.time = data.get("time", 0)
    t.use_oil_limit = data.get("use_oil_limit") or {}
    return t


def load_item_usage_arg(item_id: int) -> Optional[list]:
    entry = _get_config_entry(ITEM_DATA_STATS_CATEGORY, str(item_id))
    if entry is None:
        return None
    usage_arg = entry.get("usage_arg")
    if usage_arg is None:
        return None
    return _decode_usage_arg_uint32(usage_arg)


def calculate_operation_item_cost_rate(item_id: int) -> float:
    if item_id == 0:
        return 1.0
    ids = load_item_usage_arg(item_id)
    if ids is None:
        return 1.0
    rate = 1.0
    for buff_id in ids:
        entry = _load_benefit_buff(buff_id)
        if entry is None or entry.get("benefit_type") != "more_oil":
            continue
        try:
            effect = float(entry.get("benefit_effect", 0))
        except (ValueError, TypeError):
            continue
        rate += effect * 0.01
    return max(1.0, rate)


def find_operation_buff_id(item_id: int) -> int:
    if item_id == 0:
        return 0
    entries = _list_config_entries(BENEFIT_BUFF_CATEGORY)
    for entry in entries:
        if entry.get("benefit_type") != "desc":
            continue
        try:
            condition = int(entry.get("benefit_condition", 0))
        except (ValueError, TypeError):
            continue
        if condition == item_id:
            return entry.get("id", 0)
    return 0


def _load_benefit_buff(buff_id: int) -> Optional[dict]:
    return _get_config_entry(BENEFIT_BUFF_CATEGORY, str(buff_id))


def load_friendly_data(friendly_id: int) -> Optional[dict]:
    for category in (FRIENDLY_DATA_CATEGORY, FRIENDLY_DATA_SHARE_CATEGORY):
        entry = _get_config_entry(category, str(friendly_id))
        if entry is not None:
            return entry
    return None


def _decode_usage_arg_uint32(raw) -> Optional[list]:
    if raw is None:
        return None
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return None
        if not raw.startswith("["):
            return None
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
    else:
        parsed = raw
    if isinstance(parsed, list):
        ids = []
        for v in parsed:
            if isinstance(v, (int, float)):
                ids.append(int(v))
            elif isinstance(v, str):
                try:
                    ids.append(int(v))
                except ValueError:
                    pass
        return ids
    return None


def find_chapter_group(current, group_id: int):
    for group in current.main_group_list:
        if group.id == group_id:
            return group
    for group in current.submarine_group_list:
        if group.id == group_id:
            return group
    for group in current.support_group_list:
        if group.id == group_id:
            return group
    return None


def collect_chapter_ships(current) -> list:
    ships = []
    for group in current.main_group_list:
        ships.extend(group.ship_list)
    for group in current.submarine_group_list:
        ships.extend(group.ship_list)
    for group in current.support_group_list:
        ships.extend(group.ship_list)
    return ships


def build_move_path(path: list) -> list:
    from src.protobuf import protobuf
    move_path = []
    for pos in path:
        cell_pos = protobuf.CHAPTERCELLPOS_P13()
        cell_pos.row = pos.row
        cell_pos.column = pos.column
        move_path.append(cell_pos)
    return move_path


def build_pos(pos: ChapterPos):
    from src.protobuf import protobuf
    p = protobuf.CHAPTERCELLPOS_P13()
    p.row = pos.row
    p.column = pos.column
    return p


def find_chapter_cell_at(current, pos: ChapterPos):
    if current is None:
        return -1, None
    for i, cell in enumerate(current.cell_list):
        p = cell.pos
        if p is None:
            continue
        if p.row == pos.row and p.column == pos.column:
            return i, cell
    return -1, None


def upsert_chapter_cell(current, cell):
    if current is None or cell is None or cell.pos is None:
        return
    pos = ChapterPos(row=cell.pos.row, column=cell.pos.column)
    idx, _ = find_chapter_cell_at(current, pos)
    if idx >= 0:
        current.cell_list[idx].CopyFrom(cell)
    else:
        current.cell_list.append(cell)


def parse_chapter_grids(raw: list) -> list:
    grids = []
    for entry in raw:
        if len(entry) < 4:
            raise ValueError("invalid grid entry")
        row = _parse_uint32(entry[0])
        column = _parse_uint32(entry[1])
        walkable = _parse_bool(entry[2])
        attachment = _parse_uint32(entry[3])
        grids.append(ChapterGrid(row=row, column=column, walkable=walkable, attachment=attachment))
    return grids


def _parse_uint32(value) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except (ValueError, TypeError):
            raise ValueError(f"unsupported number: {value}")
    raise ValueError(f"unsupported number: {value}")


def _parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return False


def _parse_uint32_list(value) -> list:
    if not isinstance(value, list):
        return []
    result = []
    for entry in value:
        try:
            result.append(_parse_uint32(entry))
        except ValueError:
            continue
    return result


def find_move_path(grids: list, start: ChapterPos, end: ChapterPos) -> list:
    if start.row == end.row and start.column == end.column:
        return [start]
    walkable = {}
    for grid in grids:
        if grid.walkable:
            walkable[(grid.row, grid.column)] = True
    start_key = (start.row, start.column)
    end_key = (end.row, end.column)
    if start_key not in walkable or end_key not in walkable:
        return None
    queue = [start_key]
    visited = {start_key: True}
    parent = {}
    while queue:
        current = queue.pop(0)
        if current == end_key:
            break
        neighbors = []
        neighbors.append((current[0] + 1, current[1]))
        if current[0] > 1:
            neighbors.append((current[0] - 1, current[1]))
        neighbors.append((current[0], current[1] + 1))
        if current[1] > 1:
            neighbors.append((current[0], current[1] - 1))
        for neighbor in neighbors:
            if neighbor in visited or neighbor not in walkable:
                continue
            visited[neighbor] = True
            parent[neighbor] = current
            queue.append(neighbor)
    if end_key not in visited:
        return None
    path = []
    current = end_key
    while True:
        path.append(ChapterPos(row=current[0], column=current[1]))
        if current == start_key:
            break
        current = parent[current]
    path.reverse()
    return path


def select_spawn_positions(grids: list, attachment: int) -> list:
    positions = []
    for grid in grids:
        if grid.attachment == attachment:
            positions.append(ChapterPos(row=grid.row, column=grid.column))
    if not positions and grids:
        positions.append(ChapterPos(row=grids[0].row, column=grids[0].column))
    return positions


def choose_spawn(spawns: list, index: int) -> ChapterPos:
    if not spawns:
        return ChapterPos(row=1, column=1)
    if index < len(spawns):
        return spawns[index]
    return spawns[0]


def select_first(values: list) -> int:
    if not values:
        return 0
    return values[0]


def select_random_expedition(values: list) -> int:
    if not values:
        return 0
    candidates = []
    for value in values:
        try:
            id_val = _parse_uint32(value)
        except (ValueError, TypeError):
            continue
        if id_val != 0:
            candidates.append(id_val)
    if not candidates:
        return 0
    return chapter_ambush_rand.choice(candidates)


def select_expedition_from_weights(weights: list) -> int:
    entries = []
    total = 0
    for entry in weights:
        if not entry:
            continue
        try:
            id_val = _parse_uint32(entry[0])
            weight = _parse_uint32(entry[1]) if len(entry) > 1 else 0
        except (ValueError, IndexError, TypeError):
            continue
        if id_val == 0:
            continue
        entries.append((id_val, weight))
        if weight > 0:
            total += weight
    if total > 0:
        pick = chapter_ambush_rand.randint(1, total)
        for id_val, weight in entries:
            if weight <= 0:
                continue
            pick -= weight
            if pick <= 0:
                return id_val
    for id_val, _weight in entries:
        return id_val
    return 0


def resolve_ambush_expedition(template) -> int:
    if template is None:
        return 0
    expedition_id = select_random_expedition(template.ambush_expeditions)
    if expedition_id != 0:
        return expedition_id
    return select_expedition_from_weights(template.expedition_weight)


def resolve_cell_flag(attachment: int) -> int:
    if attachment == CHAPTER_ATTACH_AMBUSH:
        return CHAPTER_CELL_AMBUSH
    return CHAPTER_CELL_ACTIVE


def select_attachment_id(attachment: int, template: ChapterTemplate) -> int:
    if attachment == CHAPTER_ATTACH_BOX:
        return select_first(template.random_box_list)
    if attachment == CHAPTER_ATTACH_SUPPLY:
        return select_supply_attachment_amount()
    if attachment == CHAPTER_ATTACH_BOSS:
        return 0
    if attachment == CHAPTER_ATTACH_ENEMY:
        return select_expedition_from_weights(template.expedition_weight)
    if attachment == CHAPTER_ATTACH_ELITE:
        return select_first(template.elite_expeditions)
    if attachment == CHAPTER_ATTACH_AMBUSH:
        return resolve_ambush_expedition(template)
    if attachment in (CHAPTER_ATTACH_CHAMPION, CHAPTER_ATTACH_BOMB_ENEMY, CHAPTER_ATTACH_TORPEDO_ENEMY):
        id_val = select_first(template.guarder_expeditions)
        if id_val != 0:
            return id_val
        return select_expedition_from_weights(template.expedition_weight)
    return 0


def select_supply_attachment_amount() -> int:
    return 3


def select_box_attachment_id(pos: ChapterPos, template: ChapterTemplate) -> int:
    ids = select_position_attachment_ids(pos, template.box_list)
    if ids:
        import random
        return random.choice(ids)
    first = select_first(template.random_box_list)
    if first != 0:
        return first
    return 0


def select_position_attachment_id(pos: ChapterPos, entries: list) -> int:
    ids = select_position_attachment_ids(pos, entries)
    if not ids:
        return 0
    return ids[0]


def select_position_attachment_ids(pos: ChapterPos, entries: list) -> list:
    for entry in entries:
        if len(entry) < 3:
            continue
        try:
            row = _parse_uint32(entry[0])
        except (ValueError, TypeError):
            continue
        if row != pos.row:
            continue
        try:
            column = _parse_uint32(entry[1])
        except (ValueError, TypeError):
            continue
        if column != pos.column:
            continue
        return _parse_uint32_list(entry[2])
    return []


def build_chapter_cells(grids: list, template: ChapterTemplate) -> list:
    from src.protobuf import protobuf
    if not grids:
        return []
    cells = []
    boss_id = 0
    if template is not None and template.boss_expedition_id:
        boss_id = template.boss_expedition_id[0]
    for grid in grids:
        if grid.attachment == 0:
            continue
        cell = protobuf.CHAPTERCELLINFO_P13()
        cell.pos.CopyFrom(build_pos(ChapterPos(row=grid.row, column=grid.column)))
        cell.item_type = grid.attachment
        cell.item_flag = resolve_cell_flag(grid.attachment)
        cell.item_data = 0
        if grid.attachment == CHAPTER_ATTACH_BOSS and boss_id != 0:
            cell.item_id = boss_id
        elif grid.attachment == CHAPTER_ATTACH_BOX and template is not None:
            attachment_id = select_box_attachment_id(ChapterPos(row=grid.row, column=grid.column), template)
            if attachment_id != 0:
                cell.item_id = attachment_id
        elif grid.attachment == CHAPTER_ATTACH_SUPPLY and template is not None:
            cell.item_id = select_supply_attachment_amount()
        elif grid.attachment == CHAPTER_ATTACH_LANDBASE and template is not None:
            attachment_id = select_position_attachment_id(ChapterPos(row=grid.row, column=grid.column), template.land_based)
            if attachment_id != 0:
                cell.item_id = attachment_id
        elif template is not None:
            attachment_id = select_attachment_id(grid.attachment, template)
            if attachment_id != 0:
                cell.item_id = attachment_id
        if cell.item_id == 0 and grid.attachment in (
            CHAPTER_ATTACH_ENEMY,
            CHAPTER_ATTACH_ELITE,
            CHAPTER_ATTACH_AMBUSH,
            CHAPTER_ATTACH_TORPEDO_ENEMY,
            CHAPTER_ATTACH_CHAMPION,
            CHAPTER_ATTACH_BOMB_ENEMY,
        ):
            continue
        cells.append(cell)
    return cells


def build_initial_chapter_cells(grids: list, template: ChapterTemplate) -> list:
    all_cells = build_chapter_cells(grids, template)
    enemy_refresh = template.enemy_refresh or []
    static = [c for c in all_cells if c.item_type not in (CHAPTER_ATTACH_ENEMY, CHAPTER_ATTACH_BOSS)]
    enemy_candidates = [c for c in all_cells if c.item_type == CHAPTER_ATTACH_ENEMY]
    chosen = []
    initial_count = enemy_refresh[0] if enemy_refresh else len(enemy_candidates)
    if initial_count > 0 and enemy_candidates:
        k = min(initial_count, len(enemy_candidates))
        chosen = random.sample(enemy_candidates, k)
    boss_cells = []
    if (template.boss_refresh or 0) == 0:
        boss_candidates = [c for c in all_cells if c.item_type == CHAPTER_ATTACH_BOSS]
        if boss_candidates:
            boss_cells.append(random.choice(boss_candidates))
    return static + chosen + boss_cells


def spawn_wave_cells(current, template: ChapterTemplate, grids: list, round_index: int) -> list:
    all_cells = build_chapter_cells(grids, template)
    enemy_refresh = template.enemy_refresh or []
    boss_refresh = template.boss_refresh or 0

    spawned_positions = {}
    current_enemies = 0
    boss_spawned = False
    for c in current.cell_list:
        if c.item_type in (CHAPTER_ATTACH_ENEMY, CHAPTER_ATTACH_BOSS):
            spawned_positions[(c.pos.row, c.pos.column)] = True
        if c.item_type == CHAPTER_ATTACH_ENEMY:
            current_enemies += 1
        elif c.item_type == CHAPTER_ATTACH_BOSS:
            boss_spawned = True

    enemy_pool = [c for c in all_cells if c.item_type == CHAPTER_ATTACH_ENEMY]
    pool_count = len(enemy_pool)

    if not enemy_refresh:
        target_enemies = pool_count
    elif round_index < 0:
        target_enemies = 0
    elif round_index < len(enemy_refresh):
        target_enemies = sum(enemy_refresh[0:round_index + 1])
    else:
        target_enemies = sum(enemy_refresh)
    target_enemies = min(target_enemies, pool_count)

    new_cells = []
    needed = target_enemies - current_enemies
    if needed > 0:
        candidates = [
            c for c in enemy_pool
            if (c.pos.row, c.pos.column) not in spawned_positions
        ]
        if candidates:
            k = min(needed, len(candidates))
            chosen = random.sample(candidates, k)
            new_cells.extend(chosen)
            for c in chosen:
                spawned_positions[(c.pos.row, c.pos.column)] = True

    if boss_refresh > 0 and round_index >= boss_refresh and not boss_spawned:
        boss_candidates = [
            c for c in all_cells
            if c.item_type == CHAPTER_ATTACH_BOSS
            and (c.pos.row, c.pos.column) not in spawned_positions
        ]
        if boss_candidates:
            new_cells.append(random.choice(boss_candidates))

    return new_cells


def build_commander_list(main_id: int, sub_id: int) -> list:
    from src.protobuf import protobuf
    commanders = []
    if main_id != 0:
        c = protobuf.COMMANDERSINFO()
        c.pos = 1
        c.id = main_id
        commanders.append(c)
    if sub_id != 0:
        c = protobuf.COMMANDERSINFO()
        c.pos = 2
        c.id = sub_id
        commanders.append(c)
    return commanders


# Per-ship base ammo (`ammo` field of ship_data_statistics) drives the
# submarine fleet's ammo capacity: the client shows a sub fleet on the chapter
# map as restAmmo/max, where max = chapter ammo_submarine + SUM of each sub's
# ammo attribute (model/vo/chapterleveldata.lua getFleetAmmo). EN submarines
# carry ammo 2 each, so a standard 3-sub fleet starts with 6. The server used
# to seed the group's bullet from ammo_submarine only (0 on EN templates),
# leaving every submarine group with 0/6 ammo at sortie start.
_SHIP_BASE_AMMO_CACHE: dict = {}


def _load_ship_base_ammo(template_id: int) -> int:
    if template_id in _SHIP_BASE_AMMO_CACHE:
        return _SHIP_BASE_AMMO_CACHE[template_id]
    ammo = 0
    try:
        entry = _get_config_entry("sharecfgdata/ship_data_statistics.json", str(template_id))
        if entry is not None:
            ammo = int(entry.get("ammo", 0) or 0)
    except Exception:
        ammo = 0
    _SHIP_BASE_AMMO_CACHE[template_id] = ammo
    return ammo


def _resolve_ship_template_id(ship_id: int, owned_ships_map: Optional[dict] = None) -> Optional[int]:
    """Resolve an owned ship id to its template ship_id (from ship_data_statistics)."""
    if owned_ships_map:
        owned = owned_ships_map.get(ship_id) if hasattr(owned_ships_map, "get") else None
        if owned is not None:
            tpl = owned.get("ship_id") if isinstance(owned, dict) else getattr(owned, "ship_id", None)
            if tpl is not None:
                return int(tpl)
    # DB fallback if not present in cache
    try:
        from src.db.session import get_sync_session
        from sqlalchemy import text
        with get_sync_session() as session:
            row = session.execute(
                text("SELECT ship_id FROM owned_ships WHERE id = :id AND deleted_at IS NULL"),
                {"id": ship_id},
            ).fetchone()
            if row:
                return int(row[0])
    except Exception:
        pass
    return None


def normal_team_starting_ammo(team, owned_ships_map, allowance: int) -> int:
    """Starting `bullet` for a fresh normal (surface) group on the chapter map.

    Mirrors the client's getFleetAmmo max for FleetType.Normal: the chapter
    allowance (ammo_total) plus MAX of each ship's own ammo attribute
    (model/vo/chaptercell/chapterfleet.lua getShipAmmo -> math.max).
    Vestal / Akashi / repair ships give +1 ammo when limit broken.
    """
    bonus = 0
    ship_list = getattr(team, "ship_list", None) or []
    for ship_id in ship_list:
        tpl_id = _resolve_ship_template_id(ship_id, owned_ships_map)
        if tpl_id:
            bonus = max(bonus, _load_ship_base_ammo(tpl_id))
    return allowance + bonus


def submarine_team_starting_ammo(team, owned_ships_map, allowance: int) -> int:
    """Starting `bullet` for a fresh submarine group on the chapter map.

    Mirrors the client's getFleetAmmo max for FleetType.Submarine: the chapter
    allowance (ammo_submarine) plus every submarine's own ammo attribute
    (model/vo/chaptercell/chapterfleet.lua getShipAmmo -> sum).
    ``owned_ships_map`` maps owned ship id -> owned ship record (dict or ORM
    object with ship_id = template id); when unavailable the allowance alone
    is used.
    """
    total = allowance
    ship_list = getattr(team, "ship_list", None) or []
    for ship_id in ship_list:
        tpl_id = _resolve_ship_template_id(ship_id, owned_ships_map)
        if tpl_id:
            total += _load_ship_base_ammo(tpl_id)
    return total


def get_group_max_ammo(current, group, template: ChapterTemplate, owned_ships_map=None) -> int:
    """Compute maximum ammo capacity for a group on the chapter map.

    Matches model/vo/chapterleveldata.lua getFleetAmmo:
    - Normal fleet: template.ammo_total + max(ship.ammo)
    - Submarine fleet: template.ammo_submarine + sum(ship.ammo)
    - Support fleet: template.ammo_total
    """
    is_submarine = False
    is_support = False
    if current is not None:
        if any(g.id == group.id for g in getattr(current, "submarine_group_list", [])):
            is_submarine = True
        elif any(g.id == group.id for g in getattr(current, "support_group_list", [])):
            is_support = True

    if is_support:
        return template.ammo_total

    ships = getattr(group, "ship_list", [])
    if is_submarine:
        total = template.ammo_submarine
        for s in ships:
            tpl_id = _resolve_ship_template_id(s.id, owned_ships_map)
            if tpl_id:
                total += _load_ship_base_ammo(tpl_id)
        return total
    else:
        bonus = 0
        for s in ships:
            tpl_id = _resolve_ship_template_id(s.id, owned_ships_map)
            if tpl_id:
                bonus = max(bonus, _load_ship_base_ammo(tpl_id))
        return template.ammo_total + bonus


def build_groups_from_teams(teams: list, spawns: list, ammo):
    from src.protobuf import protobuf
    groups = []
    ship_count = 0
    for index, team in enumerate(teams):
        if not team.ship_list:
            continue
        spawn = choose_spawn(spawns, index)
        ships = []
        for ship_id in team.ship_list:
            s = protobuf.SHIPINCHAPTER_P13()
            s.id = ship_id
            s.hp_rant = 10000
            ships.append(s)
            ship_count += 1
        commanders = build_commander_list(team.commander_main, team.commander_sub)
        group_id = team.id
        if group_id == 0:
            group_id = index + 1
        # `ammo` may be a per-team callable (normal/submarine groups compute their
        # capacity from the fleet's ships) or a plain int for the others.
        team_ammo = ammo(team) if callable(ammo) else ammo
        g = protobuf.GROUPINCHAPTER_P13()
        g.id = group_id
        g.ship_list.extend(ships)
        g.pos.CopyFrom(build_pos(spawn))
        g.step_count = 0
        g.bullet = team_ammo
        g.start_pos.CopyFrom(build_pos(spawn))
        g.commander_list.extend(commanders)
        g.move_step_down = 0
        g.kill_count = 0
        g.fleet_id = group_id
        g.vision_lv = 0
        groups.append(g)
    return groups, ship_count


def build_groups_from_elite(group_ids: list, elite: list, spawns: list, ammo):
    from src.protobuf import protobuf
    groups = []
    ship_count = 0
    for index, group_id in enumerate(group_ids):
        spawn = choose_spawn(spawns, index)
        elite_fleet = elite[index] if index < len(elite) else None
        if elite_fleet is None or not elite_fleet.ship_id_list:
            continue
        ships = []
        for ship_id in elite_fleet.ship_id_list:
            s = protobuf.SHIPINCHAPTER_P13()
            s.id = ship_id
            s.hp_rant = 10000
            ships.append(s)
            ship_count += 1
        commanders = []
        for commander in elite_fleet.commanders:
            c = protobuf.COMMANDERSINFO()
            c.pos = commander.pos
            c.id = commander.id
            commanders.append(c)
        if group_id == 0:
            group_id = index + 1
        team_ammo = ammo(elite_fleet) if callable(ammo) else ammo
        g = protobuf.GROUPINCHAPTER_P13()
        g.id = group_id
        g.ship_list.extend(ships)
        g.pos.CopyFrom(build_pos(spawn))
        g.step_count = 0
        g.bullet = team_ammo
        g.start_pos.CopyFrom(build_pos(spawn))
        g.commander_list.extend(commanders)
        g.move_step_down = 0
        g.kill_count = 0
        g.fleet_id = group_id
        g.vision_lv = 0
        groups.append(g)
    return groups, ship_count


def build_chapter_strategies(ids: list) -> list:
    from src.protobuf import protobuf
    if not ids:
        return []
    strategies = []
    for id_val in ids:
        s = protobuf.STRATEGYINFO_P13()
        s.id = id_val
        s.count = 0
        strategies.append(s)
    return strategies


def build_operation_buff_list(buff_id: int, item_id: int = 0) -> list:
    """Build the list of operation buffs for CURRENTCHAPTERINFO.operation_buff.
    For special operation items (like item 61001 High-Efficiency Combat Logistics Plan),
    originally sends all buffs from the item's usage_arg in SC_13102
    (e.g. [5, 8, 9, 47, 48] covering exp doubling, desc, extra drop, oil increase).
    The client relies on buff 8 (extra_drop) in operationBuffList to activate the
    Operation Bonus UI elements and headers in battle results.
    """
    if item_id:
        args = load_item_usage_arg(item_id)
        if args:
            return [int(x) for x in args]
    if buff_id == 0:
        return []
    buff = _load_benefit_buff(buff_id)
    if buff:
        cond = buff.get("benefit_condition")
        if cond:
            try:
                args = load_item_usage_arg(int(cond))
                if args:
                    return [int(x) for x in args]
            except (ValueError, TypeError):
                pass
    return [buff_id]


def build_escort_list(grids: list, template: ChapterTemplate):
    from src.protobuf import protobuf
    if template is None or template.friendly_id == 0:
        return []
    friendly = load_friendly_data(template.friendly_id)
    hp = friendly.get("hp", 0) if friendly else 0
    escorts = []
    for grid in grids:
        if grid.attachment != CHAPTER_ATTACH_TRANSPORT:
            continue
        escort = protobuf.CHAPTERCELLINFO_P13()
        escort.pos.CopyFrom(build_pos(ChapterPos(row=grid.row, column=grid.column)))
        escort.item_type = CHAPTER_ATTACH_TRANSPORT
        escort.item_id = template.friendly_id
        escort.item_flag = CHAPTER_CELL_ACTIVE
        escort.item_data = hp
        escorts.append(escort)
    return escorts


def build_current_chapter_info(template: ChapterTemplate, payload, operation_buff_id: int, owned_ships_map=None):
    from src.protobuf import protobuf
    grids = parse_chapter_grids(template.grids)
    main_spawns = select_spawn_positions(grids, CHAPTER_ATTACH_BORN)
    sub_spawns = select_spawn_positions(grids, CHAPTER_ATTACH_BORN_SUB)
    cell_list = build_initial_chapter_cells(grids, template)
    main_groups, main_count = build_groups_from_teams(
        payload.fleet.main_team, main_spawns,
        lambda team: normal_team_starting_ammo(team, owned_ships_map, template.ammo_total),
    )
    sub_groups, sub_count = build_groups_from_teams(
        payload.fleet.submarine_team, sub_spawns,
        lambda team: submarine_team_starting_ammo(team, owned_ships_map, template.ammo_submarine),
    )
    support_groups, support_count = build_groups_from_teams(payload.fleet.support_team, main_spawns, template.ammo_total)
    escort_list = build_escort_list(grids, template)
    strategies = build_chapter_strategies(template.chapter_strategy)
    init_ship_count = main_count + sub_count + support_count
    import time
    current = protobuf.CURRENTCHAPTERINFO()
    current.id = payload.id
    current.time = int(time.time()) + template.time
    current.cell_list.extend(cell_list)
    current.main_group_list.extend(main_groups)
    current.ai_list.extend([])
    current.escort_list.extend(escort_list)
    current.round = 0
    current.is_submarine_auto_attack = 0
    op_item = getattr(payload, "operation_item", 0)
    current.operation_buff.extend(build_operation_buff_list(operation_buff_id, item_id=op_item))
    current.model_act_count = 0
    current.buff_list.extend([])
    current.loop_flag = payload.loop_flag
    current.extra_flag_list.extend([])
    current.cell_flag_list.extend([])
    current.chapter_hp = 0
    current.chapter_strategy_list.extend(strategies)
    current.kill_count = 0
    current.init_ship_count = init_ship_count
    current.continuous_kill_count = 0
    current.battle_statistics.extend([])
    del current.fleet_duties[:]
    current.fleet_duties.extend(payload.fleet_duties)
    current.move_step_count = 0
    current.submarine_group_list.extend(sub_groups)
    current.support_group_list.extend(support_groups)
    return current, init_ship_count


def chapter_ambush_prevented_by_recon(template, current, client) -> bool:
    # Client parity (chapterleveldata.lua GetWillActiveAmbush): once ANY normal
    # fleet's recon value (invest sums) reaches the map's avoid_require, ambush
    # is disabled for the whole chapter and the level screen shows
    # "Chance of encounter: None".
    if template is None or current is None or client is None:
        return False
    avoid_require = float(getattr(template, "avoid_require", 0) or 0)
    if avoid_require <= 0:
        return False
    for group in current.main_group_list:
        if calculate_group_invest_sums(group, client) >= avoid_require:
            return True
    return False


def maybe_trigger_chapter_ambush(template, current, group, end: ChapterPos, client):
    from src.protobuf import protobuf
    if template is None or current is None or group is None or client is None:
        return None
    if template.is_ambush == 0:
        return None
    if end.row == 0 or end.column == 0:
        return None
    _, cell = find_chapter_cell_at(current, end)
    if cell is not None:
        if cell.item_type != CHAPTER_ATTACH_BORN and cell.item_type != CHAPTER_ATTACH_BORN_SUB:
            return None
    if chapter_ambush_prevented_by_recon(template, current, client):
        return None
    threshold = calculate_ambush_trigger_threshold(template, group, end, client)
    if threshold == 0:
        return None
    if chapter_ambush_rand.randint(0, CHAPTER_CHANCE_BASE - 1) >= threshold:
        return None
    expedition_id = resolve_ambush_expedition(template)
    if expedition_id == 0:
        return None
    ambush_cell = protobuf.CHAPTERCELLINFO_P13()
    ambush_cell.pos.CopyFrom(build_pos(end))
    ambush_cell.item_type = CHAPTER_ATTACH_AMBUSH
    ambush_cell.item_id = expedition_id
    ambush_cell.item_flag = CHAPTER_CELL_AMBUSH
    ambush_cell.item_data = 0
    upsert_chapter_cell(current, ambush_cell)
    return ambush_cell


def calculate_ambush_trigger_threshold(template, group, pos: ChapterPos, client) -> int:
    if template is None or group is None or client is None:
        return 0
    step = int(group.step_count)
    if step > 0:
        step -= 1
    inv = float(template.investigation_ratio)
    invest_sums = calculate_group_invest_sums(group, client)
    pos_extra, global_extra = chapter_ambush_ratio_extras(template, pos)
    rate = 0.05 + pos_extra + global_extra
    if step > 0:
        denom = inv + invest_sums
        if denom > 0:
            rate += (inv / denom) / 4 * float(step)
    if pos_extra == 0:
        rate -= calculate_fleet_equip_ambush_rate_reduce(group, client)
    rate = clamp_chance(rate)
    return int(rate * CHAPTER_CHANCE_BASE)


def calculate_ambush_dodge_threshold(template, group, pos: ChapterPos, client) -> int:
    if template is None or group is None or client is None:
        return 0
    avoid = float(template.avoid_ratio)
    if avoid <= 0:
        return CHAPTER_CHANCE_BASE
    dodge_sums = calculate_group_dodge_sums(group, client)
    if dodge_sums <= 0:
        return 0
    chance = dodge_sums / (dodge_sums + avoid)
    pos_extra, _ = chapter_ambush_ratio_extras(template, pos)
    if pos_extra == 0:
        chance += calculate_fleet_equip_dodge_rate_up(group, client)
    chance = clamp_chance(chance)
    return int(chance * CHAPTER_CHANCE_BASE)


def calculate_group_invest_sums(group, client) -> float:
    s = calculate_group_invest_sum_base(group, client)
    if s <= 0:
        return 0
    return math.pow(s, 2.0 / 3.0)


def calculate_group_dodge_sums(group, client) -> float:
    s = calculate_group_dodge_sum_base(group, client)
    if s <= 0:
        return 0
    return math.pow(s, 2.0 / 3.0)


def calculate_group_invest_sum_base(group, client) -> float:
    if group is None or client is None or client.commander is None:
        return 0
    if client.commander.owned_ships_map is None:
        client.commander.load()
    total = 0.0
    for ship in group.ship_list:
        ship_id = ship.id
        if ship_id == 0:
            continue
        owned = client.commander.owned_ships_map.get(ship_id)
        if owned is None:
            continue
        air, dodge = calculate_ship_properties_air_dodge(owned, client.commander.commander_id)
        total += air + dodge
    return total


def calculate_group_dodge_sum_base(group, client) -> float:
    if group is None or client is None or client.commander is None:
        return 0
    if client.commander.owned_ships_map is None:
        client.commander.load()
    total = 0.0
    for ship in group.ship_list:
        ship_id = ship.id
        if ship_id == 0:
            continue
        owned = client.commander.owned_ships_map.get(ship_id)
        if owned is None:
            continue
        _, dodge = calculate_ship_properties_air_dodge(owned, client.commander.commander_id)
        total += dodge
    return total


def ensure_ambush_cell_has_expedition(cell, template):
    if cell is None or template is None:
        return
    if cell.item_id != 0:
        return
    expedition_id = resolve_ambush_expedition(template)
    if expedition_id == 0:
        return
    cell.item_id = expedition_id


def repair_invalid_ambush_cells(current, template) -> bool:
    if current is None or not current.cell_list:
        return False
    from src.orm.config_entry import get_config_entry
    changed = False
    keep = []
    for cell in current.cell_list:
        if cell.item_type == CHAPTER_ATTACH_AMBUSH:
            if cell.item_id != 0 and get_config_entry("sharecfgdata/expedition_data_template.json", str(cell.item_id)) is not None:
                keep.append(cell)
                continue
            expedition_id = resolve_ambush_expedition(template)
            if expedition_id == 0:
                changed = True
                continue
            cell.item_id = expedition_id
            changed = True
        keep.append(cell)
    if changed:
        del current.cell_list[:]
        current.cell_list.extend(keep)
    return changed


_extra_attr_level_limit = None


def get_extra_attr_level_limit() -> int:
    global _extra_attr_level_limit
    if _extra_attr_level_limit is None:
        entry = _get_config_entry("ShareCfg/gameset.json", "extra_attr_level_limit")
        if entry is not None:
            val = entry.get("key_value", 0)
            if val > 0:
                _extra_attr_level_limit = val
            else:
                _extra_attr_level_limit = 100
        else:
            _extra_attr_level_limit = 100
    return _extra_attr_level_limit


_intimacy_templates = None


def _load_intimacy_templates():
    global _intimacy_templates
    entries = _list_config_entries("ShareCfg/intimacy_template.json")
    templates = []
    for entry in entries:
        t = IntimacyTemplateEntry()
        t.id = entry.get("id", 0)
        t.lower_bound = entry.get("lower_bound", 0)
        t.upper_bound = entry.get("upper_bound", 0)
        t.attr_bonus = entry.get("attr_bonus", 0)
        templates.append(t)
    _intimacy_templates = templates


def intimacy_attr_bonus_rate(intimacy: int) -> float:
    global _intimacy_templates
    if _intimacy_templates is None:
        _load_intimacy_templates()
    for tpl in _intimacy_templates:
        if tpl.lower_bound <= intimacy <= tpl.upper_bound:
            return float(tpl.attr_bonus) / 10000
    return 0


def calc_floor(value: float) -> float:
    return math.floor(value + 1e-9)


def clamp_chance(value: float) -> float:
    if value < 0:
        return 0
    if value > 1:
        return 1
    return value


def chapter_ambush_ratio_extras(template, pos: ChapterPos):
    if template is None:
        return 0.0, 0.0
    pos_extra = 0.0
    global_extra = 0.0
    for entry in template.ambush_ratio_extra:
        if len(entry) == 1:
            global_extra = float(entry[0]) / CHAPTER_CHANCE_BASE
        elif len(entry) >= 3 and entry[0] == pos.row and entry[1] == pos.column:
            pos_extra = float(entry[2]) / CHAPTER_CHANCE_BASE
    return pos_extra, global_extra


def calculate_ship_properties_air_dodge(owned, owner_id: int):
    if owned is None:
        return 0.0, 0.0
    stats = load_ship_data_statistics(owned.ship_id if hasattr(owned, "ship_id") else owned["ship_id"])
    if stats is None:
        return 0.0, 0.0
    ship_id = owned.id if hasattr(owned, "id") else owned["id"]
    level = owned.level if hasattr(owned, "level") else owned["level"]
    intimacy = owned.intimacy if hasattr(owned, "intimacy") else owned["intimacy"]
    extra_limit = get_extra_attr_level_limit()
    base_air = ship_growth_for_index(stats, SHIP_ATTR_INDEX_AIR, level, extra_limit)
    base_dodge = ship_growth_for_index(stats, SHIP_ATTR_INDEX_DODGE, level, extra_limit)
    bonus_rate = intimacy_attr_bonus_rate(intimacy)
    transform_air, transform_dodge = ship_transform_additions_air_dodge(owner_id, ship_id)
    prop_air = base_air * (1 + bonus_rate) + transform_air
    prop_dodge = base_dodge * (1 + bonus_rate) + transform_dodge
    air = calc_floor(prop_air)
    dodge = calc_floor(prop_dodge)
    equip_air, equip_dodge = equipment_attribute_additions(owner_id, ship_id)
    air += equip_air
    dodge += equip_dodge
    sp_air, sp_dodge = spweapon_attribute_additions(owner_id, ship_id)
    air += sp_air
    dodge += sp_dodge
    return air, dodge


def ship_transform_additions_air_dodge(owner_id: int, ship_id: int):
    rows = _sync_get_owned_ship_transforms(owner_id)
    air_add = 0.0
    dodge_add = 0.0
    for row in rows:
        if row.ship_id != ship_id:
            continue
        cfg = load_transform_data(row.transform_id)
        if cfg is None:
            continue
        level = int(row.level)
        if level <= 0:
            continue
        for i in range(level):
            if i >= len(cfg.effect):
                break
            effect = cfg.effect[i]
            air_add += effect.get("air", 0)
            dodge_add += effect.get("dodge", 0)
    return air_add, dodge_add


def ship_growth_for_index(stats: ShipDataStatisticsEntry, index: int, level: int, extra_limit: int) -> float:
    if stats is None or index < 0:
        return 0
    if index >= len(stats.attrs) or index >= len(stats.attrs_growth) or index >= len(stats.attrs_growth_extra):
        return 0
    base = float(stats.attrs[index])
    if level > 1:
        base += float(level - 1) * float(stats.attrs_growth[index]) / 1000
    if extra_limit > 0 and level > extra_limit:
        base += float(level - extra_limit) * float(stats.attrs_growth_extra[index]) / 1000
    return base


def load_ship_data_statistics(template_id: int) -> Optional[ShipDataStatisticsEntry]:
    entry = _get_config_entry("sharecfgdata/ship_data_statistics.json", str(template_id))
    if entry is None:
        return None
    stats = ShipDataStatisticsEntry()
    stats.id = entry.get("id", 0)
    stats.attrs = entry.get("attrs") or []
    stats.attrs_growth = entry.get("attrs_growth") or []
    stats.attrs_growth_extra = entry.get("attrs_growth_extra") or []
    return stats


def equipment_attribute_additions(owner_id: int, ship_id: int):
    rows = _sync_list_owned_ship_equipment(owner_id, ship_id)
    air_add = 0.0
    dodge_add = 0.0
    for row in rows:
        cfg = load_equip_data_statistics(row["equip_id"])
        if cfg is None:
            continue
        air_add += equip_attribute_value(cfg.attribute_1, cfg.value_1, "air")
        dodge_add += equip_attribute_value(cfg.attribute_1, cfg.value_1, "dodge")
        air_add += equip_attribute_value(cfg.attribute_2, cfg.value_2, "air")
        dodge_add += equip_attribute_value(cfg.attribute_2, cfg.value_2, "dodge")
        air_add += equip_attribute_value(cfg.attribute_3, cfg.value_3, "air")
        dodge_add += equip_attribute_value(cfg.attribute_3, cfg.value_3, "dodge")
    return air_add, dodge_add


def spweapon_attribute_additions(owner_id: int, ship_id: int) -> tuple[float, float]:
    if owner_id <= 0 or ship_id <= 0:
        return 0.0, 0.0
    from src.orm.spweapon import list_owned_sp_weapons_sync
    try:
        sp_weapons = list_owned_sp_weapons_sync(owner_id)
    except Exception:
        return 0.0, 0.0
    equipped = None
    for sp in sp_weapons:
        sid = getattr(sp, "equipped_ship_id", None) or (sp.get("equipped_ship_id") if isinstance(sp, dict) else 0)
        if sid == ship_id:
            equipped = sp
            break
    if not equipped:
        return 0.0, 0.0
    template_id = getattr(equipped, "template_id", None) or (equipped.get("template_id") if isinstance(equipped, dict) else 0)
    attr_1_val = getattr(equipped, "attr_1", None) or (equipped.get("attr_1") if isinstance(equipped, dict) else 0) or 0
    attr_2_val = getattr(equipped, "attr_2", None) or (equipped.get("attr_2") if isinstance(equipped, dict) else 0) or 0
    entry = _get_config_entry("sharecfgdata/spweapon_data_statistics.json", str(template_id))
    if not entry:
        return 0.0, 0.0
    base_id = entry.get("base")
    base_entry = _get_config_entry("sharecfgdata/spweapon_data_statistics.json", str(base_id)) if base_id else None

    def _resolve(key):
        val = entry.get(key)
        if val is not None:
            return val
        if base_entry is not None:
            return base_entry.get(key)
        return None

    a1 = _resolve("attribute_1")
    v1 = (_parse_float(_resolve("value_1")) or 0.0) + float(attr_1_val)
    a2 = _resolve("attribute_2")
    v2 = (_parse_float(_resolve("value_2")) or 0.0) + float(attr_2_val)

    air_add = 0.0
    dodge_add = 0.0
    if a1 == "air":
        air_add += v1
    elif a1 == "dodge":
        dodge_add += v1
    if a2 == "air":
        air_add += v2
    elif a2 == "dodge":
        dodge_add += v2
    return air_add, dodge_add


def _get_fleet_equip_max_extra(group, client, param_key: str) -> float:
    if group is None or client is None or client.commander is None:
        return 0
    owner_id = client.commander.commander_id
    max_extra = 0.0
    for ship in group.ship_list:
        owned = client.commander.owned_ships_map.get(ship.id)
        if owned is None:
            continue
        ship_id = owned.id if hasattr(owned, "id") else owned["id"]
        rows = _sync_list_owned_ship_equipment(owner_id, ship_id)
        for row in rows:
            cfg = load_equip_data_statistics(row["equip_id"])
            if cfg is None:
                continue
            value = equip_parameter_rate(cfg.equip_parameters, param_key)
            if value > max_extra:
                max_extra = value
    return max_extra


def calculate_fleet_equip_ambush_rate_reduce(group, client) -> float:
    return _get_fleet_equip_max_extra(group, client, "ambush_extra")


def calculate_fleet_equip_dodge_rate_up(group, client) -> float:
    return _get_fleet_equip_max_extra(group, client, "avoid_extra")


def load_equip_data_statistics(equip_id: int) -> Optional[EquipDataStatisticsEntry]:
    entry = _get_config_entry("sharecfgdata/equip_data_statistics.json", str(equip_id))
    if entry is None:
        return None
    base_id = entry.get("base")
    base_entry = _get_config_entry("sharecfgdata/equip_data_statistics.json", str(base_id)) if base_id else None

    stats = EquipDataStatisticsEntry()
    stats.id = entry.get("id", 0)

    def _resolve(key):
        val = entry.get(key)
        if val is not None:
            return val
        if base_entry is not None:
            return base_entry.get(key)
        return None

    stats.attribute_1 = _resolve("attribute_1")
    stats.value_1 = _resolve("value_1")
    stats.attribute_2 = _resolve("attribute_2")
    stats.value_2 = _resolve("value_2")
    stats.attribute_3 = _resolve("attribute_3")
    stats.value_3 = _resolve("value_3")

    params = entry.get("equip_parameters")
    if not params and base_entry is not None:
        params = base_entry.get("equip_parameters")
    stats.equip_parameters = params or {}
    return stats


def load_transform_data(transform_id: int) -> Optional[TransformDataEntry]:
    entry = _get_config_entry("ShareCfg/transform_data_template.json", str(transform_id))
    if entry is None:
        return None
    t = TransformDataEntry()
    t.id = entry.get("id", 0)
    t.effect = entry.get("effect") or []
    return t


def equip_attribute_value(attr: Optional[str], value, expected: str) -> float:
    if attr is None or attr != expected:
        return 0
    parsed = _parse_float(value)
    if parsed is None:
        return 0
    return parsed


def equip_parameter_rate(params: dict, key: str) -> float:
    if not params:
        return 0
    value = params.get(key)
    if value is None:
        return 0
    parsed = _parse_float(value)
    if parsed is None:
        return 0
    return parsed / CHAPTER_CHANCE_BASE


def _parse_float(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    return None


def get_chapter_state_by_commander(commander_id: int):
    return _sync_get_chapter_state(commander_id)


def upsert_chapter_state(commander_id: int, chapter_id: int, state_bytes: bytes):
    _sync_upsert_chapter_state(commander_id, chapter_id, state_bytes)


def delete_chapter_state(commander_id: int):
    _sync_delete_chapter_state(commander_id)


def get_chapter_drops(_commander_id: int, chapter_id: int) -> list:
    # The "drop ship list" (SC_13110) is the full pool of ship ids obtainable
    # from a chapter. These come from the chapter's `awards`: each "Mystery Ship"
    # virtual item (type 2) lists its possible ships in `display_icon`, and any
    # award given directly as a ship (type 4) also counts.
    template = load_chapter_template(chapter_id, 0)
    if template is None or not template.awards:
        return []
    awards = template.awards
    if isinstance(awards, str):
        import json
        try:
            awards = json.loads(awards)
        except Exception:
            return []
    if not isinstance(awards, list):
        return []
    ship_ids = []
    for entry in awards:
        if len(entry) < 2:
            continue
        drop_type = entry[0]
        for i in range(1, len(entry)):
            drop_id = entry[i]
            if drop_id == 0:
                continue
            if drop_type == 4:
                ship_ids.append(drop_id)
                continue
            if drop_type == 2:
                from src.answer.battle_session import _load_virtual_item_config
                config = _load_virtual_item_config(drop_id)
                if config and config.get("display_icon"):
                    for sub in config["display_icon"]:
                        if len(sub) >= 2 and sub[0] == 4:
                            ship_ids.append(sub[1])
    return ship_ids


def ensure_chapter_progress(commander_id: int, chapter_id: int):
    _sync_ensure_chapter_progress(commander_id, chapter_id)
