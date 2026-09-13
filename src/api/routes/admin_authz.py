from fastapi import APIRouter, Depends, Request

from src.api.handlers.admin_authz import get_admin_authz_handler, AdminAuthzHandler

router = APIRouter(prefix="/api/v1/admin/authz", tags=["admin_authz"])


@router.get("/roles")
async def list_roles(handler: AdminAuthzHandler = Depends(get_admin_authz_handler)):
    return await handler.list_roles()


@router.get("/roles/{role}")
async def get_role_policy(role: str, handler: AdminAuthzHandler = Depends(get_admin_authz_handler)):
    return await handler.get_role_policy(role)


@router.put("/roles/{role}")
async def update_role_policy(role: str, req: Request, handler: AdminAuthzHandler = Depends(get_admin_authz_handler)):
    return await handler.update_role_policy(role, req)


@router.get("/permissions")
async def list_permissions(handler: AdminAuthzHandler = Depends(get_admin_authz_handler)):
    return await handler.list_permissions()


@router.get("/accounts/{account_id}/roles")
async def get_account_roles(account_id: str, handler: AdminAuthzHandler = Depends(get_admin_authz_handler)):
    return await handler.get_account_roles(account_id)


@router.put("/accounts/{account_id}/roles")
async def update_account_roles(account_id: str, req: Request, handler: AdminAuthzHandler = Depends(get_admin_authz_handler)):
    return await handler.update_account_roles(account_id, req)


@router.get("/accounts/{account_id}/overrides")
async def get_account_overrides(account_id: str, handler: AdminAuthzHandler = Depends(get_admin_authz_handler)):
    return await handler.get_account_overrides(account_id)


@router.put("/accounts/{account_id}/overrides")
async def update_account_overrides(account_id: str, req: Request, handler: AdminAuthzHandler = Depends(get_admin_authz_handler)):
    return await handler.update_account_overrides(account_id, req)
