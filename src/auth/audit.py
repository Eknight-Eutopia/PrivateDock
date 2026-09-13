import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from src.db.store import get_default_store


async def log_audit(action: str, actor_user_id: Optional[str] = None, target_user_id: Optional[str] = None, metadata: Optional[dict] = None):
    if metadata is None:
        metadata = {}
    if target_user_id:
        metadata["target_account_id"] = target_user_id
    try:
        store = get_default_store()
        if store is None:
            return
        metadata_bytes = json.dumps(metadata).encode("utf-8") if metadata else None
        await store.aexecute(
            "INSERT INTO audit_logs (id, actor_account_id, method, path, status_code, action, metadata, created_at) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
            str(uuid.uuid4()), actor_user_id, "EVENT", "/", 0, action, metadata_bytes, datetime.now(timezone.utc),
        )
    except Exception:
        pass


async def log_user_audit(action: str, actor_user_id: Optional[str] = None, target_commander_id: Optional[int] = None, metadata: Optional[dict] = None):
    if metadata is None:
        metadata = {}
    if target_commander_id is not None:
        metadata["target_commander_id"] = target_commander_id
    try:
        store = get_default_store()
        if store is None:
            return
        metadata_bytes = json.dumps(metadata).encode("utf-8") if metadata else None
        await store.aexecute(
            "INSERT INTO audit_logs (id, actor_account_id, method, path, status_code, action, metadata, created_at) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
            str(uuid.uuid4()), actor_user_id, "EVENT", "/", 0, action, metadata_bytes, datetime.now(timezone.utc),
        )
    except Exception:
        pass
