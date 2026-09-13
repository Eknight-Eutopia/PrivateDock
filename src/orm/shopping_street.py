from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, select, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


class ShoppingStreetState(Base):
    __tablename__ = "shopping_street_states"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    level: Mapped[int] = mapped_column(BigInteger, default=0)
    next_flash_time: Mapped[int] = mapped_column(BigInteger, default=0)
    level_up_time: Mapped[int] = mapped_column(BigInteger, default=0)
    flash_count: Mapped[int] = mapped_column(BigInteger, default=0)


class ShoppingStreetGood(Base):
    __tablename__ = "shopping_street_goods"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    goods_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    discount: Mapped[int] = mapped_column(BigInteger, default=0)
    buy_count: Mapped[int] = mapped_column(BigInteger, default=0)


def get_shopping_street_state(commander_id: int) -> Optional[dict]:
    with get_sync_session() as session:
        row = session.execute(
            select(ShoppingStreetState).where(ShoppingStreetState.commander_id == commander_id)
        ).scalar_one_or_none()
        if row is None:
            return None
        return {
            "commander_id": row.commander_id,
            "level": row.level,
            "next_flash_time": row.next_flash_time,
            "level_up_time": row.level_up_time,
            "flash_count": row.flash_count,
        }


def upsert_shopping_street_state(commander_id: int, level: int, next_flash_time: int, level_up_time: int, flash_count: int) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO shopping_street_states (commander_id, level, next_flash_time, level_up_time, flash_count)
                VALUES (:cid, :lv, :nft, :lut, :fc)
                ON CONFLICT (commander_id)
                DO UPDATE SET level = EXCLUDED.level,
                    next_flash_time = EXCLUDED.next_flash_time,
                    level_up_time = EXCLUDED.level_up_time,
                    flash_count = EXCLUDED.flash_count
            """),
            {"cid": commander_id, "lv": level, "nft": next_flash_time, "lut": level_up_time, "fc": flash_count},
        )
        session.commit()


def list_shopping_street_goods(commander_id: int) -> list[dict]:
    with get_sync_session() as session:
        rows = session.execute(
            select(ShoppingStreetGood).where(ShoppingStreetGood.commander_id == commander_id)
        ).scalars().all()
        return [
            {
                "commander_id": r.commander_id,
                "goods_id": r.goods_id,
                "discount": r.discount,
                "buy_count": r.buy_count,
            }
            for r in rows
        ]


def upsert_shopping_street_good(commander_id: int, goods_id: int, discount: int, buy_count: int) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO shopping_street_goods (commander_id, goods_id, discount, buy_count)
                VALUES (:cid, :gid, :disc, :bc)
                ON CONFLICT (commander_id, goods_id)
                DO UPDATE SET discount = EXCLUDED.discount, buy_count = EXCLUDED.buy_count
            """),
            {"cid": commander_id, "gid": goods_id, "disc": discount, "bc": buy_count},
        )
        session.commit()


def delete_shopping_street_good(commander_id: int, goods_id: int) -> bool:
    with get_sync_session() as session:
        result = session.execute(
            text("DELETE FROM shopping_street_goods WHERE commander_id = :cid AND goods_id = :gid"),
            {"cid": commander_id, "gid": goods_id},
        )
        session.commit()
        return result.rowcount > 0


get_shopping_street_state_sync = get_shopping_street_state
upsert_shopping_street_state_sync = upsert_shopping_street_state
list_shopping_street_goods_sync = list_shopping_street_goods
upsert_shopping_street_good_sync = upsert_shopping_street_good
delete_shopping_street_good_sync = delete_shopping_street_good
