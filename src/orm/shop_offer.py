from __future__ import annotations
from typing import Any, Optional
from sqlalchemy import BigInteger, String, JSON, select
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session


class ShopOffer(Base):
    __tablename__ = 'shop_offers'
    __table_args__ = {}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    effects: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    effect_args: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    number: Mapped[int] = mapped_column(BigInteger, default=0)
    resource_number: Mapped[int] = mapped_column(BigInteger, default=0)
    resource_id: Mapped[int] = mapped_column(BigInteger, default=0)
    type: Mapped[int] = mapped_column(BigInteger, default=0)
    genre: Mapped[str] = mapped_column(String, default='')
    discount: Mapped[int] = mapped_column(BigInteger, default=0)


async def count_shop_offers(genre: str = "") -> int:
    async with get_session() as session:
        if genre:
            result = await session.execute(
                select(ShopOffer).where(ShopOffer.genre == genre)
            )
        else:
            result = await session.execute(select(ShopOffer))
        return len(result.scalars().all())


async def list_shop_offers(offset: int = 0, limit: int = 100, genre: str = "") -> list[dict[str, Any]]:
    async with get_session() as session:
        q = select(ShopOffer).order_by(ShopOffer.id)
        if genre:
            q = q.where(ShopOffer.genre == genre)
        q = q.offset(offset).limit(limit)
        result = await session.execute(q)
        rows = result.scalars().all()
        return [
            {
                "id": r.id,
                "effects": r.effects,
                "effect_args": r.effect_args,
                "number": r.number,
                "resource_number": r.resource_number,
                "resource_id": r.resource_id,
                "type": r.type,
                "genre": r.genre,
                "discount": r.discount,
            }
            for r in rows
        ]


async def get_shop_offer(offer_id: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        r = await session.get(ShopOffer, offer_id)
        if r is None:
            return None
        return {
            "id": r.id,
            "effects": r.effects,
            "effect_args": r.effect_args,
            "number": r.number,
            "resource_number": r.resource_number,
            "resource_id": r.resource_id,
            "type": r.type,
            "genre": r.genre,
            "discount": r.discount,
        }


async def create_shop_offer(data: dict[str, Any]) -> None:
    async with get_session() as session:
        obj = ShopOffer(
            id=data["id"],
            effects=data.get("effects"),
            effect_args=data.get("effect_args"),
            number=data.get("number", 0),
            resource_number=data.get("resource_number", 0),
            resource_id=data.get("resource_id", 0),
            type=data.get("type", 0),
            genre=data.get("genre", ""),
            discount=data.get("discount", 0),
        )
        session.add(obj)
        await session.commit()


async def update_shop_offer(offer_id: int, data: dict[str, Any]) -> None:
    async with get_session() as session:
        r = await session.get(ShopOffer, offer_id)
        if r is None:
            return
        r.effects = data.get("effects", r.effects)
        r.effect_args = data.get("effect_args", r.effect_args)
        r.number = data.get("number", r.number)
        r.resource_number = data.get("resource_number", r.resource_number)
        r.resource_id = data.get("resource_id", r.resource_id)
        r.type = data.get("type", r.type)
        r.genre = data.get("genre", r.genre)
        r.discount = data.get("discount", r.discount)
        await session.commit()


async def delete_shop_offer(offer_id: int) -> bool:
    async with get_session() as session:
        r = await session.get(ShopOffer, offer_id)
        if r is None:
            return False
        await session.delete(r)
        await session.commit()
        return True
