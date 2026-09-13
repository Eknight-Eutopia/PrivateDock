from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


# ── SQLAlchemy model ──

class ShipEquipConfig(Base):
    __tablename__ = 'ship_equip_configs'
    ship_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    equip_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
