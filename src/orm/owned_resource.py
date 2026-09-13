from __future__ import annotations
from dataclasses import dataclass


# ── Dataclass (dataclass) ──
@dataclass
class OwnedResource:
    commander_id: int = 0
    resource_id: int = 0
    count: int = 0

# ── SQLAlchemy model ──
