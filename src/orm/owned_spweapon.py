from __future__ import annotations

from src.db.session import Base



from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

class OwnedSpweapon(Base):
    __tablename__ = 'owned_spweapons'
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(BigInteger)
    template_id: Mapped[int] = mapped_column(BigInteger, default=0)
    attr_1: Mapped[int] = mapped_column("attr_1", BigInteger, default=0)
    attr_2: Mapped[int] = mapped_column("attr_2", BigInteger, default=0)
    attr_temp_1: Mapped[int] = mapped_column("attr_temp_1", BigInteger, default=0)
    attr_temp_2: Mapped[int] = mapped_column("attr_temp_2", BigInteger, default=0)
    effect: Mapped[int] = mapped_column(BigInteger, default=0)
    pt: Mapped[int] = mapped_column(BigInteger, default=0)
    equipped_ship_id: Mapped[int] = mapped_column(BigInteger, default=0)

    @property
    def attr1(self) -> int:
        return self.attr_1

    @attr1.setter
    def attr1(self, val: int):
        self.attr_1 = val

    @property
    def attr2(self) -> int:
        return self.attr_2

    @attr2.setter
    def attr2(self, val: int):
        self.attr_2 = val

    @property
    def attr_temp1(self) -> int:
        return self.attr_temp_1

    @attr_temp1.setter
    def attr_temp1(self, val: int):
        self.attr_temp_1 = val

    @property
    def attr_temp2(self) -> int:
        return self.attr_temp_2

    @attr_temp2.setter
    def attr_temp2(self, val: int):
        self.attr_temp_2 = val

    def __getitem__(self, item: str):
        if hasattr(self, item):
            return getattr(self, item)
        raise KeyError(item)

    def __setitem__(self, key: str, value):
        setattr(self, key, value)

    def get(self, key: str, default=None):
        return getattr(self, key, default)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "template_id": self.template_id,
            "attr_1": self.attr_1,
            "attr_2": self.attr_2,
            "attr_temp_1": self.attr_temp_1,
            "attr_temp_2": self.attr_temp_2,
            "effect": self.effect,
            "pt": self.pt,
            "equipped_ship_id": self.equipped_ship_id,
        }

