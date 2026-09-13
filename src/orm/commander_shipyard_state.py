from __future__ import annotations

from src.db.session import Base
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

# ── SQLAlchemy model ──

class CommanderShipyardState(Base):
    __tablename__ = 'commander_shipyard_states'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cold_time: Mapped[int] = mapped_column(BigInteger, default=0)
    daily_catchup_strengthen: Mapped[int] = mapped_column(BigInteger, default=0)
    daily_catchup_strengthen_ur: Mapped[int] = mapped_column(BigInteger, default=0)
