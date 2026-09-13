from fastapi import Request

from src.api.response import ok, error


class MeHandler:
    async def get_commander(self, _req: Request):
        return error("not_implemented", "not implemented")

    async def get_permissions(self):
        return ok({"roles": [], "permissions": []})


_handler = MeHandler()


def get_me_handler() -> MeHandler:
    return _handler
