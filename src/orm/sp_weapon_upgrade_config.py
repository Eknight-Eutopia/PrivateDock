from __future__ import annotations

from src.db.session import Base
from typing import Optional
from sqlalchemy import BigInteger, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, JSON
from sqlalchemy.orm import Mapped, mapped_column

# ── SQLAlchemy model ──

class SpWeaponUpgradeConfig(Base):
    __tablename__ = 'sp_weapon_upgrade_configs'
    spweapon_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    level: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    upgrade_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
