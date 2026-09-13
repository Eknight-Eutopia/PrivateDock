import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from src.config.config import current
from src.auth.password import hash_password
from src.auth.config import normalize_user_config
from src.logger.logger import log_event, LOG_LEVEL_ERROR

from .helpers import (
    is_numeric_only,
    next_local_arg2,
    get_local_account_by_account,
    create_local_account,
)

REGISTER_RESULT_OK = 0
REGISTER_RESULT_INVALID_ACCOUNT = 1010
REGISTER_RESULT_ACCOUNT_EXISTS = 1011
REGISTER_RESULT_NUMERIC_ACCOUNT = 1012
REGISTER_RESULT_DATABASE_ERROR = 11


def handle_register_account(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_10001()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 10002, e

    response = protobuf.SC_10002()
    response.result = REGISTER_RESULT_OK

    account = payload.account.strip()
    if not account:
        response.result = REGISTER_RESULT_INVALID_ACCOUNT
        asyncio.create_task(client.send_message(10002, response))
        return 0, 10002, None

    if is_numeric_only(account):
        response.result = REGISTER_RESULT_NUMERIC_ACCOUNT
        asyncio.create_task(client.send_message(10002, response))
        return 0, 10002, None

    existing = get_local_account_by_account(account)
    if existing is not None:
        response.result = REGISTER_RESULT_ACCOUNT_EXISTS
        asyncio.create_task(client.send_message(10002, response))
        return 0, 10002, None

    try:
        arg2 = next_local_arg2()
    except RuntimeError as e:
        log_event("Server", "SC_10002", f"failed to allocate arg2: {e}", LOG_LEVEL_ERROR)
        response.result = REGISTER_RESULT_DATABASE_ERROR
        asyncio.create_task(client.send_message(10002, response))
        return 0, 10002, None

    auth_config = normalize_user_config(current().auth)
    auth_config.password_min_length = 1

    try:
        password_hash_str = hash_password(payload.password)
    except Exception as e:
        log_event("Server", "SC_10002", f"failed to hash password: {e}", LOG_LEVEL_ERROR)
        response.result = REGISTER_RESULT_DATABASE_ERROR
        asyncio.create_task(client.send_message(10002, response))
        return 0, 10002, None

    try:
        create_local_account(arg2, account, password_hash_str, payload.mail_box)
    except Exception as e:
        log_event("Server", "SC_10002", f"failed to create account: {e}", LOG_LEVEL_ERROR)
        response.result = REGISTER_RESULT_DATABASE_ERROR
        asyncio.create_task(client.send_message(10002, response))
        return 0, 10002, None

    asyncio.create_task(client.send_message(10002, response))
    return 0, 10002, None
