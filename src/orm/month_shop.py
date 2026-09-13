from __future__ import annotations

from src.db.session import Base
from datetime import datetime
from typing import Optional

from sqlalchemy import select, text

from src.db.session import get_session
from sqlalchemy import BigInteger, DateTime
from sqlalchemy.orm import Mapped, mapped_column

def list_month_shop_purchase_counts_sync(commander_id: int, month: int) -> dict[int, int]:
    from src.db.session import get_sync_session
    with get_sync_session() as session:
        result = session.execute(
            select(MonthShopPurchase).where(
                MonthShopPurchase.commander_id == commander_id,
                MonthShopPurchase.month == month,
            )
        )
        rows = list(result.scalars().all())
        return {r.goods_id: r.buy_count for r in rows}


async def list_month_shop_purchase_counts(commander_id: int, month: int) -> dict[int, int]:
    async with get_session() as session:
        result = await session.execute(
            select(MonthShopPurchase).where(
                MonthShopPurchase.commander_id == commander_id,
                MonthShopPurchase.month == month,
            )
        )
        rows = list(result.scalars().all())
        return {r.goods_id: r.buy_count for r in rows}

async def get_month_shop_purchase_count(
    commander_id: int, goods_id: int, month: int
) -> int:
    async with get_session() as session:
        result = await session.execute(
            select(MonthShopPurchase).where(
                MonthShopPurchase.commander_id == commander_id,
                MonthShopPurchase.goods_id == goods_id,
                MonthShopPurchase.month == month,
            )
        )
        row = result.scalar_one_or_none()
        return row.buy_count if row is not None else 0

async def increment_month_shop_purchase(
    commander_id: int, goods_id: int, month: int, delta: int = 1
):
    async with get_session() as session:
        await session.execute(
            text("""
                INSERT INTO month_shop_purchases (commander_id, goods_id, month, buy_count)
                VALUES (:cid, :gid, :month, :delta)
                ON CONFLICT (commander_id, goods_id, month)
                DO UPDATE SET
                  buy_count = month_shop_purchases.buy_count + EXCLUDED.buy_count,
                  updated_at = CURRENT_TIMESTAMP
            """),
            {"cid": commander_id, "gid": goods_id, "month": month, "delta": delta},
        )
        await session.commit()

class MonthShopPurchase(Base):
    __tablename__ = 'month_shop_purchases'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    goods_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    month: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    buy_count: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
