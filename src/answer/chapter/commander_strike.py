from __future__ import annotations

import json
import random
from typing import Optional

from src.logger.logger import log_event, LOG_LEVEL_INFO
from src.orm.commander_meow import (
    get_commander_meow,
    get_commander_skill_config,
    get_commander_skill_effect_config,
    get_initial_commander_skills,
)
from src.orm.game_data import get_ship_template_config
from src.protobuf import protobuf
from src.answer.chapter.helpers import (
    CHAPTER_ATTACH_BOMB_ENEMY,
    CHAPTER_ATTACH_BOSS,
    CHAPTER_ATTACH_CHAMPION,
    CHAPTER_ATTACH_ELITE,
    CHAPTER_ATTACH_ENEMY,
    CHAPTER_ATTACH_TORPEDO_ENEMY,
    CHAPTER_CELL_ACTIVE,
)

NON_BOSS_ENEMY_ATTACHMENTS = {
    CHAPTER_ATTACH_ENEMY,
    CHAPTER_ATTACH_ELITE,
    CHAPTER_ATTACH_TORPEDO_ENEMY,
    CHAPTER_ATTACH_CHAMPION,
    CHAPTER_ATTACH_BOMB_ENEMY,
}


def is_strike_target_cell(cell) -> bool:
    """Checks if a chapter cell is a valid non-boss enemy target for a preemptive strike."""
    if cell is None:
        return False
    if getattr(cell, "item_flag", 0) != CHAPTER_CELL_ACTIVE:
        return False
    item_type = getattr(cell, "item_type", 0)
    if item_type == CHAPTER_ATTACH_BOSS:
        return False
    if item_type not in NON_BOSS_ENEMY_ATTACHMENTS:
        return False
    if getattr(cell, "item_data", 0) >= 10000:
        return False
    return True


def check_skill_condition(condition, commander_pos: int, group, client) -> bool:
    """
    Validates condition clauses from commander_skill_effect_template:
      - ['pos', 1]: Requires commander equipped at slot 1 (Command Cat) or 2 (Staff Cat).
      - ['count', [1, 20, 21], 1, 6]: Fleet must have between min and max alive ships of allowed types.
      - ['insubteam', 1]: Submarine team condition (always False for surface fleet).
    """
    if not condition:
        return True

    if isinstance(condition, dict):
        clauses = list(condition.values())
    elif isinstance(condition, (list, tuple)):
        clauses = condition
    else:
        return True

    for clause in clauses:
        if not clause or not isinstance(clause, (list, tuple)):
            continue
        c_type = clause[0]

        if c_type == "pos":
            if len(clause) > 1 and commander_pos != int(clause[1]):
                return False

        elif c_type == "count":
            if len(clause) < 2:
                continue
            allowed = clause[1]
            if isinstance(allowed, (list, tuple, set)):
                allowed_set = {int(x) for x in allowed}
            else:
                allowed_set = {int(allowed)}

            min_count = int(clause[2]) if len(clause) > 2 else 1
            max_count = int(clause[3]) if len(clause) > 3 else 999

            matching_ships = 0
            if group and client and getattr(client, "commander", None):
                cmd = client.commander
                if getattr(cmd, "owned_ships_map", None) is None and hasattr(cmd, "load"):
                    cmd.load()
                owned_map = getattr(cmd, "owned_ships_map", None) or {}

                for s in getattr(group, "ship_list", []):
                    s_id = getattr(s, "id", 0)
                    hp = getattr(s, "hp_rant", 10000)
                    if s_id == 0 or hp <= 0:
                        continue
                    owned = owned_map.get(s_id)
                    if owned is None:
                        continue
                    cfg = get_ship_template_config(owned.ship_id)
                    if cfg and cfg.get("type") in allowed_set:
                        matching_ships += 1

            if not (min_count <= matching_ships <= max_count):
                return False

        elif c_type == "insubteam":
            req = int(clause[1]) if len(clause) > 1 else 0
            if req == 1:
                return False

    return True


def evaluate_commander_preemptive_strikes(
    client,
    current,
    group,
    target_cell,
    rng: Optional[random.Random] = None,
) -> list[protobuf.AI_ACT_P13]:
    """
    Evaluates whether equipped Meowfficers in `group` trigger preemptive strike(s)
    against `target_cell` when contacting it during chapter movement.

    Returns a list of AI_ACT_P13 messages for SC_13104.fleet_act_list,
    and updates `target_cell.item_data` with the cumulative damage.
    """
    if not is_strike_target_cell(target_cell):
        return []

    if client is None or getattr(client, "commander", None) is None:
        return []

    commander_id = client.commander.commander_id
    acts = []

    commander_list = getattr(group, "commander_list", [])
    for c in commander_list:
        pos = getattr(c, "pos", 0)
        meow_id = getattr(c, "id", 0)
        if meow_id == 0:
            continue

        meow = get_commander_meow(commander_id, meow_id)
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

            tactics = skill_cfg.get("effect_tactic", [])
            for tactic_id in tactics:
                effect_cfg = get_commander_skill_effect_config(int(tactic_id))
                if not effect_cfg or effect_cfg.get("effect_type") != "attack":
                    continue

                cond = effect_cfg.get("condition", [])
                if not check_skill_condition(cond, pos, group, client):
                    continue

                args = effect_cfg.get("args", [])
                if len(args) < 4:
                    continue

                # args: [anim_name, strategy_id, chance_in_10000, hp_ratio, duration]
                # e.g. ["torpedo", 102, 1500, 0.3, 600]
                chance = int(args[2])
                roll = rng.randint(1, 10000) if rng is not None else random.randint(1, 10000)
                if roll > chance:
                    continue

                ratio = float(args[3])
                hp_del_val = int(round(ratio * 10000))

                new_item_data = min(10000, getattr(target_cell, "item_data", 0) + hp_del_val)
                target_cell.item_data = new_item_data

                act = protobuf.AI_ACT_P13()
                act.act_type = 0
                act.strategy_id = int(args[1]) if isinstance(args[1], int) else 102
                act.commander_skill_effect_id = int(effect_cfg["id"])
                act.hp_del = hp_del_val

                act.ai_pos.row = group.pos.row
                act.ai_pos.column = group.pos.column
                act.target_pos.row = target_cell.pos.row
                act.target_pos.column = target_cell.pos.column

                cell_update = act.map_update.add()
                if isinstance(target_cell, protobuf.CHAPTERCELLINFO_P13):
                    cell_update.CopyFrom(target_cell)
                else:
                    cell_update.pos.row = target_cell.pos.row
                    cell_update.pos.column = target_cell.pos.column
                    cell_update.item_type = getattr(target_cell, "item_type", 0)
                    cell_update.item_id = getattr(target_cell, "item_id", 0)
                    cell_update.item_flag = getattr(target_cell, "item_flag", 0)
                    cell_update.item_data = getattr(target_cell, "item_data", 0)
                    extra = getattr(target_cell, "extra_id", None)
                    if extra:
                        if isinstance(extra, (list, tuple)):
                            cell_update.extra_id.extend([int(x) for x in extra])
                        else:
                            cell_update.extra_id.append(int(extra))

                acts.append(act)

                log_event(
                    "Chapter/CommanderStrike",
                    "Triggered",
                    f"meow_id={meow_id} tactic_id={tactic_id} "
                    f"target=({target_cell.pos.row}, {target_cell.pos.column}) "
                    f"hp_del={hp_del_val} cell_data={new_item_data}",
                    LOG_LEVEL_INFO,
                )

                if target_cell.item_data >= 10000:
                    break

    return acts
