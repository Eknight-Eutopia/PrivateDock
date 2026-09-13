from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, DateTime, String, text as sa_text
from sqlalchemy.orm import Mapped, mapped_column
from src.orm.account import Account

from src.db.session import Base, get_sync_session

UserRegistrationStatusPending = "pending"
UserRegistrationStatusConsumed = "consumed"
UserRegistrationStatusExpired = "expired"

ErrUserAccountExists = ValueError("user account exists")
ErrRegistrationChallengeExists = ValueError("registration challenge exists")
ErrRegistrationChallengeNotFound = ValueError("registration challenge not found")
ErrRegistrationChallengeConsumed = ValueError("registration challenge consumed")
ErrRegistrationChallengeExpired = ValueError("registration challenge expired")
ErrRegistrationChallengeMismatch = ValueError("registration challenge mismatch")
ErrRegistrationChallengePinMismatch = ValueError("registration challenge pin mismatch")
ErrRegistrationPinExists = ValueError("registration pin exists")


# ── SQLAlchemy model ──
class UserRegistrationChallenge(Base):
    __tablename__ = 'user_registration_challenges'
    __table_args__ = {}
    id: Mapped[str] = mapped_column(String, primary_key=True)
    commander_id: Mapped[int] = mapped_column(BigInteger, default=0)
    pin: Mapped[str] = mapped_column(String, default='')
    password_hash: Mapped[str] = mapped_column(String, default='')
    password_algo: Mapped[str] = mapped_column(String, default='')
    status: Mapped[str] = mapped_column(String, default='')
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


def _row_to_challenge(row) -> UserRegistrationChallenge:
    return UserRegistrationChallenge(
        id=row[0],
        commander_id=row[1],
        pin=row[2],
        password_hash=row[3],
        password_algo=row[4],
        status=row[5],
        expires_at=row[6],
        consumed_at=row[7],
        created_at=row[8],
    )


def create_user_registration_challenge(commander_id: int, pin: str, password_hash: str, password_algo: str, expires_at: datetime, now: datetime) -> UserRegistrationChallenge:
    with get_sync_session() as session:
        existing_count = session.execute(
            sa_text("SELECT COUNT(*) FROM accounts WHERE commander_id = :cid"),
            {"cid": commander_id},
        ).scalar() or 0
        if existing_count > 0:
            raise ErrUserAccountExists
        pending = session.execute(
            sa_text("""
                SELECT id FROM user_registration_challenges
                WHERE commander_id = :cid AND status = :st
                ORDER BY created_at DESC LIMIT 1
            """),
            {"cid": commander_id, "st": UserRegistrationStatusPending},
        ).fetchone()
        if pending is not None:
            session.execute(
                sa_text("""
                    UPDATE user_registration_challenges
                    SET status = :st_expired
                    WHERE id = :id
                """),
                {"id": pending[0], "st_expired": UserRegistrationStatusExpired},
            )
        pin_exists = session.execute(
            sa_text("""
                SELECT EXISTS(
                    SELECT 1 FROM user_registration_challenges
                    WHERE pin = :pin AND status = :st AND expires_at > :now
                )
            """),
            {"pin": pin, "st": UserRegistrationStatusPending, "now": now},
        ).scalar() or False
        if pin_exists:
            raise ErrRegistrationPinExists
        import uuid
        entry = UserRegistrationChallenge(
            id=uuid.uuid4().hex,
            commander_id=commander_id,
            pin=pin,
            password_hash=password_hash,
            password_algo=password_algo,
            status=UserRegistrationStatusPending,
            expires_at=expires_at,
            consumed_at=None,
            created_at=now,
        )
        session.execute(
            sa_text("""
                INSERT INTO user_registration_challenges
                    (id, commander_id, pin, password_hash, password_algo, status, expires_at, consumed_at, created_at)
                VALUES (:id, :cid, :pin, :ph, :pa, :st, :exp, NULL, :ca)
            """),
            {
                "id": entry.id,
                "cid": entry.commander_id,
                "pin": entry.pin,
                "ph": entry.password_hash,
                "pa": entry.password_algo,
                "st": entry.status,
                "exp": entry.expires_at,
                "ca": entry.created_at,
            },
        )
        session.commit()
        return entry


