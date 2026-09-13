from __future__ import annotations

from src.db.session import Base
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

# ── SQLAlchemy model ──

class ShipyardBlueprintProto(Base):
    __tablename__ = 'shipyard_blueprint_protos'
    blueprint_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ship_id: Mapped[int] = mapped_column(BigInteger)
    blue_print_level: Mapped[int] = mapped_column(BigInteger, default=0)
