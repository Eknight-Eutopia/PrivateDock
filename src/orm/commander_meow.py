from __future__ import annotations
import json
import math
import os
import random
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session
from src.misc import DATA_DIR
from src.protobuf import protobuf

_TEMPLATES_CACHE: dict[int, dict] = {}
_GROUPS_CACHE: list[dict] = []
_LEVELS_CACHE: dict[int, dict] = {}
_SKILLS_CACHE: dict[int, dict] = {}
_SKILL_EFFECTS_CACHE: dict[int, dict] = {}
_MATERIALS_CACHE: dict[int, dict] = {}


def get_commander_template(template_id: int) -> dict | None:
    global _TEMPLATES_CACHE
    if not _TEMPLATES_CACHE:
        path = os.path.join(DATA_DIR, "EN", "ShareCfg", "commander_data_template.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                items = data if isinstance(data, list) else data.values()
                for it in items:
                    if isinstance(it, dict) and "id" in it:
                        _TEMPLATES_CACHE[int(it["id"])] = it
        except Exception:
            pass
    return _TEMPLATES_CACHE.get(template_id)


def get_commander_ability_groups() -> list[dict]:
    global _GROUPS_CACHE
    if not _GROUPS_CACHE:
        path = os.path.join(DATA_DIR, "EN", "ShareCfg", "commander_ability_group.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                _GROUPS_CACHE = data if isinstance(data, list) else list(data.values())
        except Exception:
            pass
    return _GROUPS_CACHE


def get_commander_level_config(level: int) -> dict | None:
    global _LEVELS_CACHE
    if not _LEVELS_CACHE:
        path = os.path.join(DATA_DIR, "EN", "ShareCfg", "commander_level.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                items = data if isinstance(data, list) else data.values()
                for it in items:
                    if isinstance(it, dict) and "level" in it:
                        _LEVELS_CACHE[int(it["level"])] = it
        except Exception:
            pass
    return _LEVELS_CACHE.get(level)


def get_commander_skill_config(skill_id: int) -> dict | None:
    global _SKILLS_CACHE
    if not _SKILLS_CACHE:
        path = os.path.join(DATA_DIR, "EN", "ShareCfg", "commander_skill_template.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                items = data if isinstance(data, list) else data.values()
                for it in items:
                    if isinstance(it, dict) and "id" in it:
                        _SKILLS_CACHE[int(it["id"])] = it
        except Exception:
            pass
    return _SKILLS_CACHE.get(skill_id)


def get_commander_skill_effect_config(effect_id: int) -> dict | None:
    global _SKILL_EFFECTS_CACHE
    if not _SKILL_EFFECTS_CACHE:
        path = os.path.join(DATA_DIR, "EN", "ShareCfg", "commander_skill_effect_template.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                items = data if isinstance(data, list) else data.values()
                for it in items:
                    if isinstance(it, dict) and "id" in it:
                        _SKILL_EFFECTS_CACHE[int(it["id"])] = it
        except Exception:
            pass
    return _SKILL_EFFECTS_CACHE.get(effect_id)


def get_commander_next_level_exp(level: int, rarity: int) -> int:
    cfg = get_commander_level_config(level)
    if not cfg:
        return 999999
    return int(cfg.get(f"exp_{rarity}", cfg.get("exp", 999999)))


def add_commander_exp(level: int, current_exp: int, gain_exp: int, rarity: int, max_level: int = 30) -> tuple[int, int]:
    if level >= max_level:
        return max_level, 0
    exp = current_exp + gain_exp
    while level < max_level:
        next_exp = get_commander_next_level_exp(level, rarity)
        if exp >= next_exp:
            exp -= next_exp
            level += 1
        else:
            break
    if level >= max_level:
        exp = 0
    return level, exp


def add_commander_skill_exp(skills: list[dict], gain: int) -> list[dict]:
    if not skills or gain <= 0:
        return skills
    res = [dict(s) for s in skills]
    cur_skill = res[0]
    cur_id = cur_skill.get("id", 0)
    cur_exp = cur_skill.get("exp", 0) + gain
    cfg = get_commander_skill_config(cur_id)
    while cfg and cfg.get("next_id") and cfg.get("next_id") != 0 and cfg.get("exp", 0) > 0:
        need_exp = cfg["exp"]
        if cur_exp >= need_exp:
            cur_exp -= need_exp
            cur_id = cfg["next_id"]
            cfg = get_commander_skill_config(cur_id)
        else:
            break
    cur_skill["id"] = cur_id
    cur_skill["exp"] = cur_exp
    res[0] = cur_skill
    return res


def get_initial_commander_skills(template_id: int) -> list[dict]:
    tpl = get_commander_template(template_id)
    skill_id = tpl.get("skill_id", template_id) if tpl else template_id
    return [{"id": int(skill_id), "exp": 0}]


def roll_initial_commander_talents(template_id: int) -> tuple[list[int], list[int]]:
    tpl = get_commander_template(template_id)
    rarity = tpl.get("rarity", 3) if tpl else 3
    num_talents = 1
    if rarity == 4:
        num_talents = 2
    elif rarity >= 5:
        num_talents = 3

    groups = get_commander_ability_groups()
    valid_groups = [g for g in groups if g.get("ability_list")]
    if not valid_groups:
        return [101], [101]

    chosen = random.sample(valid_groups, min(num_talents, len(valid_groups)))
    talents = [int(g["ability_list"][0]) for g in chosen]
    return talents, list(talents)


def populate_proto_commander_info(entry: protobuf.COMMANDERINFO, meow) -> None:
    if meow is None:
        return

    if isinstance(meow, dict):
        entry.id = meow.get("id", 0)
        entry.template_id = meow.get("template_id", 0)
        entry.level = meow.get("level", 1) or 1
        entry.exp = meow.get("exp", 0) or 0
        entry.is_locked = meow.get("is_locked", 0) or 0
        entry.used_pt = meow.get("used_pt", 0) or 0
        entry.ability_time = meow.get("ability_time", 0) or 0
        entry.name = meow.get("name", "") or ""
        entry.rename_time = meow.get("rename_time", 0) or 0
        skills_raw = meow.get("skills") or meow.get("skill")
        ability_raw = meow.get("ability")
        ability_origin_raw = meow.get("ability_origin")
    else:
        entry.id = getattr(meow, "id", 0)
        entry.template_id = getattr(meow, "template_id", 0)
        entry.level = getattr(meow, "level", 1) or 1
        entry.exp = getattr(meow, "exp", 0) or 0
        entry.is_locked = getattr(meow, "is_locked", 0) or 0
        entry.used_pt = getattr(meow, "used_pt", 0) or 0
        entry.ability_time = getattr(meow, "ability_time", 0) or 0
        entry.name = getattr(meow, "name", "") or ""
        entry.rename_time = getattr(meow, "rename_time", 0) or 0
        skills_raw = getattr(meow, "skills", None) or getattr(meow, "skill", None)
        ability_raw = getattr(meow, "ability", None)
        ability_origin_raw = getattr(meow, "ability_origin", None)

    # Parse skills
    if isinstance(skills_raw, str):
        try:
            skills_raw = json.loads(skills_raw)
        except Exception:
            skills_raw = []
    if not skills_raw:
        skills_raw = get_initial_commander_skills(entry.template_id)
    for s in skills_raw:
        se = entry.skill.add()
        se.id = int(s.get("id", 0) if isinstance(s, dict) else getattr(s, "id", 0))
        se.exp = int(s.get("exp", 0) if isinstance(s, dict) else getattr(s, "exp", 0))

    # Parse abilities
    if isinstance(ability_raw, str):
        try:
            ability_raw = json.loads(ability_raw)
        except Exception:
            ability_raw = []
    if isinstance(ability_origin_raw, str):
        try:
            ability_origin_raw = json.loads(ability_origin_raw)
        except Exception:
            ability_origin_raw = []

    if not ability_raw:
        ability_raw, ability_origin_raw = roll_initial_commander_talents(entry.template_id)

    entry.ability.extend([int(a) for a in ability_raw])
    entry.ability_origin.extend([int(a) for a in (ability_origin_raw or ability_raw)])


def ensure_commander_meows(commander_id: int, meow_ids: list[int]):
    with get_sync_session() as session:
        existing = session.execute(
            select(CommanderMeow).where(CommanderMeow.commander_id == commander_id)
        ).scalars().all()
        existing_ids = {m.id for m in existing}
        for mid in meow_ids:
            if mid not in existing_ids:
                skills = get_initial_commander_skills(mid)
                ability, ability_origin = roll_initial_commander_talents(mid)
                session.add(
                    CommanderMeow(
                        commander_id=commander_id,
                        template_id=mid,
                        level=1,
                        skills=json.dumps(skills),
                        ability=json.dumps(ability),
                        ability_origin=json.dumps(ability_origin),
                    )
                )
        session.commit()


def get_commander_meow(commander_id: int, meow_id: int) -> CommanderMeow | None:
    with get_sync_session() as session:
        return session.execute(
            select(CommanderMeow).where(
                CommanderMeow.commander_id == commander_id,
                CommanderMeow.id == meow_id,
            )
        ).scalar_one_or_none()


def list_commander_meows(commander_id: int) -> list[CommanderMeow]:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderMeow).where(CommanderMeow.commander_id == commander_id)
        )
        return list(result.scalars().all())


def create_commander_meow(commander_id: int, template_id: int) -> CommanderMeow:
    skills = get_initial_commander_skills(template_id)
    ability, ability_origin = roll_initial_commander_talents(template_id)
    with get_sync_session() as session:
        obj = CommanderMeow(
            commander_id=commander_id,
            template_id=template_id,
            level=1,
            skills=json.dumps(skills),
            ability=json.dumps(ability),
            ability_origin=json.dumps(ability_origin),
            name="",
            rename_time=0,
        )
        session.add(obj)
        session.commit()
        session.refresh(obj)
        return obj


def delete_commander_meows(commander_id: int, meow_ids: list[int]):
    with get_sync_session() as session:
        for mid in meow_ids:
            obj = session.execute(
                select(CommanderMeow).where(
                    CommanderMeow.commander_id == commander_id,
                    CommanderMeow.id == mid,
                )
            ).scalar_one_or_none()
            if obj is not None:
                session.delete(obj)
        session.commit()


def update_commander_meow_exp(commander_id: int, meow_id: int, exp: int):
    with get_sync_session() as session:
        obj = session.execute(
            select(CommanderMeow).where(
                CommanderMeow.commander_id == commander_id,
                CommanderMeow.id == meow_id,
            )
        ).scalar_one_or_none()
        if obj is not None:
            obj.exp = exp
            session.commit()


def update_commander_meow_level_exp(commander_id: int, meow_id: int, level: int, exp: int, skills: list | None = None):
    with get_sync_session() as session:
        obj = session.execute(
            select(CommanderMeow).where(
                CommanderMeow.commander_id == commander_id,
                CommanderMeow.id == meow_id,
            )
        ).scalar_one_or_none()
        if obj is not None:
            obj.level = level
            obj.exp = exp
            if skills is not None:
                obj.skills = json.dumps(skills)
            session.commit()


def update_commander_meow_lock(commander_id: int, meow_id: int, is_locked: int):
    with get_sync_session() as session:
        obj = session.execute(
            select(CommanderMeow).where(
                CommanderMeow.commander_id == commander_id,
                CommanderMeow.id == meow_id,
            )
        ).scalar_one_or_none()
        if obj is not None:
            obj.is_locked = is_locked
            session.commit()


def update_commander_meow_name(commander_id: int, meow_id: int, name: str, rename_time: int):
    with get_sync_session() as session:
        obj = session.execute(
            select(CommanderMeow).where(
                CommanderMeow.commander_id == commander_id,
                CommanderMeow.id == meow_id,
            )
        ).scalar_one_or_none()
        if obj is not None:
            obj.name = name
            obj.rename_time = rename_time
            session.commit()


def is_commander_meow_in_any_fleet(commander_id: int, meow_id: int) -> bool:
    if not meow_id:
        return False
    from src.orm.fleet import Fleet
    with get_sync_session() as session:
        fleets = session.execute(
            select(Fleet).where(Fleet.commander_id == commander_id)
        ).scalars().all()
        for f in fleets:
            raw = getattr(f, "meowfficer_list", None)
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except Exception:
                    raw = []
            if isinstance(raw, list) and meow_id in raw:
                return True
        return False


def update_fleet_meowfficer_slot(commander_id: int, game_id: int, pos: int, meow_id: int):
    if pos not in (1, 2):
        return
    from src.orm.fleet import Fleet
    from sqlalchemy.orm.attributes import flag_modified
    with get_sync_session() as session:
        # If equipping a Meowfficer (meow_id != 0), clear it from any other fleet or slot
        if meow_id != 0:
            all_fleets = session.execute(
                select(Fleet).where(Fleet.commander_id == commander_id)
            ).scalars().all()
            for f in all_fleets:
                raw_f = getattr(f, "meowfficer_list", None)
                if isinstance(raw_f, str):
                    try:
                        raw_f = json.loads(raw_f)
                    except Exception:
                        raw_f = []
                if not isinstance(raw_f, list):
                    raw_f = []
                new_f = list(raw_f)
                while len(new_f) < 2:
                    new_f.append(0)
                changed = False
                for idx, mid in enumerate(new_f):
                    if mid == meow_id and (f.game_id != game_id or (idx + 1) != pos):
                        new_f[idx] = 0
                        changed = True
                if changed:
                    f.meowfficer_list = new_f
                    flag_modified(f, "meowfficer_list")

        fleet = session.execute(
            select(Fleet).where(
                Fleet.commander_id == commander_id,
                Fleet.game_id == game_id,
            )
        ).scalar_one_or_none()
        if fleet is None:
            fleet = Fleet(
                commander_id=commander_id,
                game_id=game_id,
                name="",
                ship_list=[],
                meowfficer_list=[0, 0],
            )
            session.add(fleet)
            session.flush()

        raw = getattr(fleet, "meowfficer_list", None)
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                raw = []
        if not isinstance(raw, list):
            raw = []
        new_list = list(raw)
        while len(new_list) < 2:
            new_list.append(0)
        new_list[pos - 1] = meow_id
        fleet.meowfficer_list = new_list
        flag_modified(fleet, "meowfficer_list")
        session.commit()


def get_commander_create_material_config(pool_id: int = 1) -> dict:
    global _MATERIALS_CACHE
    if not _MATERIALS_CACHE:
        path = os.path.join(DATA_DIR, "EN", "ShareCfg", "commander_data_create_material.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                items = data if isinstance(data, list) else data.values()
                for it in items:
                    if isinstance(it, dict) and "id" in it:
                        _MATERIALS_CACHE[int(it["id"])] = it
        except Exception:
            pass
    return _MATERIALS_CACHE.get(pool_id, {})


def get_commander_data_template_config() -> dict:
    return {}


def get_commander_ability_template() -> dict:
    return {}


def list_commander_ability_groups() -> list:
    return []


def roll_commander_template_for_pool(pool_id: int = 1) -> int:
    target_rarity = pool_id + 2
    fallbacks = {
        3: [12011, 12021, 22011, 22021, 32011, 32021, 42011, 42021],
        4: [11011, 11021, 21011, 21021, 21031, 21041, 31011, 31021, 41011, 41021, 51011, 51021, 61011, 61021],
        5: [10011, 10021, 20011, 20021, 30011, 30021, 40011, 40021, 50011, 50021, 60011, 60021],
    }
    candidates = []
    try:
        path = os.path.join(DATA_DIR, "EN", "ShareCfg", "commander_data_template.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            items = data if isinstance(data, list) else data.values()
            for item in items:
                if isinstance(item, dict) and item.get("rarity") == target_rarity:
                    candidates.append(int(item["id"]))
    except Exception:
        pass

    if not candidates:
        candidates = fallbacks.get(target_rarity, fallbacks[3])
    return random.choice(candidates)


class CommanderCatteryOpBit:
    pass


COMMANDER_QUICK_FINISH_ITEM_ID = 20010
COMMANDER_QUICK_FINISH_UNIT_SEC = 1200


def compute_commander_quick_finish_counts(boxes: list, now: int, available_items: int) -> dict[str, int]:
    remaining_items = max(0, available_items)
    item_cnt = 0
    finish_cnt = 0
    affect_cnt = 0

    sorted_boxes = sorted(
        boxes,
        key=lambda b: b.get("box_id", b.get("id", 0)) if isinstance(b, dict) else getattr(b, "box_id", getattr(b, "id", 0)),
    )

    for box in sorted_boxes:
        if remaining_items <= 0:
            break

        pool_id = box.get("pool_id", 0) if isinstance(box, dict) else getattr(box, "pool_id", 0)
        finish_time = box.get("finish_time", 0) if isinstance(box, dict) else getattr(box, "finish_time", 0)
        begin_time = box.get("begin_time", 0) if isinstance(box, dict) else getattr(box, "begin_time", 0)

        if pool_id == 0 or finish_time <= now:
            continue

        if now < begin_time:
            remaining = finish_time - begin_time
        else:
            remaining = finish_time - now

        if remaining <= 0:
            continue

        needed = math.ceil(remaining / COMMANDER_QUICK_FINISH_UNIT_SEC)
        if needed <= 0:
            continue

        if needed <= remaining_items:
            item_cnt += needed
            finish_cnt += 1
            affect_cnt += 1
            remaining_items -= needed
        else:
            item_cnt += remaining_items
            affect_cnt += 1
            remaining_items = 0
            break

    return {
        "item_cnt": item_cnt,
        "finish_cnt": finish_cnt,
        "affect_cnt": affect_cnt,
    }


def apply_commander_quick_finish(boxes: list, now: int, item_count: int) -> list:
    from src.orm.commander_box import upsert_commander_box

    remaining_items = max(0, item_count)
    sorted_boxes = sorted(
        boxes,
        key=lambda b: b.get("box_id", b.get("id", 0)) if isinstance(b, dict) else getattr(b, "box_id", getattr(b, "id", 0)),
    )
    updated_boxes = []

    for box in sorted_boxes:
        if remaining_items <= 0:
            updated_boxes.append(box)
            continue

        pool_id = box.get("pool_id", 0) if isinstance(box, dict) else getattr(box, "pool_id", 0)
        finish_time = box.get("finish_time", 0) if isinstance(box, dict) else getattr(box, "finish_time", 0)
        begin_time = box.get("begin_time", 0) if isinstance(box, dict) else getattr(box, "begin_time", 0)

        if pool_id == 0 or finish_time <= now:
            updated_boxes.append(box)
            continue

        if now < begin_time:
            remaining = finish_time - begin_time
        else:
            remaining = finish_time - now

        if remaining <= 0:
            updated_boxes.append(box)
            continue

        needed = math.ceil(remaining / COMMANDER_QUICK_FINISH_UNIT_SEC)
        if needed <= 0:
            updated_boxes.append(box)
            continue

        spend = min(needed, remaining_items)
        reduction = spend * COMMANDER_QUICK_FINISH_UNIT_SEC

        if reduction >= remaining:
            new_finish_time = now
            new_begin_time = min(begin_time, now)
        else:
            new_finish_time = finish_time - reduction
            new_begin_time = min(begin_time, new_finish_time)

        if isinstance(box, dict):
            box["finish_time"] = new_finish_time
            box["begin_time"] = new_begin_time
        else:
            box.finish_time = new_finish_time
            box.begin_time = new_begin_time

        upsert_commander_box(box)
        remaining_items -= spend
        updated_boxes.append(box)

    return updated_boxes


def get_commander_upgrade_rates() -> tuple[int, int, int]:
    from src.answer.remaster_config import load_gameset_value
    val = load_gameset_value("commander_exp_same_rate")
    same_rate = val if val is not None else 12000
    val_skill = load_gameset_value("commander_skill_exp")
    skill_exp = val_skill if val_skill is not None else 1
    return same_rate, skill_exp, 0


class CommanderMeow(Base):
    __tablename__ = 'commander_meows'
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    commander_id: Mapped[int] = mapped_column(BigInteger)
    template_id: Mapped[int] = mapped_column(BigInteger, default=0)
    level: Mapped[int] = mapped_column(BigInteger, default=1)
    exp: Mapped[int] = mapped_column(BigInteger, default=0)
    is_locked: Mapped[int] = mapped_column(BigInteger, default=0)
    used_pt: Mapped[int] = mapped_column(BigInteger, default=0)
    skills: Mapped[str] = mapped_column(Text, default="[]")
    ability: Mapped[str] = mapped_column(Text, default="[]")
    ability_origin: Mapped[str] = mapped_column(Text, default="[]")
    name: Mapped[str] = mapped_column(Text, default="")
    rename_time: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
