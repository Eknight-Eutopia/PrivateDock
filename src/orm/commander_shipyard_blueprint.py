from __future__ import annotations

from src.db.session import Base
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

# ── SQLAlchemy model ──

class CommanderShipyardBlueprint(Base):
    __tablename__ = 'commander_shipyard_blueprints'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    blueprint_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ship_id: Mapped[int] = mapped_column(BigInteger, default=0)
    start_time: Mapped[int] = mapped_column(BigInteger, default=0)
    blue_print_level: Mapped[int] = mapped_column(BigInteger, default=0)
    exp: Mapped[int] = mapped_column(BigInteger, default=0)
    start_duration: Mapped[int] = mapped_column(BigInteger, default=0)
