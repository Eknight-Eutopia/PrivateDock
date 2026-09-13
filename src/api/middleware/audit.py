import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


def set_audit_action(request: Request, action: str):
    if action:
        request.state.audit_action = action


def add_audit_metadata(request: Request, key: str, value):
    if not key:
        return
    meta = getattr(request.state, "audit_metadata", None)
    if meta is None:
        meta = {}
        request.state.audit_metadata = meta
    meta[key] = value


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        latency_ms = (time.monotonic() - start) * 1000

        account = getattr(request.state, "auth_account", None)
        actor_account_id = account.get("id") if account else None

        action = getattr(request.state, "audit_action", "")
        meta = getattr(request.state, "audit_metadata", {}) or {}
        meta["latency_ms"] = latency_ms

        return response
