from fastapi import APIRouter, Depends, Query, Request

from src.api.handlers.exchange_codes import get_exchange_code_handler, ExchangeCodeHandler

router = APIRouter(prefix="/api/v1/exchange-codes", tags=["exchange_codes"])


@router.get("")
async def list_exchange_codes(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    handler: ExchangeCodeHandler = Depends(get_exchange_code_handler),
):
    return await handler.list_codes(offset, limit)


@router.post("")
async def create_exchange_code(_req: Request, handler: ExchangeCodeHandler = Depends(get_exchange_code_handler)):
    return await handler.create_code()


@router.get("/{code_id}")
async def get_exchange_code(code_id: int, handler: ExchangeCodeHandler = Depends(get_exchange_code_handler)):
    return await handler.get_code()


@router.put("/{code_id}")
async def update_exchange_code(code_id: int, req: Request, handler: ExchangeCodeHandler = Depends(get_exchange_code_handler)):
    return await handler.update_code()


@router.delete("/{code_id}")
async def delete_exchange_code(code_id: int, handler: ExchangeCodeHandler = Depends(get_exchange_code_handler)):
    return await handler.delete_code()


@router.get("/{code_id}/redeems")
async def list_code_redeems(
    code_id: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    handler: ExchangeCodeHandler = Depends(get_exchange_code_handler),
):
    return await handler.list_redeems(offset, limit)


@router.post("/{code_id}/redeem")
async def redeem_code(code_id: int, req: Request, handler: ExchangeCodeHandler = Depends(get_exchange_code_handler)):
    return await handler.redeem_code(code_id, req)
