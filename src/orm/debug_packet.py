from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


# ── Dataclass (dataclass) ──
@dataclass
class DebugPacket:
    id: int = 0
    packet_id: int = 0
    payload: Optional[bytes] = None
    created_at: Optional[datetime] = None
