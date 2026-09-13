from fastapi import Request

from src.api.response import ok, error


class UserAuthHandler:
    async def login(self, _req: Request):
        return error("not_implemented", "not implemented")

    async def logout(self, _req: Request):
        return ok()

    async def session(self, _req: Request):
        return error("not_implemented", "not implemented")


_handler = UserAuthHandler()


def get_user_auth_handler() -> UserAuthHandler:
    return _handler
