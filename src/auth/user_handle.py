import os
from datetime import datetime, timezone

from src.orm.account import Account
from src.db.store import get_default_store


async def ensure_user_handle(account: Account) -> bool:
    if account.web_authn_user_handle and len(account.web_authn_user_handle) > 0:
        return False
    handle = os.urandom(32)
    store = get_default_store()
    await store.aexecute(
        "UPDATE accounts SET web_authn_user_handle = $1, updated_at = $2 WHERE id = $3",
        handle, datetime.now(timezone.utc), account.id,
    )
    account.web_authn_user_handle = handle
    return True
