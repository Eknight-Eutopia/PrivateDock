from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


# ── Dataclass (dataclass) ──
@dataclass
class MonthShopPurchase:
    commander_id: int = 0
    goods_id: int = 0
    month: int = 0
    buy_count: int = 0
    updated_at: Optional[datetime] = None

# ── SQLAlchemy model ──
