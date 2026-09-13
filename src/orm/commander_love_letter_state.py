from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, DateTime, JSON, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


class LoveLetterMedalState:
    def __init__(self, group_id: int = 0, exp: int = 0, level: int = 0):
        self.group_id = group_id
        self.exp = exp
        self.level = level

    def to_dict(self) -> dict:
        return {"group_id": self.group_id, "exp": self.exp, "level": self.level}

    @classmethod
    def from_dict(cls, d: dict) -> "LoveLetterMedalState":
        return cls(group_id=d.get("group_id", 0), exp=d.get("exp", 0), level=d.get("level", 0))


class LoveLetterLetterState:
    def __init__(self, group_id: int = 0, letter_id_list: Optional[list[int]] = None):
        self.group_id = group_id
        self.letter_id_list = letter_id_list or []

    def to_dict(self) -> dict:
        return {"group_id": self.group_id, "letter_id_list": self.letter_id_list}

    @classmethod
    def from_dict(cls, d: dict) -> "LoveLetterLetterState":
        return cls(group_id=d.get("group_id", 0), letter_id_list=d.get("letter_id_list", []))


class LoveLetterConvertedItem:
    def __init__(self, item_id: int = 0, group_id: int = 0, year: int = 0):
        self.item_id = item_id
        self.group_id = group_id
        self.year = year

    def to_dict(self) -> dict:
        return {"item_id": self.item_id, "group_id": self.group_id, "year": self.year}

    @classmethod
    def from_dict(cls, d: dict) -> "LoveLetterConvertedItem":
        return cls(item_id=d.get("item_id", 0), group_id=d.get("group_id", 0), year=d.get("year", 0))


class CommanderLoveLetterStateData:
    def __init__(self):
        self.commander_id: int = 0
        self.medals: list[LoveLetterMedalState] = []
        self.manual_letters: list[LoveLetterLetterState] = []
        self.converted_items: list[LoveLetterConvertedItem] = []
        self.rewarded_ids: list[int] = []
        self.letter_contents: dict[int, str] = {}
        self.created_at: Optional[datetime] = None
        self.updated_at: Optional[datetime] = None


def _marshal_contents(contents: dict[int, str]) -> str:
    if not contents:
        return "{}"
    encoded = {str(k): v for k, v in contents.items()}
    return json.dumps(encoded, ensure_ascii=False, separators=(",", ":"))


def _unmarshal_contents(raw) -> dict[int, str]:
    if not raw:
        return {}
    if isinstance(raw, str):
        decoded = json.loads(raw)
    elif isinstance(raw, (bytes, bytearray)):
        decoded = json.loads(raw.decode("utf-8"))
    else:
        decoded = raw
    if not decoded:
        return {}
    result = {}
    for k, v in decoded.items():
        try:
            result[int(k)] = str(v)
        except (ValueError, TypeError):
            pass
    return result


def _row_to_state_data(row) -> CommanderLoveLetterStateData:
    state = CommanderLoveLetterStateData()
    state.commander_id = row.commander_id
    state.created_at = row.created_at
    state.updated_at = row.updated_at

    medals_raw = row.medals
    if medals_raw:
        if isinstance(medals_raw, str):
            medals_list = json.loads(medals_raw)
        else:
            medals_list = medals_raw
        state.medals = [LoveLetterMedalState.from_dict(m) for m in medals_list]

    manual_raw = row.manual_letters
    if manual_raw:
        if isinstance(manual_raw, str):
            manual_list = json.loads(manual_raw)
        else:
            manual_list = manual_raw
        state.manual_letters = [LoveLetterLetterState.from_dict(m) for m in manual_list]

    converted_raw = row.converted_items
    if converted_raw:
        if isinstance(converted_raw, str):
            converted_list = json.loads(converted_raw)
        else:
            converted_list = converted_raw
        state.converted_items = [LoveLetterConvertedItem.from_dict(c) for c in converted_list]

    rewarded_raw = row.rewarded_ids
    if rewarded_raw:
        if isinstance(rewarded_raw, str):
            state.rewarded_ids = json.loads(rewarded_raw)
        else:
            state.rewarded_ids = list(rewarded_raw)

    contents_raw = row.letter_contents
    if contents_raw:
        state.letter_contents = _unmarshal_contents(contents_raw)

    return state


def get_or_create_commander_love_letter_state(commander_id: int) -> CommanderLoveLetterStateData:
    with get_sync_session() as session:
        row = session.get(CommanderLoveLetterState, commander_id)
        if row is not None:
            return _row_to_state_data(row)
        now = datetime.now(timezone.utc)
        session.execute(
            text("""
                INSERT INTO commander_love_letter_states
                    (commander_id, medals, manual_letters, converted_items, rewarded_ids, letter_contents, created_at, updated_at)
                VALUES (:cid, '[]', '[]', '[]', '[]', '{}', :now, :now)
            """),
            {"cid": commander_id, "now": now},
        )
        session.commit()
        state = CommanderLoveLetterStateData()
        state.commander_id = commander_id
        state.created_at = now
        state.updated_at = now
        return state


def save_commander_love_letter_state(state: CommanderLoveLetterStateData):
    with get_sync_session() as session:
        session.execute(
            text("""
                UPDATE commander_love_letter_states SET
                    medals = :medals,
                    manual_letters = :manual_letters,
                    converted_items = :converted_items,
                    rewarded_ids = :rewarded_ids,
                    letter_contents = :letter_contents,
                    updated_at = NOW()
                WHERE commander_id = :cid
            """),
            {
                "cid": state.commander_id,
                "medals": json.dumps([m.to_dict() for m in state.medals], ensure_ascii=False),
                "manual_letters": json.dumps([m.to_dict() for m in state.manual_letters], ensure_ascii=False),
                "converted_items": json.dumps([c.to_dict() for c in state.converted_items], ensure_ascii=False),
                "rewarded_ids": json.dumps(state.rewarded_ids, ensure_ascii=False),
                "letter_contents": _marshal_contents(state.letter_contents),
            },
        )
        session.commit()


def delete_commander_love_letter_state(commander_id: int):
    with get_sync_session() as session:
        session.execute(
            text("DELETE FROM commander_love_letter_states WHERE commander_id = :cid"),
            {"cid": commander_id},
        )
        session.commit()


class CommanderLoveLetterState(Base):
    __tablename__ = 'commander_love_letter_states'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    medals: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    manual_letters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    converted_items: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    rewarded_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    letter_contents: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
