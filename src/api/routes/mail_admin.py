from fastapi import APIRouter, Depends, Request

from src.api.middleware.permissions import require_admin
from src.api.handlers.mail_admin import search_catalog, search_target_players, send_target_mail


router = APIRouter(
    prefix="/api/v1/mail-admin",
    tags=["mail-admin"],
    dependencies=[Depends(require_admin)],
)


@router.get("/players/search")
async def search_players_route(request: Request):
    return await search_target_players(request)


@router.get("/catalog")
async def catalog_route(request: Request):
    return await search_catalog(request)


@router.post("/send")
async def send_mail_route(request: Request):
    return await send_target_mail(request)
