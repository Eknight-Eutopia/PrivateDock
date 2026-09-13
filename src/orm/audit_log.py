from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


# ── Dataclass (dataclass) ──
@dataclass
class AuditLog:
    id: str = ""
    actor_account_id: Optional[str] = None
    actor_commander_id: Optional[int] = None
    method: str = ""
    path: str = ""
    status_code: int = 0
    permission_key: Optional[str] = None
    permission_op: Optional[str] = None
    action: Optional[str] = None
    metadata: Optional[bytes] = None
    created_at: Optional[datetime] = None
