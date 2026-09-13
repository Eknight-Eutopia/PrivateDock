from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, JSON, String, select, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


class ExchangeCode(Base):
    __tablename__ = "exchange_codes"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), default="")
    platform: Mapped[str] = mapped_column(String(32), default="")
    quota: Mapped[int] = mapped_column(BigInteger, default=-1)
    rewards: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ExchangeCodeRedeem(Base):
    __tablename__ = "exchange_code_redeems"
    exchange_code_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    redeemed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


def get_exchange_code(code: str) -> Optional[dict]:
    with get_sync_session() as session:
        row = session.execute(
            select(ExchangeCode).where(ExchangeCode.code == code)
        ).scalar_one_or_none()
        if row is None:
            return None
        return {
            "id": row.id,
            "code": row.code,
            "platform": row.platform,
            "quota": row.quota,
            "rewards": row.rewards,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }


def create_exchange_code_redeem(exchange_code_id: int, commander_id: int) -> Optional[dict]:
    with get_sync_session() as session:
        row = session.execute(
            text("""
                INSERT INTO exchange_code_redeems (exchange_code_id, commander_id, redeemed_at)
                VALUES (:ecid, :cid, CURRENT_TIMESTAMP)
                ON CONFLICT (exchange_code_id, commander_id) DO NOTHING
                RETURNING redeemed_at
            """),
            {"ecid": exchange_code_id, "cid": commander_id},
        ).fetchone()
        session.commit()
        if row is None:
            return None
        return {
            "exchange_code_id": exchange_code_id,
            "commander_id": commander_id,
            "redeemed_at": row[0],
        }


def get_exchange_code_redeem(exchange_code_id: int, commander_id: int) -> Optional[dict]:
    with get_sync_session() as session:
        row = session.execute(
            select(ExchangeCodeRedeem).where(
                ExchangeCodeRedeem.exchange_code_id == exchange_code_id,
                ExchangeCodeRedeem.commander_id == commander_id,
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return {
            "exchange_code_id": row.exchange_code_id,
            "commander_id": row.commander_id,
            "redeemed_at": row.redeemed_at,
        }


def decrement_exchange_code_quota(code_id: int) -> bool:
    with get_sync_session() as session:
        result = session.execute(
            text("""
                UPDATE exchange_codes
                SET quota = quota - 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = :id AND quota > 0
            """),
            {"id": code_id},
        )
        session.commit()
        return result.rowcount > 0


get_exchange_code_sync = get_exchange_code
create_exchange_code_redeem_sync = create_exchange_code_redeem
get_exchange_code_redeem_sync = get_exchange_code_redeem
decrement_exchange_code_quota_sync = decrement_exchange_code_quota