def verify_user_registration_challenge(challenge_id: str, pin: str, now: datetime) -> UserRegistrationChallenge:
    with get_sync_session() as session:
        row = session.execute(
            sa_text("""
                SELECT id, commander_id, pin, password_hash, password_algo, status, expires_at, consumed_at, created_at
                FROM user_registration_challenges
                WHERE id = :id
            """),
            {"id": challenge_id},
        ).fetchone()
        if row is None:
            raise ErrRegistrationChallengeNotFound
        challenge = _row_to_challenge(row)
        if challenge.status == UserRegistrationStatusConsumed:
            raise ErrRegistrationChallengeConsumed
        if challenge.status == UserRegistrationStatusExpired:
            raise ErrRegistrationChallengeExpired
        if challenge.expires_at and challenge.expires_at <= now:
            session.execute(
                sa_text("UPDATE user_registration_challenges SET status = :st WHERE id = :id"),
                {"st": UserRegistrationStatusExpired, "id": challenge_id},
            )
            session.commit()
            raise ErrRegistrationChallengeExpired
        if challenge.pin != pin:
            raise ErrRegistrationChallengePinMismatch
        return challenge


def consume_user_registration_challenge(commander_id: int, pin: str, now: datetime) -> Account:
    with get_sync_session() as session:
        challenge = session.execute(
            sa_text("""
                SELECT id, commander_id, pin, password_hash, password_algo, status, expires_at, consumed_at, created_at
                FROM user_registration_challenges
                WHERE pin = :pin AND status = :st
                ORDER BY created_at DESC LIMIT 1
            """),
            {"pin": pin, "st": UserRegistrationStatusPending},
        ).fetchone()
        if challenge is None:
            raise ErrRegistrationChallengeNotFound
        c = _row_to_challenge(challenge)
        if c.commander_id != commander_id:
            raise ErrRegistrationChallengeMismatch
        if c.expires_at and c.expires_at <= now:
            session.execute(
                sa_text("UPDATE user_registration_challenges SET status = :st WHERE id = :id"),
                {"st": UserRegistrationStatusExpired, "id": c.id},
            )
            session.commit()
            raise ErrRegistrationChallengeExpired
        existing = session.execute(
            sa_text("SELECT COUNT(*) FROM accounts WHERE commander_id = :cid"),
            {"cid": commander_id},
        ).scalar() or 0
        if existing > 0:
            raise ErrUserAccountExists
        role_row = session.execute(
            sa_text("SELECT id FROM roles WHERE name = 'player' LIMIT 1"),
        ).fetchone()
        role_id = role_row[0] if role_row else None
        import uuid
        created = Account(
            id=uuid.uuid4().hex,
            commander_id=commander_id,
            password_hash=c.password_hash,
            password_algo=c.password_algo,
            password_updated_at=now,
            created_at=now,
            updated_at=now,
        )
        session.execute(
            sa_text("""
                INSERT INTO accounts (id, commander_id, password_hash, password_algo, password_updated_at, created_at, updated_at)
                VALUES (:id, :cid, :ph, :pa, :pua, :ca, :ua)
            """),
            {
                "id": created.id,
                "cid": created.commander_id,
                "ph": created.password_hash,
                "pa": created.password_algo,
                "pua": created.password_updated_at,
                "ca": created.created_at,
                "ua": created.updated_at,
            },
        )
        if role_id:
            session.execute(
                sa_text("INSERT INTO account_roles (account_id, role_id, created_at) VALUES (:aid, :rid, :ca)"),
                {"aid": created.id, "rid": role_id, "ca": now},
            )
        session.execute(
            sa_text("""
                UPDATE user_registration_challenges
                SET status = :st, consumed_at = :ca
                WHERE id = :id
            """),
            {"st": UserRegistrationStatusConsumed, "ca": now, "id": c.id},
        )
        session.commit()
        return created


