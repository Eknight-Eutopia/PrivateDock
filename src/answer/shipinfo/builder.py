"""Single place that builds protobuf.SHIPINFO for a ship handed to the client.

Every packet that sends a player-owned ship (dock syncs SC_12001/SC_12010,
build collection SC_12026, SC_12042 exchange push, support requisition
SC_16101, meta views 63306/70006) must go through `build_ship_info` /
`build_ship_infos`, so the client always receives a COMPLETE snapshot:
template skills (with trained levels), equip slot skeleton (count from the
ship template config), strengths, transforms, shadow skins and flag phantoms.

Historical bug this fixes: SC_16101 (support requisition) used to build a
minimal SHIPINFO with only base fields, so the freshly bought ships showed
no skills and no equipment slots until re-login.

Intentional exceptions (do NOT route through here):
- `supportship.helpers.blank_assist_ship_info` — a deliberately blank
  placeholder (id=0/template_id=0) for CS_12301;
- the minimal SHIPINFO summaries inside guild TEAM_CHUNK building
  (`guild/event_handlers.py`) — display-only views of other members' ships.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.logger.logger import log_event, LOG_LEVEL_ERROR
from src.misc.safe_ts import safe_ts
from src.protobuf import protobuf

_MISSING = object()

# Column order of the tuple rows returned by owned_ship.list_ships_by_ids.
_ROW_FIELDS = {
    "id": 0,
    "ship_id": 1,
    "level": 2,
    "exp": 3,
    "energy": 4,
    "intimacy": 5,
    "skin_id": 6,
    "max_level": 7,
    "is_locked": 8,
    "propose": 9,
    "common_flag": 10,
    "activity_npc": 11,
    "create_time": 12,
    "custom_name": 13,
    "change_name_timestamp": 14,
    "state": 15,
    "state_info1": 16,
    "state_info2": 17,
    "state_info3": 18,
    "state_info4": 19,
    "proficiency": 20,
}


@dataclass
class ShipInfoContext:
    """Per-commander auxiliary data used to fill a full SHIPINFO snapshot."""

    flags: dict = field(default_factory=dict)       # ship_id -> [phantom_id, ...]
    shadows: dict = field(default_factory=dict)     # ship_id -> [shadow-skin rows]
    equips: dict = field(default_factory=dict)      # ship_id -> [{pos, equip_id, skin_id}]
    strengths: dict = field(default_factory=dict)   # ship_id -> [strength rows]
    transforms: dict = field(default_factory=dict)  # ship_id -> [transform rows]
    skills: dict = field(default_factory=dict)      # (ship_id, skill_id) -> trained row
    spweapons: dict = field(default_factory=dict)   # ship_id -> owned_spweapon


def load_shipinfo_context(commander_id: int, ship_ids=None) -> ShipInfoContext:
    """Bulk-load everything needed to render `ship_ids` (default: all ships).

    Individual loaders never raise: a failure is logged at ERROR and only the
    affected sub-list comes out empty, mirroring the tolerant login-dock
    loading of tactical skills. Ship snapshots must stay serializable even if
    one auxiliary table is missing.
    """
    ctx = ShipInfoContext()
    ids = [int(i) for i in ship_ids] if ship_ids else None

    from src.orm.owned_ship import (
        list_random_flag_ship_phantoms,
        list_owned_ship_shadow_skins,
    )
    from src.orm.equipment import list_all_owned_ship_equipment
    from src.orm.owned_ship_strength import list_all_owned_ship_strengths
    from src.orm.owned_ship_transform import list_owned_ship_transforms_grouped

    try:
        for r in list_random_flag_ship_phantoms(commander_id, ids):
            ctx.flags.setdefault(r.ship_id, []).append(r.phantom_id)
    except Exception as e:
        log_event("ShipInfo", "ContextLoadError",
                  f"flag phantoms failed for cid={commander_id}: {e}", LOG_LEVEL_ERROR)

    try:
        for r in list_owned_ship_shadow_skins(commander_id, ids):
            ctx.shadows.setdefault(r.ship_id, []).append(r)
    except Exception as e:
        log_event("ShipInfo", "ContextLoadError",
                  f"shadow skins failed for cid={commander_id}: {e}", LOG_LEVEL_ERROR)

    try:
        ctx.equips = list_all_owned_ship_equipment(commander_id) or {}
    except Exception as e:
        log_event("ShipInfo", "ContextLoadError",
                  f"equipments failed for cid={commander_id}: {e}", LOG_LEVEL_ERROR)

    try:
        for r in list_all_owned_ship_strengths(commander_id, ids or []):
            ctx.strengths.setdefault(r.ship_id, []).append(r)
    except Exception as e:
        log_event("ShipInfo", "ContextLoadError",
                  f"strengths failed for cid={commander_id}: {e}", LOG_LEVEL_ERROR)

    try:
        ctx.transforms = list_owned_ship_transforms_grouped(commander_id) or {}
    except Exception as e:
        log_event("ShipInfo", "ContextLoadError",
                  f"transforms failed for cid={commander_id}: {e}", LOG_LEVEL_ERROR)

    try:
        from src.orm.tactical_class import list_commander_ship_skills
        for sk in list_commander_ship_skills(commander_id):
            skill_id = int(sk.skill_id or sk.skill_pos or 0)
            if skill_id:
                ctx.skills[(int(sk.ship_id), skill_id)] = sk
    except Exception as e:
        log_event("ShipInfo", "ContextLoadError",
                  f"tactical skills failed for cid={commander_id}: {e}", LOG_LEVEL_ERROR)

    try:
        from src.orm.spweapon import list_owned_sp_weapons_sync
        for spw in list_owned_sp_weapons_sync(commander_id):
            sid = int(spw.get("equipped_ship_id", 0) if isinstance(spw, dict) else getattr(spw, "equipped_ship_id", 0))
            if sid:
                ctx.spweapons[sid] = spw
    except Exception as e:
        log_event("ShipInfo", "ContextLoadError",
                  f"spweapons failed for cid={commander_id}: {e}", LOG_LEVEL_ERROR)

    return ctx


def _ship_field(ship, names, default=None):
    """Read a ship field from an ORM object, a dict, or a tuple row."""
    if isinstance(ship, dict):
        for n in names:
            if n in ship:
                return ship[n]
        return default
    if isinstance(ship, (tuple, list)):
        idx = None
        for n in names:
            if n in _ROW_FIELDS:
                idx = _ROW_FIELDS[n]
                break
        if idx is None or len(ship) <= idx:
            return default
        return ship[idx]
    for n in names:
        v = getattr(ship, n, _MISSING)
        if v is not _MISSING:
            return v
    return default


def _as_ts(value) -> int:
    if hasattr(value, "timestamp"):
        return safe_ts(value)
    return int(value)


def _fill_equip_slots(s, template_id: int, ship_id: int,
                      context: Optional[ShipInfoContext], equip_overrides) -> None:
    from src.orm.game_data import get_ship_equip_config, _get_ship_equip_slot_count

    entries: dict[int, tuple[int, int]] = {}
    if equip_overrides is not None:
        # Explicit slots (e.g. NPC ships): {pos: equip_id | (equip_id, skin_id) | dict}
        for pos, value in equip_overrides.items():
            if isinstance(value, dict):
                entries[int(pos)] = (int(value.get("equip_id") or 0), int(value.get("skin_id") or 0))
            elif isinstance(value, (tuple, list)):
                entries[int(pos)] = (int(value[0] or 0), int(value[1] or 0) if len(value) > 1 else 0)
            else:
                entries[int(pos)] = (int(value or 0), 0)
        max_pos = max(entries) if entries else 0
    else:
        ship_equips = context.equips.get(ship_id, []) if context is not None else []
        for e in ship_equips:
            entries[int(e["pos"])] = (int(e.get("equip_id") or 0), int(e.get("skin_id") or 0))
        # Slot count comes from the ship template config so empty slots are
        # still transmitted (the client renders the slot UI from this list).
        max_pos = _get_ship_equip_slot_count(get_ship_equip_config(template_id))

    for pos in range(1, max_pos + 1):
        ei = protobuf.EQUIPSKIN_INFO()
        equip_id, skin_id = entries.get(pos, (0, 0))
        ei.id = equip_id
        ei.skinId = skin_id
        s.equip_info_list.append(ei)


def build_ship_info(ship, context: Optional[ShipInfoContext] = None, *,
                    char_random_flags=None, equip_overrides=None) -> protobuf.SHIPINFO:
    """Build a complete SHIPINFO for one ship.

    `ship` may be an OwnedShip-like object, a dict (owned_ships_map style;
    `propose` may arrive as `marry_flag`, name as `custom_name` or `name`) or
    a tuple row from `owned_ship.list_ships_by_ids`.

    `char_random_flags` overrides the context's flag phantoms; `equip_overrides`
    replaces the DB equipment with explicit slots ({pos: id|(id, skin)}).
    """
    s = protobuf.SHIPINFO()
    sid = int(_ship_field(ship, ("id",), 0) or 0)
    tid = int(_ship_field(ship, ("ship_id", "template_id"), 0) or 0)
    s.id = sid
    s.template_id = tid
    s.level = int(_ship_field(ship, ("level",), 1) or 1)
    s.exp = int(_ship_field(ship, ("exp",), 0) or 0) + int(_ship_field(ship, ("surplus_exp",), 0) or 0)
    s.energy = int(_ship_field(ship, ("energy",), 0) or 0)
    s.intimacy = int(_ship_field(ship, ("intimacy",), 0) or 0)
    s.skin_id = int(_ship_field(ship, ("skin_id",), 0) or 0)
    s.max_level = int(_ship_field(ship, ("max_level",), 0) or 0)
    s.is_locked = int(bool(_ship_field(ship, ("is_locked",), 0)))
    s.propose = int(bool(_ship_field(ship, ("propose", "marry_flag"), 0)))
    s.common_flag = int(bool(_ship_field(ship, ("common_flag",), 0)))
    s.activity_npc = int(_ship_field(ship, ("activity_npc",), 0) or 0)
    s.proficiency = int(_ship_field(ship, ("proficiency",), 0) or 0)

    ship_state = protobuf.SHIPSTATE(
        state=int(_ship_field(ship, ("state",), 1) or 1),
        state_info_1=int(_ship_field(ship, ("state_info1",), 0) or 0),
        state_info_2=int(_ship_field(ship, ("state_info2",), 0) or 0),
        state_info_3=int(_ship_field(ship, ("state_info3",), 0) or 0),
        state_info_4=int(_ship_field(ship, ("state_info4",), 0) or 0),
    )
    s.state.CopyFrom(ship_state)

    create_time = _ship_field(ship, ("create_time",), None)
    if create_time is not None:
        s.create_time = _as_ts(create_time)
    s.name = str(_ship_field(ship, ("custom_name", "name"), "") or "")
    change_ts = _ship_field(ship, ("change_name_timestamp",), None)
    if change_ts is not None:
        s.change_name_timestamp = _as_ts(change_ts)

    flags = char_random_flags
    if flags is None and context is not None:
        flags = context.flags.get(sid, [])
    if flags:
        s.char_random_flag.extend(flags if isinstance(flags, list) else [flags])

    # Template skills; trained level/exp when the commander studied them.
    from src.orm.game_data import get_ship_skill_ids
    seen_skills = set()
    for skill_id in get_ship_skill_ids(tid):
        sk = protobuf.SHIPSKILL()
        sk.skill_id = skill_id
        seen_skills.add(skill_id)
        owned = context.skills.get((sid, skill_id)) if context is not None else None
        if owned is not None:
            sk.skill_lv = int(owned.level)
            sk.skill_exp = int(owned.exp)
        else:
            sk.skill_lv = 1
            sk.skill_exp = 0
        s.skill_id_list.append(sk)

    # Any additional trained skills on this ship not present in template display
    if context is not None:
        for (cs_sid, cs_skid), owned in context.skills.items():
            if cs_sid == sid and cs_skid not in seen_skills:
                sk = protobuf.SHIPSKILL()
                sk.skill_id = cs_skid
                sk.skill_lv = int(owned.level)
                sk.skill_exp = int(owned.exp)
                s.skill_id_list.append(sk)
                seen_skills.add(cs_skid)

    if context is not None:
        for strength in sorted(context.strengths.get(sid, []),
                               key=lambda x: getattr(x, "strength_id", 0)):
            si = protobuf.STRENGTH_INFO()
            si.id = strength.strength_id
            si.exp = strength.exp
            s.strength_list.append(si)
        for t in sorted(context.transforms.get(sid, []),
                        key=lambda x: getattr(x, "transform_id", 0)):
            ti = protobuf.TRANSFORM_INFO()
            ti.id = t.transform_id
            ti.level = t.level
            s.transform_list.append(ti)
        for shadow in context.shadows.get(sid, []):
            kv = protobuf.KVDATA()
            if isinstance(shadow, dict):
                kv.key = shadow.get("shadow_id", 0)
                kv.value = shadow.get("skin_id", 0)
            else:
                kv.key = shadow.shadow_id
                kv.value = shadow.skin_id
            s.skin_shadow_list.append(kv)

    _fill_equip_slots(s, tid, sid, context, equip_overrides)

    if context is not None:
        spw = context.spweapons.get(sid)
        if spw is not None:
            from src.orm.spweapon import to_proto_owned_sp_weapon
            proto_sp = to_proto_owned_sp_weapon(spw)
            if proto_sp is not None:
                s.spweapon.CopyFrom(proto_sp)

    return s


def build_ship_infos(ships, commander_id: Optional[int] = None,
                     context: Optional[ShipInfoContext] = None, **kwargs) -> list:
    """Build SHIPINFO for many ships, loading the context once."""
    if context is None and commander_id is not None:
        ids = [int(_ship_field(sh, ("id",), 0) or 0) for sh in ships]
        context = load_shipinfo_context(commander_id, [i for i in ids if i])
    return [build_ship_info(sh, context, **kwargs) for sh in ships]
