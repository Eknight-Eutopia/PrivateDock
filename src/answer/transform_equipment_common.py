"""Shared helpers for the Equipment Transform (Gear Lab) handlers.

Gear Lab is the *Equipment Transform* tab inside Technology: a weaker weapon
plus resources turns into a better one. The client drives it with

    CS_14015 { equip_id, upgrade_id }      -- source in the bag
    CS_14013 { ship_id, pos, upgrade_id }  -- source equipped on a ship
    -> SC_14016 / SC_14014 { result }

(``view/equipment/transformation/equipmenttransformutil.lua`` and
``controller/command/equipment/transformequipmentcommand.lua``). ``upgrade_id``
is the ``equip_upgrade_data`` formula id, not an equipment id.

Per step the client validates and applies exactly what
``EquipmentTransformUtil.CheckTransformFormulasSucceed`` computes::

    equip_upgrade_data[upgrade_id].upgrade_from == GetEquipRootStatic(source)
    gold  : -coin_consume + destroy_gold(source) + GetRevertRewardsStatic(source).gold
    items : -material_consume + GetRevertRewardsStatic(source)

then replaces ``source`` with ``equip_upgrade_data[upgrade_id].target_id``.
The helpers below mirror the two ``Equipment.*Static`` functions from
``model/vo/equipment.lua`` so the server and the client agree on the numbers.
"""

from __future__ import annotations

from typing import Any, Optional

from src.answer.trans_use import add_trans_use_items


def _equip_row(equip_id: int, cache: dict) -> Optional[Any]:
    """``equip_data_template`` row (``src.orm.equipment.Equipment``), memoised
    per request. ``None`` is cached too, so a missing id costs one query."""
    if not equip_id:
        return None
    if equip_id not in cache:
        from src.orm.equipment import get_equipment_by_id
        try:
            cache[equip_id] = get_equipment_by_id(equip_id)
        except Exception:
            cache[equip_id] = None
    return cache[equip_id]


def _field(row, name: str, default=0):
    if row is None:
        return default
    if isinstance(row, dict):
        value = row.get(name, default)
    else:
        value = getattr(row, name, default)
    return default if value is None else value


def equip_root(equip_id: int, cache: Optional[dict] = None) -> int:
    """Client ``Equipment.GetEquipRootStatic``: follow ``prev`` to the base."""
    cache = {} if cache is None else cache
    original = int(equip_id or 0)
    current = original
    seen: set[int] = set()
    while current and current not in seen:
        seen.add(current)
        row = _equip_row(current, cache)
        if row is None:
            return original
        prev = int(_field(row, "prev", 0) or 0)
        if prev <= 0:
            return current
        current = prev
    return original


def destroy_gold(equip_id: int, cache: Optional[dict] = None) -> int:
    """Scrap value the client credits back when the source is consumed."""
    row = _equip_row(int(equip_id or 0), {} if cache is None else cache)
    return int(_field(row, "destroy_gold", 0) or 0)


def revert_rewards(equip_id: int, cache: Optional[dict] = None) -> tuple[dict[int, int], int]:
    """Client ``Equipment.GetRevertRewardsStatic`` -> ``(items, gold)``.

    Walks the ``prev`` chain refunding, at every hop, the *previous* node's
    ``trans_use_item`` and the *current* node's ``trans_use_gold``. That
    asymmetry is the client's own (``model/vo/equipment.lua``); mirrored
    verbatim so the two sides agree on the totals.
    """
    cache = {} if cache is None else cache
    items: dict[int, int] = {}
    gold = 0
    current = int(equip_id or 0)
    seen: set[int] = set()
    while current and current not in seen:
        seen.add(current)
        row = _equip_row(current, cache)
        if row is None:
            break
        prev = int(_field(row, "prev", 0) or 0)
        if prev <= 0:
            break
        prev_row = _equip_row(prev, cache)
        if prev_row is None:
            break
        add_trans_use_items(items, _field(prev_row, "trans_use_item", None))
        gold += int(_field(row, "trans_use_gold", 0) or 0)
        current = prev
    return items, gold


def get_formula(upgrade_id: int) -> Optional[dict]:
    """``equip_upgrade_data[upgrade_id]`` (``upgrade_from`` / ``target_id`` /
    ``coin_consume`` / ``material_consume``) or ``None`` when unknown."""
    from src.orm.game_data import get_equip_upgrade_data
    data = get_equip_upgrade_data(int(upgrade_id or 0))
    return data if isinstance(data, dict) else None


def formula_materials(formula: dict) -> dict[int, int]:
    """``material_consume`` (``[[item_id, count], ...]``) as a flat mapping."""
    costs: dict[int, int] = {}
    add_trans_use_items(costs, formula.get("material_consume"))
    return costs


