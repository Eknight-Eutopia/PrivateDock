from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, Boolean, DateTime, LargeBinary, String, text as sa_text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


# ── SQLAlchemy model ──
class Account(Base):
    __tablename__ = 'accounts'
    __table_args__ = {}
    id: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    username_normalized: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    commander_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    password_hash: Mapped[str] = mapped_column(String, default='')
    password_algo: Mapped[str] = mapped_column(String, default='')
    password_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    disabled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    web_authn_user_handle: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


def _row_to_account(row) -> Account:
    return Account(
        id=row[0],
        username=row[1],
        username_normalized=row[2],
        commander_id=row[3] if row[3] else None,
        password_hash=row[4],
        password_algo=row[5],
        password_updated_at=row[6],
        is_admin=row[7],
        disabled_at=row[8],
        last_login_at=row[9],
        web_authn_user_handle=row[10] if len(row) > 10 else None,
        created_at=row[11] if len(row) > 11 else None,
        updated_at=row[12] if len(row) > 12 else None,
    )


def _scan_account_row(row) -> Account:
    return _row_to_account(row)


def get_account_by_commander_id(commander_id: int) -> Optional[Account]:
    with get_sync_session() as session:
        row = session.execute(
            sa_text("""
                SELECT id, username, username_normalized, commander_id,
                    password_hash, password_algo, password_updated_at,
                    is_admin, disabled_at, last_login_at,
                    web_authn_user_handle, created_at, updated_at
                FROM accounts
                WHERE commander_id = :cid
            """),
            {"cid": commander_id},
        ).fetchone()
        if row is None:
            return None
        return _row_to_account(row)


def update_account_last_login_at(account_id: str, login_at: datetime) -> None:
    with get_sync_session() as session:
        session.execute(
            sa_text("""
                UPDATE accounts
                SET last_login_at = :la, updated_at = :la
                WHERE id = :id
            """),
            {"id": account_id, "la": login_at},
        )
        session.commit()


def count_admin_accounts() -> int:
    with get_sync_session() as session:
        return session.execute(
            sa_text("""
                SELECT COUNT(*)
                FROM accounts
                WHERE is_admin = true
                   OR EXISTS (
                    SELECT 1
                    FROM account_roles
                    JOIN roles ON roles.id = account_roles.role_id
                    WHERE account_roles.account_id = accounts.id
                      AND roles.name = 'admin'
                )
            """),
        ).scalar() or 0


def list_admin_accounts(offset: int = 0, limit: int = 20) -> tuple[list[Account], int]:
    with get_sync_session() as session:
        session.commit()
        total = session.execute(
            sa_text("""
                SELECT COUNT(*)
                FROM accounts
                WHERE is_admin = true
                   OR EXISTS (
                    SELECT 1
                    FROM account_roles
                    JOIN roles ON roles.id = account_roles.role_id
                    WHERE account_roles.account_id = accounts.id
                      AND roles.name = 'admin'
                )
            """),
        ).scalar() or 0
        rows = session.execute(
            sa_text("""
                SELECT id, username, username_normalized, commander_id,
                    password_hash, password_algo, password_updated_at,
                    is_admin, disabled_at, last_login_at,
                    web_authn_user_handle, created_at, updated_at
                FROM accounts
                WHERE is_admin = true
                   OR EXISTS (
                    SELECT 1
                    FROM account_roles
                    JOIN roles ON roles.id = account_roles.role_id
                    WHERE account_roles.account_id = accounts.id
                      AND roles.name = 'admin'
                )
                ORDER BY created_at DESC
                OFFSET :off
                LIMIT :lim
            """),
            {"off": offset, "lim": limit},
        ).fetchall()
        accounts = [_row_to_account(r) for r in rows]
        return accounts, total

# ── SQLAlchemy model ──
