from __future__ import annotations

import json
import math
from typing import Optional

from src.answer.chapter.helpers import (
    CHAPTER_ATTACH_AMBUSH,
    CHAPTER_ATTACH_BOMB_ENEMY,
    CHAPTER_ATTACH_ELITE,
    CHAPTER_ATTACH_ENEMY,
    CHAPTER_ATTACH_TORPEDO_ENEMY,
    CHAPTER_CELL_ACTIVE,
    _get_config_entry,
    _resolve_ship_template_id,
    _sync_list_owned_ship_equipment,
    get_extra_attr_level_limit,
    intimacy_attr_bonus_rate,
    load_equip_data_statistics,
    load_ship_data_statistics,
    ship_growth_for_index,
)
from src.logger.logger import LOG_LEVEL_INFO, log_event
from src.orm.commander_meow import (
    get_commander_meow,
    get_commander_skill_config,
    get_commander_skill_effect_config,
    get_initial_commander_skills,
)
from src.protobuf import protobuf

SUB_ATTACKABLE_ENEMY_ATTACHMENTS = {
    CHAPTER_ATTACH_ENEMY,
    CHAPTER_ATTACH_ELITE,
    CHAPTER_ATTACH_AMBUSH,
    CHAPTER_ATTACH_TORPEDO_ENEMY,
    CHAPTER_ATTACH_BOMB_ENEMY,
}

DEFAULT_MIN_DAMAGE_CAP = 3.0
DEFAULT_MAX_DAMAGE_CAP = 20.0
MEOW_BONUS_MAX_DAMAGE_CAP = 25.0


def get_expedition_level(expedition_id: int) -> int:
    """Returns the enemy level from expedition_data_template."""
    if expedition_id <= 0:
        return 1
    entry = _get_config_entry("sharecfgdata/expedition_data_template.json", str(expedition_id))
    if entry and isinstance(entry, dict):
        return int(entry.get("level", 1) or 1)
    return 1


def calculate_ship_combat_power(owned, owner_id: int) -> float:
    """Computes combat power of an owned submarine ship."""
    if owned is None:
        return 3000.0

    ship_id = owned.id if hasattr(owned, "id") else owned["id"]
    template_id = owned.ship_id if hasattr(owned, "ship_id") else owned["ship_id"]
    level = owned.level if hasattr(owned, "level") else owned["level"]
    intimacy = owned.intimacy if hasattr(owned, "intimacy") else owned["intimacy"]

    stats = load_ship_data_statistics(template_id)
    if stats is None:
        return 3000.0

    extra_limit = get_extra_attr_level_limit()
    bonus_rate = intimacy_attr_bonus_rate(intimacy)

    dur = ship_growth_for_index(stats, 0, level, extra_limit) * (1 + bonus_rate)
    cannon = ship_growth_for_index(stats, 1, level, extra_limit) * (1 + bonus_rate)
    torp = ship_growth_for_index(stats, 2, level, extra_limit) * (1 + bonus_rate)
    aa = ship_growth_for_index(stats, 3, level, extra_limit) * (1 + bonus_rate)
    air = ship_growth_for_index(stats, 4, level, extra_limit) * (1 + bonus_rate)
    rld = ship_growth_for_index(stats, 5, level, extra_limit) * (1 + bonus_rate)
    hit = ship_growth_for_index(stats, 7, level, extra_limit) * (1 + bonus_rate)
    dodge = ship_growth_for_index(stats, 8, level, extra_limit) * (1 + bonus_rate)
    speed = ship_growth_for_index(stats, 9, level, extra_limit)
    asw = ship_growth_for_index(stats, 11, level, extra_limit) * (1 + bonus_rate)

    base_power = (
        dur / 5.0 + cannon + torp + aa + air + rld + hit * 2.0 + dodge * 2.0 + speed + asw
    )

    # Equipment power contribution
    equip_power = 0.0
    equip_rows = _sync_list_owned_ship_equipment(owner_id, ship_id)
    for row in equip_rows:
        cfg = load_equip_data_statistics(row["equip_id"])
        if cfg is not None:
            equip_power += 250.0

    return max(500.0, base_power + equip_power)


