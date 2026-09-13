from __future__ import annotations

from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class RequisitionShip(Base):
    __tablename__ = 'requisition_ships'
    __table_args__ = {}
    ship_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
