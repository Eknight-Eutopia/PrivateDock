from fastapi import APIRouter, Depends, Request

from src.api.handlers.user_me import get_me_handler, MeHandler

router = APIRouter(prefix="/api/v1/me", tags=["me"])


@router.get("/commander")
async def me_commander(req: Request, handler: MeHandler = Depends(get_me_handler)):
    return await handler.get_commander(req)


@router.get("/permissions")
async def me_permissions(_req: Request, handler: MeHandler = Depends(get_me_handler)):
    return await handler.get_permissions()
