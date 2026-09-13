from fastapi import Request, HTTPException

from src.api.middleware.auth import get_account, is_auth_disabled
from src.api.response import error
from src.authz import Capability, Operation, operation_for_method


_authz_cache_key = "authz.effective"


async def effective_permissions(request: Request):
    cached = getattr(request.state, _authz_cache_key, None)
    if cached is not None:
        return cached
    account = get_account(request)
    if account is None:
        return {}
    from src.orm.authz_store import load_effective_permissions
    perms = await load_effective_permissions(account["id"])
    setattr(request.state, _authz_cache_key, perms)
    return perms


async def require_permission(request: Request, key: str, op: Operation):
    setattr(request.state, "authz.key", key)
    setattr(request.state, "authz.op", op.value)
    if is_auth_disabled(request):
        return
    account = get_account(request)
    if account is None:
        raise HTTPException(status_code=401, detail=error("auth.session_missing", "session required"))
    perms = await effective_permissions(request)
    cap = perms.get(key, Capability())
    if not cap.allowed(op):
        raise HTTPException(status_code=403, detail=error("permissions.denied", "permission denied"))


async def require_permission_any(key: str):
    async def _inner(request: Request):
        op = operation_for_method(request.method, Operation.ReadAny, Operation.WriteAny)
        await require_permission(request, key, op)
    return _inner


async def require_permission_self(key: str):
    async def _inner(request: Request):
        op = operation_for_method(request.method, Operation.ReadSelf, Operation.WriteSelf)
        await require_permission(request, key, op)
    return _inner


async def require_permission_for_method(key: str, read_op: Operation, write_op: Operation):
    async def _inner(request: Request):
        if request.method == "OPTIONS":
            return
        op = operation_for_method(request.method, read_op, write_op)
        await require_permission(request, key, op)
    return _inner


async def require_permission_any_or_self(key: str):
    async def _inner(request: Request):
        setattr(request.state, "authz.key", key)
        if request.method == "OPTIONS":
            return
        if is_auth_disabled(request):
            return
        account = get_account(request)
        if account is None:
            raise HTTPException(status_code=401, detail=error("auth.session_missing", "session required"))
        perms = await effective_permissions(request)
        cap = perms.get(key, Capability())

        id_param = request.path_params.get("player_id") or request.path_params.get("id")
        is_self = False
        if id_param and account.get("commander_id"):
            try:
                parsed = int(id_param)
                is_self = parsed == account["commander_id"]
            except (ValueError, TypeError):
                pass

        op = operation_for_method(request.method, Operation.ReadSelf, Operation.WriteSelf) if is_self else operation_for_method(request.method, Operation.ReadAny, Operation.WriteAny)
        setattr(request.state, "authz.op", op.value)

        if not cap.allowed(op):
            raise HTTPException(status_code=403, detail=error("permissions.denied", "permission denied"))
    return _inner
