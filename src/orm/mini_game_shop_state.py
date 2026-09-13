from __future__ import annotations

from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class MiniGameShopState(Base):
    __tablename__ = 'mini_game_shop_states'
    __table_args__ = {}
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    next_refresh_time: Mapped[int] = mapped_column(BigInteger, default=0)
