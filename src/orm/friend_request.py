from __future__ import annotations

from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

class FriendRequest(Base):
    __tablename__ = "friend_requests"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sender_id: Mapped[int] = mapped_column(BigInteger, default=0)
    target_id: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[int] = mapped_column(BigInteger, default=0)
