from __future__ import annotations

from sqlalchemy import BigInteger, select
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


class GlobalSkinRestriction(Base):
    __tablename__ = 'global_skin_restrictions'
    __table_args__ = {}
    skin_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    type: Mapped[int] = mapped_column(BigInteger, default=0)

def list_global_skin_restrictions() -> list:
    with get_sync_session() as session:
        result = session.execute(select(GlobalSkinRestriction).order_by(GlobalSkinRestriction.skin_id))
        return list(result.scalars().all())
