from fastapi import Request

from src.api.response import ok, error


class ExchangeCodeHandler:
    async def list_codes(self, offset: int, limit: int):
        return ok({"codes": [], "meta": {"offset": offset, "limit": limit, "total": 0}})

    async def create_code(self):
        return error("not_implemented", "not implemented")

    async def get_code(self):
        return error("not_implemented", "not implemented")

    async def update_code(self):
        return error("not_implemented", "not implemented")

    async def delete_code(self):
        return ok()

    async def list_redeems(self, offset: int, limit: int):
        return ok({"redeems": [], "meta": {"offset": offset, "limit": limit, "total": 0}})

    async def redeem_code(self, _code_id: int, _req: Request):
        return error("not_implemented", "not implemented")


_handler = ExchangeCodeHandler()


def get_exchange_code_handler() -> ExchangeCodeHandler:
    return _handler
