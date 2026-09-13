from fastapi import Request

from src.api.response import ok, error


class RegistrationHandler:
    async def challenge(self, _req: Request):
        return error("not_implemented", "not implemented")

    async def verify(self):
        return error("not_implemented", "not implemented")

    async def status(self, _req: Request):
        return ok({"status": "ok"})


_handler = RegistrationHandler()


def get_registration_handler() -> RegistrationHandler:
    return _handler
