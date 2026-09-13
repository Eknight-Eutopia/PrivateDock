from fastapi import Request
from fastapi.responses import JSONResponse

from src.api.middleware.auth import get_account
from src.api.response import ok, error
from src.api.types.user_permissions import UserPermissionPolicyResponse
from src.api.types.admin_authz import PermissionPolicyEntry
from src.auth.audit import log_audit
from src.authz import known_permissions
from src.authz.keys import RolePlayer
from src.orm.authz_store import load_role_policy_by_name, replace_role_policy_by_name, get_role_by_name


class AdminPermissionPolicyHandler:
    async def get(self):
        policy = await load_role_policy_by_name(RolePlayer)
        known = known_permissions()
        available = sorted(known.keys())
        entries = [
            PermissionPolicyEntry(key=e.key, read_self=e.capability.read_self, read_any=e.capability.read_any, write_self=e.capability.write_self, write_any=e.capability.write_any)
            for e in policy
        ]
        role = None
        try:
            role = await get_role_by_name(RolePlayer)
        except Exception:
            pass
        updated_at = role.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ") if role and role.updated_at else ""
        updated_by = role.updated_by or ""
        return ok(UserPermissionPolicyResponse(role=RolePlayer, permissions=entries, available_keys=available, updated_at=updated_at, updated_by=updated_by).model_dump())

    async def update(self, req: Request):
        body = await req.json()
        perms_data = body.get("permissions")
        if perms_data is None:
            return JSONResponse(error("bad_request", "permissions required"), status_code=400)
        known = known_permissions()
        seen: set[str] = set()
        caps = {}
        for entry in perms_data:
            key = (entry.get("key") or "").strip()
            if not key:
                return JSONResponse(error("bad_request", "permission key required"), status_code=400)
            if key not in known:
                return JSONResponse(error("bad_request", "unknown permission key", {"key": key}), status_code=400)
            if key in seen:
                return JSONResponse(error("bad_request", "duplicate permission key", {"key": key}), status_code=400)
            seen.add(key)
            caps[key] = type("Cap", (), {
                "read_self": entry.get("read_self", False),
                "read_any": entry.get("read_any", False),
                "write_self": entry.get("write_self", False),
                "write_any": entry.get("write_any", False),
            })()
        updated_by = None
        acct = get_account(req)
        if acct:
            updated_by = acct.get("id")
        await replace_role_policy_by_name(RolePlayer, caps, updated_by)
        if updated_by:
            await log_audit("permissions.update", updated_by, None, {"role": RolePlayer})
        return await self.get()


_handler = AdminPermissionPolicyHandler()


def get_admin_permission_policy_handler() -> AdminPermissionPolicyHandler:
    return _handler
