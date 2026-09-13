import random
from typing import Optional

from src.db.store import get_default_store

_local_account_rand = random.Random()


def is_numeric_only(value: str) -> bool:
    if not value:
        return False
    for ch in value:
        if ch < '0' or ch > '9':
            return False
    return True


def local_arg2_exists(value: int) -> bool:
    store = get_default_store()
    row = store.fetchrow(
        "SELECT 1 FROM local_accounts WHERE arg2 = $1",
        value
    )
    return row is not None


def next_local_arg2() -> int:
    max_attempts = 10
    for _ in range(max_attempts):
        candidate = _local_account_rand.randint(1, 0xFFFFFFFF)
        if not local_arg2_exists(candidate):
            return candidate
    raise RuntimeError("exhausted arg2 candidates")


def get_local_account_by_account(account: str) -> Optional[dict]:
    store = get_default_store()
    row = store.fetchrow(
        "SELECT id, arg2, account, password, mail_box FROM local_accounts WHERE account = $1",
        account
    )
    if row is None:
        return None
    return {"id": row[0], "arg2": row[1], "account": row[2], "password": row[3], "mail_box": row[4]}


def create_local_account(arg2: int, account: str, password_hash: str, mail_box: str) -> None:
    store = get_default_store()
    store.execute(
        "INSERT INTO local_accounts (arg2, account, password, mail_box) VALUES ($1, $2, $3, $4)",
        arg2, account, password_hash, mail_box
    )
