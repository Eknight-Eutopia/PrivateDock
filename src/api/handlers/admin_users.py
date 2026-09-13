from fastapi import Request

from src.api.response import ok, error


class AdminUserHandler:
    async def list_users(self, offset: int, limit: int):
        return ok({"users": [], "meta": {"offset": offset, "limit": limit, "total": 0}})

    async def get_user(self, _user_id: str):
        return error("not_implemented", "not implemented")

    async def create_user(self, _req: Request):
        return error("not_implemented", "not implemented")

    async def update_user(self, _user_id: str, _req: Request):
        return error("not_implemented", "not implemented")

    async def delete_user(self, _user_id: str):
        return ok()

    async def update_password(self):
        return error("not_implemented", "not implemented")


_handler = AdminUserHandler()


def get_admin_user_handler() -> AdminUserHandler:
    return _handler
