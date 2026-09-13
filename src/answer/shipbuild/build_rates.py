import random
from typing import List, Optional, Set, Tuple

# Base rarity drop rates (percent), keyed by rarity_id.
# Azur Lane rarity_id: 2=Common, 3=Rare, 4=Elite, 5=SR, 6=UR.
# Base Construction: 1.2% UR (when the pool has a UR ship), 7% SR, 12% Elite,
# 51% Rare, 28.8% Common. When a pool contains no UR ship, its 1.2% share is
# folded into Common (-> 30%), matching the official client behaviour.
RARITY_BASE_RATE = {6: 1.2, 5: 7.0, 4: 12.0, 3: 51.0, 2: 28.8}

# Per-ship rate-up share (percent) granted to a focus (rate-up) ship of that rarity.
# Event / Wishing Well construction: each selected rate-up ship draws this fixed
# share; the remaining ships of that rarity share what is left of the rarity total.
# SR #1/#2 get 2% each, SR #3 0.5% (we treat every focus SR uniformly at 2%,
# which is the wiki's per-featured-ship rate). Wishing Well is the only construction
# that allows rate-ups on Rare/Common ships, at 2.5% each.
RARITY_RATEUP_RATE = {6: 1.2, 5: 2.0, 4: 2.5, 3: 2.5, 2: 2.5}


def rarity_weights(
    ships: List[Tuple[int, int]],
    focus: Optional[Set[int]] = None,
    mode: str = "base",
) -> List[float]:
    """Compute draw weights for `ships` (list of (ship_id, rarity_id)).

    mode="base"  -> each ship weighted by its rarity's base rate, uniform within rarity.
    mode="event" -> focus ships get a fixed rate-up share; the other ships of that
                    rarity share the remainder of the rarity's base rate.
    """
    focus = focus or set()
    by_rarity: dict = {}
    for sid, r in ships:
        by_rarity.setdefault(r, []).append(sid)

    present = set(by_rarity.keys())
    base = dict(RARITY_BASE_RATE)
    # Redistribute the rate of any rarity absent from this pool to Common (rarity 2),
    # or to the lowest present rarity when Common is also absent.
    for r in list(base.keys()):
        if r not in present:
            add = base.pop(r)
            target = 2 if 2 in present else (min(present) if present else 2)
            base[target] = base.get(target, 0.0) + add

    weights = [0.0] * len(ships)
    for idx, (sid, r) in enumerate(ships):
        total_r = base.get(r, 0.0)
        if total_r <= 0:
            continue
        group = by_rarity[r]
        focus_in_group = [s for s in group if s in focus]
        if mode == "base" or not focus_in_group:
            weights[idx] = total_r / len(group)
            continue
        rateup = RARITY_RATEUP_RATE.get(r, 0.0)
        focus_count = len(focus_in_group)
        focus_rate = min(rateup * focus_count, total_r)
        others = [s for s in group if s not in focus]
        if focus_rate < rateup * focus_count:
            per_focus = focus_rate / focus_count
        else:
            per_focus = rateup
        per_other = (total_r - focus_rate) / len(others) if others else 0.0
        weights[idx] = per_focus if sid in focus else per_other
    return weights


def draw_ship(
    ships: List[Tuple[int, int]],
    focus: Optional[Set[int]] = None,
    mode: str = "base",
) -> Optional[int]:
    """Pick one ship_id from `ships` using the wiki rarity rates."""
    if not ships:
        return None
    weights = rarity_weights(ships, focus, mode)
    total = sum(weights)
    if total <= 0:
        return ships[0][0]
    return random.choices(ships, weights=weights, k=1)[0][0]
