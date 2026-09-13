from datetime import datetime, timezone

from fastapi import APIRouter

from src.api.response import ok

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    return ok({"status": "ok", "time": datetime.now(timezone.utc).isoformat()})
