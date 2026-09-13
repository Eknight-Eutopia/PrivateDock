from fastapi import APIRouter, Depends, Request

from src.api.handlers.activities import get_activity_handler, ActivityHandler

router = APIRouter(prefix="/api/v1/activities", tags=["activities"])


@router.get("/allowlist")
async def get_allowlist(handler: ActivityHandler = Depends(get_activity_handler)):
    return await handler.get_allowlist()


@router.put("/allowlist")
async def set_allowlist(req: Request, handler: ActivityHandler = Depends(get_activity_handler)):
    return await handler.set_allowlist(req)


@router.patch("/allowlist")
async def patch_allowlist(req: Request, handler: ActivityHandler = Depends(get_activity_handler)):
    return await handler.patch_allowlist(req)
