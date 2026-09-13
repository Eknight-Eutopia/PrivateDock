from __future__ import annotations

from dataclasses import dataclass

from src.orm.meta_character_config import (
    get_ship_data_template_meta_config,
    get_ship_meta_skill_task_config,
)


@dataclass
class MetaTacticsSkillSlot:
    skill_id: int = 0
    pos: int = 0


def get_meta_tactics_skill_slots_by_ship_template(ship_template_id: int) -> list[MetaTacticsSkillSlot]:
    ship_cfg = get_ship_data_template_meta_config(ship_template_id)
    if ship_cfg is None:
        raise ValueError(f"ship data template meta config not found: {ship_template_id}")
    result = []
    for buff_id in ship_cfg.buff_list_display:
        found = get_ship_meta_skill_task_config(buff_id, 1)
        if found is not None:
            result.append(MetaTacticsSkillSlot(skill_id=buff_id, pos=len(result) + 1))
    return result
