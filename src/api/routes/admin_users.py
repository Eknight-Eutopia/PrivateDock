from fastapi import APIRouter, Depends, Query, Request

from src.api.handlers.admin_users import get_admin_user_handler, AdminUserHandler

router = APIRouter(prefix="/api/v1/admin/users", tags=["admin_users"])


@router.get("")
async def list_users(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    handler: AdminUserHandler = Depends(get_admin_user_handler),
):
    return await handler.list_users(offset, limit)


@router.get("/{user_id}")
async def get_user(user_id: str, handler: AdminUserHandler = Depends(get_admin_user_handler)):
    return await handler.get_user(user_id)


@router.post("")
async def create_user(req: Request, handler: AdminUserHandler = Depends(get_admin_user_handler)):
    return await handler.create_user(req)


@router.patch("/{user_id}")
async def update_user(user_id: str, req: Request, handler: AdminUserHandler = Depends(get_admin_user_handler)):
    return await handler.update_user(user_id, req)


@router.delete("/{user_id}")
async def delete_user(user_id: str, handler: AdminUserHandler = Depends(get_admin_user_handler)):
    return await handler.delete_user(user_id)


@router.post("/{user_id}/password")
async def update_user_password(user_id: str, req: Request, handler: AdminUserHandler = Depends(get_admin_user_handler)):
    return await handler.update_password()
