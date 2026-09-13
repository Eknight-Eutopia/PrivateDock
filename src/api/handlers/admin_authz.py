from fastapi import Request
from fastapi.responses import JSONResponse

from src.api.middleware.auth import get_account
from src.api.response import ok, error
from src.api.types.admin_authz import (
    RoleSummary, RoleListResponse, PermissionSummary, PermissionListResponse,
    PermissionPolicyEntry, RolePolicyResponse, AccountRolesResponse, AccountOverridesResponse,
    AccountOverrideEntry,
)
from src.auth.audit import log_audit
from src.authz import known_permissions
from src.db.store import NotFoundError
from src.orm.authz_store import (
    list_roles as _list_roles,
    list_permissions as _list_permissions,
    load_role_policy_by_name,
    replace_role_policy_by_name,
    get_role_by_name,
    list_account_role_names,
    replace_account_roles_by_name,
    list_account_overrides,
    replace_account_overrides,
    AccountOverrideEntry as ORMAccountOverrideEntry,
)


class AdminAuthzHandler:
    async def list_roles(self):
        roles = await _list_roles()
        resp = [
            RoleSummary(
                name=r.name,
                description=r.description or "",
                updated_at=r.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ") if r.updated_at else "",
                updated_by=r.updated_by or "",
            )
            for r in roles
        ]
        return ok(RoleListResponse(roles=resp).model_dump())

    async def list_permissions(self):
        perms = await _list_permissions()
        resp = [PermissionSummary(key=p.key, description=p.description) for p in perms]
        return ok(PermissionListResponse(permissions=resp).model_dump())

    async def get_role_policy(self, role: str):
        if not role:
            return JSONResponse(error("bad_request", "role required"), status_code=400)
        try:
            policy = await load_role_policy_by_name(role)
        except NotFoundError:
            return JSONResponse(error("not_found", "role not found"), status_code=404)
        known = known_permissions()
        available = sorted(known.keys())
        entries = [
            PermissionPolicyEntry(key=e.key, read_self=e.capability.read_self, read_any=e.capability.read_any, write_self=e.capability.write_self, write_any=e.capability.write_any)
            for e in policy
        ]
        role_obj = None
        try:
            role_obj = await get_role_by_name(role)
        except NotFoundError:
            pass
        updated_at = role_obj.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ") if role_obj and role_obj.updated_at else ""
        updated_by = role_obj.updated_by or ""
        return ok(RolePolicyResponse(role=role, permissions=entries, available_keys=available, updated_at=updated_at, updated_by=updated_by).model_dump())

    async def update_role_policy(self, role: str, req: Request):
        if not role:
            return JSONResponse(error("bad_request", "role required"), status_code=400)
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
        try:
            await replace_role_policy_by_name(role, caps, updated_by)
        except NotFoundError:
            return JSONResponse(error("not_found", "role not found"), status_code=404)
        if updated_by:
            await log_audit("authz.role_policy.replace", updated_by, None, {"role": role})
        return await self.get_role_policy(role)

    async def get_account_roles(self, account_id: str):
        roles = await list_account_role_names(account_id)
        return ok(AccountRolesResponse(account_id=account_id, roles=roles).model_dump())

    async def update_account_roles(self, account_id: str, req: Request):
        body = await req.json()
        role_names = body.get("roles")
        if role_names is None:
            return JSONResponse(error("bad_request", "roles required"), status_code=400)
        updated_by = None
        acct = get_account(req)
        if acct:
            updated_by = acct.get("id")
        await replace_account_roles_by_name(account_id, role_names)
        if updated_by:
            await log_audit("authz.account_roles.replace", updated_by, account_id, {"count": len(role_names)})
        roles = await list_account_role_names(account_id)
        return ok(AccountRolesResponse(account_id=account_id, roles=roles).model_dump())

    async def get_account_overrides(self, account_id: str):
        rows = await list_account_overrides(account_id)
        overrides = [
            AccountOverrideEntry(key=r.key, mode=r.mode, read_self=r.capability.read_self, read_any=r.capability.read_any, write_self=r.capability.write_self, write_any=r.capability.write_any)
            for r in rows
        ]
        return ok(AccountOverridesResponse(account_id=account_id, overrides=overrides).model_dump())

    async def update_account_overrides(self, account_id: str, req: Request):
        body = await req.json()
        overrides_data = body.get("overrides")
        if overrides_data is None:
            return JSONResponse(error("bad_request", "overrides required"), status_code=400)
        entries = []
        for ov in overrides_data:
            mode = (ov.get("mode") or "").strip().lower()
            if not mode:
                mode = "allow"
            entries.append(ORMAccountOverrideEntry(
                key=(ov.get("key") or "").strip(),
                mode=mode,
                capability=type("Cap", (), {
                    "read_self": ov.get("read_self", False),
                    "read_any": ov.get("read_any", False),
                    "write_self": ov.get("write_self", False),
                    "write_any": ov.get("write_any", False),
                })(),
            ))
        updated_by = None
        acct = get_account(req)
        if acct:
            updated_by = acct.get("id")
        await replace_account_overrides(account_id, entries)
        if updated_by:
            await log_audit("authz.account_overrides.replace", updated_by, account_id, {"count": len(entries)})
        return await self.get_account_overrides(account_id)


_handler = AdminAuthzHandler()


def get_admin_authz_handler() -> AdminAuthzHandler:
    return _handler
