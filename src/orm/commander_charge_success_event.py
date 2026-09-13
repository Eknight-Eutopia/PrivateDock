from __future__ import annotations

from sqlalchemy import BigInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


def try_record_charge_success_event(commander_id: int, pay_id: str) -> bool:
    with get_sync_session() as session:
        result = session.execute(
            text("""
                INSERT INTO commander_charge_success_events (commander_id, pay_id)
                VALUES (:commander_id, :pay_id)
                ON CONFLICT (commander_id, pay_id) DO NOTHING
            """),
            {"commander_id": commander_id, "pay_id": pay_id},
        )
        session.commit()
        return result.rowcount > 0


class CommanderChargeSuccessEvent(Base):
    __tablename__ = "commander_charge_success_events"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pay_id: Mapped[str] = mapped_column(String, primary_key=True)