def get_sub_group_commander_bonuses(group, owner_id: int) -> tuple[int, float]:
    """
    Checks commander skills equipped to the submarine group:
    Returns (extra_hunting_lv, max_damage_cap).
    """
    from src.config.game_variables import get_sub_strike_damage_caps
    _, max_cap = get_sub_strike_damage_caps()
    extra_hunting_lv = 0

    commander_list = getattr(group, "commander_list", [])
    for c in commander_list:
        meow_id = getattr(c, "id", 0)
        if meow_id == 0:
            continue

        meow = get_commander_meow(owner_id, meow_id)
        if meow is None:
            continue

        skills_raw = getattr(meow, "skills", None)
        if isinstance(skills_raw, str):
            try:
                skills_raw = json.loads(skills_raw)
            except Exception:
                skills_raw = []
        elif not skills_raw:
            skills_raw = []

        if not skills_raw:
            skills_raw = get_initial_commander_skills(meow.template_id)

        for s in skills_raw:
            skill_id = int(s.get("id", 0) if isinstance(s, dict) else getattr(s, "id", 0))
            if skill_id == 0:
                continue
            skill_cfg = get_commander_skill_config(skill_id)
            if not skill_cfg:
                continue

            effects = skill_cfg.get("effect_tactic", [])
            for eff_id in effects:
                eff = get_commander_skill_effect_config(int(eff_id))
                if not eff:
                    continue

                # Condition check for sub team
                cond = eff.get("condition", [])
                valid_cond = True
                for clause in cond:
                    if clause and clause[0] == "insubteam" and len(clause) > 1:
                        if int(clause[1]) != 1:
                            valid_cond = False
                            break
                if not valid_cond:
                    continue

                eff_type = eff.get("effect_type", "")
                args = eff.get("args", [])
                if eff_type == "hunt_lv" and args:
                    extra_hunting_lv += int(args[0])
                elif eff_type == "torpedo_power_up" and len(args) >= 4:
                    mult = float(args[3]) / 100.0
                    max_cap = max(max_cap, DEFAULT_MAX_DAMAGE_CAP * mult)

    return extra_hunting_lv, max_cap


def get_sub_group_hunting_range(group, client) -> set[tuple[int, int]]:
    """Calculates all absolute (row, column) coordinates in the submarine group's hunting range."""
    ship_list = getattr(group, "ship_list", [])
    flagship_id = 0
    for s in ship_list:
        s_id = getattr(s, "id", 0)
        if s_id != 0:
            flagship_id = s_id
            break

    if flagship_id == 0:
        return set()

    cmd = getattr(client, "commander", None) if client else None
    owned_map = getattr(cmd, "owned_ships_map", None) or {}
    owner_id = getattr(cmd, "commander_id", 0) if cmd else 0

    tpl_id = _resolve_ship_template_id(flagship_id, owned_map)
    if not tpl_id:
        return set()

    entry = _get_config_entry("sharecfgdata/ship_data_statistics.json", str(tpl_id))
    if not entry or not isinstance(entry, dict):
        return set()

    hunting_range_raw = entry.get("hunting_range", [])
    base_hunting_lv = int(entry.get("huntingrange_level", 1) or 1)

    extra_lv, _ = get_sub_group_commander_bonuses(group, owner_id)
    total_hunting_lv = max(1, min(base_hunting_lv + extra_lv, len(hunting_range_raw)))

    # Center is start_pos (fallback to pos)
    start_pos = getattr(group, "start_pos", None)
    if start_pos and (start_pos.row != 0 or start_pos.column != 0):
        c_row, c_col = start_pos.row, start_pos.column
    else:
        pos = getattr(group, "pos", None)
        c_row, c_col = (pos.row, pos.column) if pos else (0, 0)

    tiles = set()
    for lvl in range(total_hunting_lv):
        level_offsets = hunting_range_raw[lvl]
        for offset in level_offsets:
            if len(offset) >= 2:
                tiles.add((c_row + offset[0], c_col + offset[1]))

    return tiles


