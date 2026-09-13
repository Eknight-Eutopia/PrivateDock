from fastapi import APIRouter, Depends, Request

from src.api.handlers.registration import get_registration_handler, RegistrationHandler

router = APIRouter(prefix="/api/v1/registration", tags=["registration"])


@router.post("/challenge")
async def registration_challenge(req: Request, handler: RegistrationHandler = Depends(get_registration_handler)):
    return await handler.challenge(req)


@router.post("/verify")
async def registration_verify(_req: Request, handler: RegistrationHandler = Depends(get_registration_handler)):
    return await handler.verify()


@router.get("/status")
async def registration_status(req: Request, handler: RegistrationHandler = Depends(get_registration_handler)):
    return await handler.status(req)
