from __future__ import annotations

from sqlalchemy import BigInteger, select
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


class GlobalSkinRestrictionWindow(Base):
    __tablename__ = 'global_skin_restriction_windows'
    __table_args__ = {}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    skin_id: Mapped[int] = mapped_column(BigInteger)
    type: Mapped[int] = mapped_column(BigInteger, default=0)
    start_time: Mapped[int] = mapped_column(BigInteger, default=0)
    stop_time: Mapped[int] = mapped_column(BigInteger, default=0)


def list_global_skin_restriction_windows() -> list:
    with get_sync_session() as session:
        result = session.execute(select(GlobalSkinRestrictionWindow).order_by(GlobalSkinRestrictionWindow.skin_id))
        return list(result.scalars().all())
