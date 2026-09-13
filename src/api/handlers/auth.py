from fastapi import Request

from src.api.response import ok, error


class AuthHandler:
    async def bootstrap(self):
        return error("not_implemented", "not implemented")

    async def bootstrap_status(self):
        return ok({"can_bootstrap": False, "admin_count": 0})

    async def login(self, _req: Request):
        return error("not_implemented", "not implemented")

    async def logout(self, _req: Request):
        return ok()

    async def session(self, _req: Request):
        return error("not_implemented", "not implemented")

    async def change_password(self):
        return error("not_implemented", "not implemented")

    async def list_passkeys(self):
        return ok({"passkeys": []})

    async def passkey_register_options(self):
        return error("not_implemented", "not implemented")

    async def passkey_register_verify(self):
        return error("not_implemented", "not implemented")

    async def delete_passkey(self):
        return ok()

    async def passkey_authenticate_options(self):
        return error("not_implemented", "not implemented")

    async def passkey_authenticate_verify(self):
        return error("not_implemented", "not implemented")


_handler = AuthHandler()


def get_auth_handler() -> AuthHandler:
    return _handler
