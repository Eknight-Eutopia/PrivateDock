import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from src.orm.auth_challenge import AuthChallenge
from src.db.store import get_default_store


class ChallengeNotFound(Exception):
    pass


async def store_challenge(account_id: Optional[str], challenge_type: str, session_data: dict, expires_at: datetime) -> AuthChallenge:
    metadata = json.dumps(session_data).encode("utf-8")
    now = datetime.now(timezone.utc)
    challenge = session_data.get("challenge", "")
    entry = AuthChallenge(
        id=str(uuid.uuid4()),
        account_id=account_id,
        challenge_type=challenge_type,
        challenge_data=challenge,
        expires_at=expires_at,
        created_at=now,
        metadata=metadata,
    )
    store = get_default_store()
    row = await store.afetchrow(
        "INSERT INTO auth_challenges (id, account_id, challenge_type, challenge_data, expires_at, created_at, metadata) "
        "VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id, account_id, challenge_type, challenge_data, expires_at, created_at, metadata",
        entry.id, entry.account_id, entry.challenge_type, entry.challenge_data,
        entry.expires_at, entry.created_at, entry.metadata,
    )
    return _row_to_challenge(row)


async def load_challenge_by_user(account_id: str, challenge_type: str) -> tuple[AuthChallenge, dict]:
    store = get_default_store()
    row = await store.afetchrow(
        "SELECT id, account_id, challenge_type, challenge_data, expires_at, created_at, metadata "
        "FROM auth_challenges WHERE account_id = $1 AND challenge_type = $2 AND expires_at > NOW() ORDER BY created_at DESC LIMIT 1",
        account_id, challenge_type,
    )
    if row is None:
        raise ChallengeNotFound("challenge not found")
    entry = _row_to_challenge(row)
    session = json.loads(entry.metadata) if entry.metadata else {}
    return entry, session


async def load_challenge_by_challenge(challenge: str, challenge_type: str) -> tuple[AuthChallenge, dict]:
    store = get_default_store()
    row = await store.afetchrow(
        "SELECT id, account_id, challenge_type, challenge_data, expires_at, created_at, metadata "
        "FROM auth_challenges WHERE challenge_data = $1 AND challenge_type = $2 AND expires_at > NOW() ORDER BY created_at DESC LIMIT 1",
        challenge, challenge_type,
    )
    if row is None:
        raise ChallengeNotFound("challenge not found")
    entry = _row_to_challenge(row)
    session = json.loads(entry.metadata) if entry.metadata else {}
    return entry, session


async def delete_challenge(challenge_id: str):
    store = get_default_store()
    await store.aexecute("DELETE FROM auth_challenges WHERE id = $1", challenge_id)


def _row_to_challenge(row) -> AuthChallenge:
    return AuthChallenge(
        id=row["id"],
        account_id=row.get("account_id"),
        challenge_type=row["challenge_type"],
        challenge_data=row["challenge_data"],
        expires_at=row.get("expires_at"),
        created_at=row.get("created_at"),
        metadata=row.get("metadata"),
    )
