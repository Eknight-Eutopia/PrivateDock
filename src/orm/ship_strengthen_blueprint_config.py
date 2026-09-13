from __future__ import annotations

from src.db.session import Base
from typing import Optional
from sqlalchemy import BigInteger, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, JSON
from sqlalchemy.orm import Mapped, mapped_column

# ── SQLAlchemy model ──

class ShipStrengthenBlueprintConfig(Base):
    __tablename__ = 'ship_strengthen_blueprint_configs'
    ship_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    strengthen_blueprint_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
