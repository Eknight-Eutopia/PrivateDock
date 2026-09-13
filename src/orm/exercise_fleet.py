from __future__ import annotations
import json
from typing import Optional

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session
from src.orm.converters import to_int64_list


class ExerciseFleet(Base):
    __tablename__ = 'exercise_fleets'
    __table_args__ = {}
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    vanguard_ship_ids: Mapped[str] = mapped_column(String, default='[]')
    main_ship_ids: Mapped[str] = mapped_column(String, default='[]')


def upsert_exercise_fleet(commander_id: int, vanguard_ship_ids: list[int], main_ship_ids: list[int]):
    with get_sync_session() as session:
        obj = session.get(ExerciseFleet, commander_id)
        if obj is None:
            obj = ExerciseFleet(
                commander_id=commander_id,
                vanguard_ship_ids=to_int64_list(vanguard_ship_ids),
                main_ship_ids=to_int64_list(main_ship_ids),
            )
            session.add(obj)
        else:
            obj.vanguard_ship_ids = to_int64_list(vanguard_ship_ids)
            obj.main_ship_ids = to_int64_list(main_ship_ids)
        session.commit()


def _parse_id_list(raw) -> list[int]:
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            return [int(x) for x in json.loads(raw)]
        except Exception:
            return []
    if isinstance(raw, (list, tuple)):
        return [int(x) for x in raw]
    return []


def get_exercise_fleet_sync(commander_id: int) -> tuple[Optional[list[int]], Optional[list[int]]]:
    with get_sync_session() as session:
        obj = session.get(ExerciseFleet, commander_id)
        if obj is None:
            return None, None
        return _parse_id_list(obj.vanguard_ship_ids), _parse_id_list(obj.main_ship_ids)
