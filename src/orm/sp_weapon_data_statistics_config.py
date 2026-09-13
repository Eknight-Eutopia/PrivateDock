from __future__ import annotations

from src.db.session import Base
from typing import Optional
from sqlalchemy import BigInteger, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, JSON
from sqlalchemy.orm import Mapped, mapped_column

# ── SQLAlchemy model ──

class SpWeaponDataStatisticsConfig(Base):
    __tablename__ = 'sp_weapon_data_statistics_configs'
    spweapon_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    stat_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
