from __future__ import annotations

from typing import Any
from dataclasses import dataclass, field

from sqlalchemy import select

from src.db.session import get_sync_session
from src.orm.config_entry import ConfigEntry

SHIP_META_REPAIR_CATEGORY = "ShareCfg/ship_meta_repair.json"
SHIP_META_SKILL_TASK_CATEGORY = "ShareCfg/ship_meta_skilltask.json"
SHIP_META_BREAKOUT_CATEGORY = "ShareCfg/ship_meta_breakout.json"
SHIP_STRENGTHEN_META_CATEGORY = "ShareCfg/ship_strengthen_meta.json"
SKILL_DATA_TEMPLATE_CATEGORY = "ShareCfg/skill_data_template.json"
ITEM_DATA_STATISTICS_CATEGORY = "sharecfgdata/item_data_statistics.json"
ITEM_DATA_STATISTICS_CATEGORY2 = "ShareCfg/item_data_statistics.json"
SHIP_DATA_TEMPLATE_CATEGORY = "sharecfgdata/ship_data_template.json"


@dataclass
class ShipMetaRepairConfig:
    id: int = 0
    item_id: int = 0
    item_num: int = 0
    repair_exp: int = 0


@dataclass
class ShipMetaBreakoutConfig:
    id: int = 0
    breakout_id: int = 0
    gold: int = 0
    item1: int = 0
    item1_num: int = 0
    item2: int = 0
    item2_num: int = 0
    level: int = 0
    repair: int = 0


@dataclass
class ShipStrengthenMetaConfig:
    id: int = 0
    ship_id: int = 0
    type: int = 0
    repair_cannon: list[int] = field(default_factory=list)
    repair_torpedo: list[int] = field(default_factory=list)
    repair_air: list[int] = field(default_factory=list)
    repair_reload: list[int] = field(default_factory=list)
    repair_total_exp: int = 0


@dataclass
class ShipMetaSkillTaskConfig:
    id: int = 0
    level: int = 0
    need_exp: int = 0
    skill_id: int = 0
    skill_levelup_task: list[list[int]] = field(default_factory=list)
    skill_unlock: list[list[int]] = field(default_factory=list)


@dataclass
class SkillDataTemplateConfig:
    id: int = 0
    max_level: int = 0


@dataclass
class ShipDataTemplateMetaConfig:
    id: int = 0
    buff_list_display: list[int] = field(default_factory=list)


@dataclass
class ItemDataStatisticsConfig:
    id: int = 0
    type: int = 0
    usage_arg: Any = None


def _get_config_entry(category: str, key: str) -> ConfigEntry:
    with get_sync_session() as session:
        result = session.execute(
            select(ConfigEntry).where(
                ConfigEntry.category == category,
                ConfigEntry.key == key,
            )
        )
        entry = result.scalar_one_or_none()
    if entry is None:
        raise ValueError(f"config entry not found: {category}/{key}")
    return entry


def _list_config_entries(category: str) -> list[ConfigEntry]:
    with get_sync_session() as session:
        result = session.execute(
            select(ConfigEntry).where(ConfigEntry.category == category)
        )
        return list(result.scalars().all())


def get_ship_meta_repair_config(repair_id: int) -> ShipMetaRepairConfig:
    entry = _get_config_entry(SHIP_META_REPAIR_CATEGORY, str(repair_id))
    return ShipMetaRepairConfig(**entry.data)


def get_ship_meta_breakout_config(template_id: int) -> ShipMetaBreakoutConfig:
    entry = _get_config_entry(SHIP_META_BREAKOUT_CATEGORY, str(template_id))
    return ShipMetaBreakoutConfig(**entry.data)


def get_ship_strengthen_meta_config(meta_id: int) -> ShipStrengthenMetaConfig:
    entry = _get_config_entry(SHIP_STRENGTHEN_META_CATEGORY, str(meta_id))
    return ShipStrengthenMetaConfig(**entry.data)


def get_ship_meta_skill_task_config_by_id(id: int) -> ShipMetaSkillTaskConfig:
    entry = _get_config_entry(SHIP_META_SKILL_TASK_CATEGORY, str(id))
    return ShipMetaSkillTaskConfig(**entry.data)


def get_ship_meta_skill_task_config(skill_id: int, level: int) -> ShipMetaSkillTaskConfig | None:
    entries = _list_config_entries(SHIP_META_SKILL_TASK_CATEGORY)
    for entry in entries:
        cfg = ShipMetaSkillTaskConfig(**entry.data)
        if cfg.skill_id == skill_id and cfg.level == level:
            return cfg
    return None


def list_ship_meta_skill_task_configs_by_skill(skill_id: int) -> list[ShipMetaSkillTaskConfig]:
    entries = _list_config_entries(SHIP_META_SKILL_TASK_CATEGORY)
    result = []
    for entry in entries:
        cfg = ShipMetaSkillTaskConfig(**entry.data)
        if cfg.skill_id == skill_id:
            result.append(cfg)
    return result


def get_skill_data_template_config(skill_id: int) -> SkillDataTemplateConfig:
    entry = _get_config_entry(SKILL_DATA_TEMPLATE_CATEGORY, str(skill_id))
    return SkillDataTemplateConfig(**entry.data)


def get_ship_data_template_meta_config(template_id: int) -> ShipDataTemplateMetaConfig:
    entry = _get_config_entry(SHIP_DATA_TEMPLATE_CATEGORY, str(template_id))
    return ShipDataTemplateMetaConfig(**entry.data)


def get_item_data_statistics_config(item_id: int) -> ItemDataStatisticsConfig:
    with get_sync_session() as session:
        result = session.execute(
            select(ConfigEntry).where(
                ConfigEntry.category == ITEM_DATA_STATISTICS_CATEGORY,
                ConfigEntry.key == str(item_id),
            )
        )
        entry = result.scalar_one_or_none()
        if entry is None:
            result = session.execute(
                select(ConfigEntry).where(
                    ConfigEntry.category == ITEM_DATA_STATISTICS_CATEGORY2,
                    ConfigEntry.key == str(item_id),
                )
            )
            entry = result.scalar_one_or_none()
    if entry is None:
        raise ValueError(f"item data statistics config not found: {item_id}")
    return ItemDataStatisticsConfig(**entry.data)
