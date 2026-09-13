import json

from sqlalchemy.exc import IntegrityError
from src.auth.password import hash_password, verify_password
from src.db.store import get_default_store

SECONDARY_PASSWORD_LENGTH = 6
SECONDARY_PASSWORD_MAX_FAILURES = 5
SECONDARY_PASSWORD_LOCKOUT_SECONDS = 300


def is_secondary_password_valid(password: str) -> bool:
    if len(password) != SECONDARY_PASSWORD_LENGTH:
        return False
    return all("0" <= ch <= "9" for ch in password)


def hash_secondary_password(password: str) -> str:
    return hash_password(password)


def verify_secondary_password(password: str, encoded: str) -> bool:
    return verify_password(encoded, password)


def sanitize_secondary_system_list(values: list) -> list:
    if not values:
        return []
    seen = set()
    result = []
    for v in values:
        if v == 0:
            continue
        if v not in seen:
            seen.add(v)
            result.append(v)
    result.sort()
    return result


def secondary_password_locked(state: dict, now: int) -> bool:
    return state["fail_cd"] > 0 and now < state["fail_cd"]


def apply_secondary_password_failure(state: dict, now: int):
    if state["fail_count"] < SECONDARY_PASSWORD_MAX_FAILURES:
        state["fail_count"] += 1
    if state["fail_count"] >= SECONDARY_PASSWORD_MAX_FAILURES:
        state["fail_count"] = SECONDARY_PASSWORD_MAX_FAILURES
        state["fail_cd"] = now + SECONDARY_PASSWORD_LOCKOUT_SECONDS


async def get_or_create_secondary_password_state(commander_id: int) -> dict:
    store = get_default_store()
    row = await store.afetchrow(
        "SELECT commander_id, password_hash, notice, system_list, state, fail_count, fail_cd "
        "FROM secondary_password_states WHERE commander_id = $1",
        commander_id
    )
    if row:
        state = dict(row)
        if isinstance(state["system_list"], str):
            state["system_list"] = json.loads(state["system_list"]) if state["system_list"] else []
        elif state["system_list"] is None:
            state["system_list"] = []
        return state

    try:
        row = await store.afetchrow(
            "INSERT INTO secondary_password_states (commander_id, password_hash, notice, system_list, state, fail_count, fail_cd) "
            "VALUES ($1, '', '', '[]', 0, 0, 0) "
            "ON CONFLICT (commander_id) DO NOTHING "
            "RETURNING commander_id, password_hash, notice, system_list, state, fail_count, fail_cd",
            commander_id
        )
    except IntegrityError:
        row = None
    if row:
        state = dict(row)
        if isinstance(state["system_list"], str):
            state["system_list"] = json.loads(state["system_list"]) if state["system_list"] else []
        elif state["system_list"] is None:
            state["system_list"] = []
        return state

    return {
        "commander_id": commander_id,
        "password_hash": "",
        "notice": "",
        "system_list": [],
        "state": 0,
        "fail_count": 0,
        "fail_cd": 0,
    }


async def save_secondary_password_state(state: dict):
    store = get_default_store()
    system_list_raw = json.dumps(state["system_list"])
    await store.aexecute(
        "INSERT INTO secondary_password_states (commander_id, password_hash, notice, system_list, state, fail_count, fail_cd) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7) "
        "ON CONFLICT (commander_id) DO UPDATE SET "
        "password_hash = EXCLUDED.password_hash, "
        "notice = EXCLUDED.notice, "
        "system_list = EXCLUDED.system_list, "
        "state = EXCLUDED.state, "
        "fail_count = EXCLUDED.fail_count, "
        "fail_cd = EXCLUDED.fail_cd",
        state["commander_id"], state["password_hash"], state["notice"],
        system_list_raw, state["state"], state["fail_count"], state["fail_cd"]
    )
