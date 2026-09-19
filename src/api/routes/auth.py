from fastapi import APIRouter, Depends, Request

from src.api.handlers.auth import get_auth_handler, AuthHandler

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/bootstrap")
async def auth_bootstrap(req: Request, handler: AuthHandler = Depends(get_auth_handler)):
    return await handler.bootstrap(req)


@router.get("/bootstrap/status")
async def auth_bootstrap_status(handler: AuthHandler = Depends(get_auth_handler)):
    return await handler.bootstrap_status()


@router.post("/login")
async def auth_login(req: Request, handler: AuthHandler = Depends(get_auth_handler)):
    return await handler.login(req)


@router.post("/logout")
async def auth_logout(req: Request, handler: AuthHandler = Depends(get_auth_handler)):
    return await handler.logout(req)


@router.get("/session")
async def auth_session(req: Request, handler: AuthHandler = Depends(get_auth_handler)):
    return await handler.session(req)


@router.post("/password")
async def auth_change_password(req: Request, handler: AuthHandler = Depends(get_auth_handler)):
    return await handler.change_password(req)


@router.get("/passkeys")
async def auth_list_passkeys(_req: Request, handler: AuthHandler = Depends(get_auth_handler)):
    return await handler.list_passkeys()


@router.post("/passkeys/register/options")
async def auth_passkey_register_options(_req: Request, handler: AuthHandler = Depends(get_auth_handler)):
    return await handler.passkey_register_options()


@router.post("/passkeys/register/verify")
async def auth_passkey_register_verify(_req: Request, handler: AuthHandler = Depends(get_auth_handler)):
    return await handler.passkey_register_verify()


@router.delete("/passkeys/{credential_id}")
async def auth_delete_passkey(credential_id: str, req: Request, handler: AuthHandler = Depends(get_auth_handler)):
    return await handler.delete_passkey()


@router.post("/passkeys/authenticate/options")
async def auth_passkey_authenticate_options(_req: Request, handler: AuthHandler = Depends(get_auth_handler)):
    return await handler.passkey_authenticate_options()


@router.post("/passkeys/authenticate/verify")
async def auth_passkey_authenticate_verify(_req: Request, handler: AuthHandler = Depends(get_auth_handler)):
    return await handler.passkey_authenticate_verify()
