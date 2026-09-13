from fastapi import APIRouter, Depends, Request

from src.api.handlers.user_auth import get_user_auth_handler, UserAuthHandler

router = APIRouter(prefix="/api/v1/user/auth", tags=["user_auth"])


@router.post("/login")
async def user_auth_login(req: Request, handler: UserAuthHandler = Depends(get_user_auth_handler)):
    return await handler.login(req)


@router.post("/logout")
async def user_auth_logout(req: Request, handler: UserAuthHandler = Depends(get_user_auth_handler)):
    return await handler.logout(req)


@router.get("/session")
async def user_auth_session(req: Request, handler: UserAuthHandler = Depends(get_user_auth_handler)):
    return await handler.session(req)