def build_plan(client, formula: dict, source_id: int, cache: Optional[dict] = None) -> Optional[dict]:
    """Net-cost plan for one transform step, or ``None`` when unaffordable.

    Mirrors ``CheckTransformFormulasSucceed``, which nets the refunds against
    the costs before deciding, so the server accepts exactly what the client
    pre-validated.
    """
    target_id = int(formula.get("target_id", 0) or 0)
    if target_id == 0:
        return None

    cache = {} if cache is None else cache
    item_costs = formula_materials(formula)
    item_refunds, refund_gold = revert_rewards(source_id, cache)
    gold_cost = int(formula.get("coin_consume", 0) or 0)
    gold_refund = destroy_gold(source_id, cache) + refund_gold

    commander = client.commander
    if commander.get_resource_count(1) + gold_refund < gold_cost:
        return None
    for item_id, count in item_costs.items():
        if commander.get_item_count(item_id) + item_refunds.get(item_id, 0) < count:
            return None

    return {
        "target_id": target_id,
        "gold_cost": gold_cost,
        "gold_refund": gold_refund,
        "item_costs": item_costs,
        "item_refunds": item_refunds,
    }


def apply_plan(client, plan: dict) -> None:
    """Charge the net gold/items of ``plan`` (refunds netted against costs)."""
    commander = client.commander

    net_gold = plan["gold_refund"] - plan["gold_cost"]
    if net_gold > 0:
        commander.add_resource(1, net_gold)
    elif net_gold < 0:
        commander.consume_resource(1, -net_gold)

    for item_id, count in plan["item_costs"].items():
        delta = plan["item_refunds"].get(item_id, 0) - count
        if delta > 0:
            commander.add_item(item_id, delta)
        elif delta < 0:
            commander.consume_item(item_id, -delta)
            adjust_item_map(client, item_id, delta)
    for item_id, refund in plan["item_refunds"].items():
        if refund <= 0 or item_id in plan["item_costs"]:
            continue
        commander.add_item(item_id, refund)


def undo_plan(client, plan: dict) -> None:
    """Best-effort reversal of :func:`apply_plan`.

    Called when a step *after* the resource/equipment charge fails, so a
    commander never ends up paying for a transform that did not happen. Never
    raises -- the caller is already handling the original error.
    """
    try:
        commander = client.commander

        net_gold = plan["gold_refund"] - plan["gold_cost"]
        if net_gold > 0:
            commander.consume_resource(1, net_gold)
        elif net_gold < 0:
            commander.add_resource(1, -net_gold)

        for item_id, count in plan["item_costs"].items():
            delta = plan["item_refunds"].get(item_id, 0) - count
            if delta > 0:
                commander.consume_item(item_id, delta)
                adjust_item_map(client, item_id, -delta)
            elif delta < 0:
                commander.add_item(item_id, -delta)
        for item_id, refund in plan["item_refunds"].items():
            if refund > 0 and item_id not in plan["item_costs"]:
                commander.consume_item(item_id, refund)
                adjust_item_map(client, item_id, -refund)
    except Exception:
        pass


def adjust_item_map(client, item_id: int, delta: int) -> None:
    """``consume_item()`` leaves the live ``commander_items_map`` untouched, but
    SC_15001 (the client's Item tab) is built from it -- keep them in sync."""
    mapping = getattr(client.commander, "commander_items_map", None)
    if not isinstance(mapping, dict):
        return
    entry = mapping.get(item_id)
    if not isinstance(entry, dict):
        return
    new_count = int(entry.get("count", 0) or 0) + delta
    if new_count <= 0:
        mapping.pop(item_id, None)
    else:
        entry["count"] = new_count


def adjust_equipment_map(client, equip_id: int, delta: int) -> None:
    """``remove_owned_equipment()`` leaves the live ``owned_equipment_map``
    untouched, but SC_14001 (the equipment bag) is built from it."""
    mapping = getattr(client.commander, "owned_equipment_map", None)
    if not isinstance(mapping, dict):
        return
    entry = mapping.get(equip_id)
    if not isinstance(entry, dict):
        return
    new_count = int(entry.get("count", 0) or 0) + delta
    if new_count <= 0:
        mapping.pop(equip_id, None)
    else:
        entry["count"] = new_count


def ensure_equipment_in_map(client, equip_id: int, count: int = 1) -> None:
    """``add_owned_equipment()`` already bumps the live map; this only makes
    sure the entry exists (no double count), so a fresh grant shows up in the
    bag even when no active commander happened to be registered."""
    mapping = getattr(client.commander, "owned_equipment_map", None)
    if not isinstance(mapping, dict) or equip_id in mapping:
        return
    mapping[equip_id] = {
        "commander_id": client.commander.commander_id,
        "equipment_id": equip_id,
        "count": count,
    }
