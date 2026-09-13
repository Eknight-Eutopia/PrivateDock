from __future__ import annotations
from dataclasses import dataclass


# ── Dataclass (dataclass) ──
@dataclass
class OwnedShipShadowSkin:
    commander_id: int = 0
    ship_id: int = 0
    shadow_id: int = 0
    skin_id: int = 0

# ── SQLAlchemy model ──