def consume_user_registration_challenge_by_id(challenge_id: str, pin: str, now: datetime) -> Account:
    with get_sync_session() as session:
        row = session.execute(
            sa_text("""
                SELECT id, commander_id, pin, password_hash, password_algo, status, expires_at, consumed_at, created_at
                FROM user_registration_challenges
                WHERE id = :id
            """),
            {"id": challenge_id},
        ).fetchone()
        if row is None:
            raise ErrRegistrationChallengeNotFound
        challenge = _row_to_challenge(row)
        if challenge.status == UserRegistrationStatusConsumed:
            raise ErrRegistrationChallengeConsumed
        if challenge.status == UserRegistrationStatusExpired:
            raise ErrRegistrationChallengeExpired
        if challenge.expires_at and challenge.expires_at <= now:
            session.execute(
                sa_text("UPDATE user_registration_challenges SET status = :st WHERE id = :id"),
                {"st": UserRegistrationStatusExpired, "id": challenge_id},
            )
            session.commit()
            raise ErrRegistrationChallengeExpired
        if challenge.pin != pin:
            raise ErrRegistrationChallengePinMismatch
        existing = session.execute(
            sa_text("SELECT COUNT(*) FROM accounts WHERE commander_id = :cid"),
            {"cid": challenge.commander_id},
        ).scalar() or 0
        if existing > 0:
            raise ErrUserAccountExists
        role_row = session.execute(
            sa_text("SELECT id FROM roles WHERE name = 'player' LIMIT 1"),
        ).fetchone()
        role_id = role_row[0] if role_row else None
        import uuid
        created = Account(
            id=uuid.uuid4().hex,
            commander_id=challenge.commander_id,
            password_hash=challenge.password_hash,
            password_algo=challenge.password_algo,
            password_updated_at=now,
            created_at=now,
            updated_at=now,
        )
        session.execute(
            sa_text("""
                INSERT INTO accounts (id, commander_id, password_hash, password_algo, password_updated_at, created_at, updated_at)
                VALUES (:id, :cid, :ph, :pa, :pua, :ca, :ua)
            """),
            {
                "id": created.id,
                "cid": created.commander_id,
                "ph": created.password_hash,
                "pa": created.password_algo,
                "pua": created.password_updated_at,
                "ca": created.created_at,
                "ua": created.updated_at,
            },
        )
        if role_id:
            session.execute(
                sa_text("INSERT INTO account_roles (account_id, role_id, created_at) VALUES (:aid, :rid, :ca)"),
                {"aid": created.id, "rid": role_id, "ca": now},
            )
        session.execute(
            sa_text("""
                UPDATE user_registration_challenges
                SET status = :st, consumed_at = :ca
                WHERE id = :id
            """),
            {"st": UserRegistrationStatusConsumed, "ca": now, "id": challenge_id},
        )
        session.commit()
        return created


def get_user_registration_challenge(challenge_id: str) -> Optional[UserRegistrationChallenge]:
    with get_sync_session() as session:
        row = session.execute(
            sa_text("""
                SELECT id, commander_id, pin, password_hash, password_algo, status, expires_at, consumed_at, created_at
                FROM user_registration_challenges
                WHERE id = :id
            """),
            {"id": challenge_id},
        ).fetchone()
        if row is None:
            return None
        return _row_to_challenge(row)


def update_user_registration_challenge_status(challenge_id: str, status: str) -> None:
    with get_sync_session() as session:
        row = session.execute(
            sa_text("SELECT consumed_at FROM user_registration_challenges WHERE id = :id"),
            {"id": challenge_id},
        ).fetchone()
        if row is None:
            return
        consumed_at = row[0]
        if status == UserRegistrationStatusConsumed and consumed_at is None:
            consumed_at = datetime.utcnow()
        session.execute(
            sa_text("""
                UPDATE user_registration_challenges
                SET status = :st, consumed_at = :ca
                WHERE id = :id
            """),
            {"st": status, "ca": consumed_at, "id": challenge_id},
        )
        session.commit()


# ── SQLAlchemy model ──
