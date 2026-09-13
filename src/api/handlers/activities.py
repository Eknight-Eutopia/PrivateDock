from fastapi import Request

from src.api.response import ok, error


class ActivityHandler:
    async def get_allowlist(self):
        return ok({"ids": []})

    async def set_allowlist(self, _req: Request):
        return error("not_implemented", "not implemented")

    async def patch_allowlist(self, _req: Request):
        return error("not_implemented", "not implemented")


_handler = ActivityHandler()


def get_activity_handler() -> ActivityHandler:
    return _handler
