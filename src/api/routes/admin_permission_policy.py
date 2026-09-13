from fastapi import APIRouter, Depends, Request

from src.api.handlers.admin_permission_policy import get_admin_permission_policy_handler, AdminPermissionPolicyHandler

router = APIRouter(prefix="/api/v1/admin/permission-policy", tags=["admin_permission_policy"])


@router.get("")
async def get_permission_policy(handler: AdminPermissionPolicyHandler = Depends(get_admin_permission_policy_handler)):
    return await handler.get()


@router.patch("")
async def update_permission_policy(req: Request, handler: AdminPermissionPolicyHandler = Depends(get_admin_permission_policy_handler)):
    return await handler.update(req)