def evaluate_submarine_auto_attacks(
    client, current
) -> tuple[list[protobuf.AI_ACT_P13], list[protobuf.CHAPTERCELLINFO_P13]]:
    """
    Evaluates whether submarine fleet(s) in Attack Mode (is_submarine_auto_attack == 1)
    execute an autonomous torpedo strike against unattacked enemy nodes in their hunting range.

    Returns:
      (sub_act_list, map_updates)
    """
    if getattr(current, "is_submarine_auto_attack", 0) != 1:
        return [], []

    sub_groups = getattr(current, "submarine_group_list", [])
    if not sub_groups:
        return [], []

    cmd = getattr(client, "commander", None) if client else None
    if cmd is None:
        return [], []

    if getattr(cmd, "owned_ships_map", None) is None and hasattr(cmd, "load"):
        cmd.load()
    owned_map = getattr(cmd, "owned_ships_map", None) or {}
    owner_id = getattr(cmd, "commander_id", 0)

    # Surface fleet positions (subs will not attack nodes currently engaged/occupied by surface fleet)
    occupied_positions = set()
    for mg in getattr(current, "main_group_list", []):
        occupied_positions.add((mg.pos.row, mg.pos.column))

    acts = []
    map_updates = []

    for group in sub_groups:
        if getattr(group, "bullet", 0) <= 0:
            continue

        hunting_tiles = get_sub_group_hunting_range(group, client)
        if not hunting_tiles:
            continue

        # Find eligible unattacked enemy cells in hunting range
        candidate_cells = []
        for cell in getattr(current, "cell_list", []):
            if getattr(cell, "item_flag", 0) != CHAPTER_CELL_ACTIVE:
                continue
            item_type = getattr(cell, "item_type", 0)
            if item_type not in SUB_ATTACKABLE_ENEMY_ATTACHMENTS:
                continue
            # Already attacked / damaged by sub
            if getattr(cell, "item_data", 0) > 0:
                continue
            pos_tuple = (cell.pos.row, cell.pos.column)
            if pos_tuple not in hunting_tiles:
                continue
            if pos_tuple in occupied_positions:
                continue

            candidate_cells.append(cell)

        if not candidate_cells:
            continue

        # Sort candidate cells row-by-row (top-to-bottom, left-to-right)
        candidate_cells.sort(key=lambda c: (c.pos.row, c.pos.column))
        target_cell = candidate_cells[0]

        # Calculate fleet combat power and average level
        ship_list = getattr(group, "ship_list", [])
        total_power = 0.0
        levels = []
        for s in ship_list:
            s_id = getattr(s, "id", 0)
            if s_id == 0:
                continue
            owned = owned_map.get(s_id)
            if owned is None:
                continue
            lvl = getattr(owned, "level", 1) or 1
            levels.append(lvl)
            total_power += calculate_ship_combat_power(owned, owner_id)

        if not levels:
            avg_sub_level = 1.0
            total_power = 5000.0
        else:
            avg_sub_level = sum(levels) / len(levels)
            total_power = max(500.0, total_power)

        enemy_level = get_expedition_level(getattr(target_cell, "item_id", 0))

        # Check Meowfficer damage cap boost
        _, max_cap = get_sub_group_commander_bonuses(group, owner_id)
        from src.config.game_variables import get_sub_strike_damage_caps
        min_cap, _ = get_sub_strike_damage_caps()

        # Formula:
        # Node HP Reduction % = 0.15 * sqrt(Sub Fleet Power) + 0.25 * (Avg Sub Level - Enemy Level)
        raw_reduction = 0.15 * math.sqrt(total_power) + 0.25 * (avg_sub_level - enemy_level)
        clamped_reduction = max(min_cap, min(max_cap, raw_reduction))

        # Stored as basis points in item_data (e.g. 18.5% -> 1850)
        reduction_basis_points = int(round(clamped_reduction * 100))

        # Deduct 1 ammo
        group.bullet = max(0, group.bullet - 1)

        # Apply damage reduction to target cell
        target_cell.item_data = reduction_basis_points
        map_updates.append(target_cell)

        # Build AI_ACT_P13
        sub_act = protobuf.AI_ACT_P13()
        sub_act.ai_pos.row = group.pos.row
        sub_act.ai_pos.column = group.pos.column
        sub_act.target_pos.row = target_cell.pos.row
        sub_act.target_pos.column = target_cell.pos.column
        sub_act.act_type = 2  # ChapterConst.ActType_SubmarineHunting

        cell_upd = sub_act.map_update.add()
        cell_upd.pos.row = target_cell.pos.row
        cell_upd.pos.column = target_cell.pos.column
        cell_upd.item_type = target_cell.item_type
        cell_upd.item_id = target_cell.item_id
        cell_upd.item_flag = target_cell.item_flag
        cell_upd.item_data = target_cell.item_data

        acts.append(sub_act)

        log_event(
            "chapter",
            "submarine_strike",
            f"Submarine fleet {group.id} launched Attack Mode strike against ({target_cell.pos.row}, {target_cell.pos.column}): "
            f"-{clamped_reduction:.2f}% HP ({reduction_basis_points} bp), remaining ammo: {group.bullet}",
        )

        # Only one attack per submarine fleet per turn
        break

    return acts, map_updates
