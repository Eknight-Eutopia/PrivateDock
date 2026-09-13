from typing import Any, Optional

from pydantic import BaseModel


class PlayerLoveLetterStateResponse(BaseModel):
    medals: list[Any]
    manual_letters: list[Any]
    converted_items: list[Any]
    rewarded_ids: list[int]
    letter_contents: dict[str, str]


class PlayerLoveLetterStateUpdateRequest(BaseModel):
    medals: Optional[list[Any]] = None
    manual_letters: Optional[list[Any]] = None
    converted_items: Optional[list[Any]] = None
    rewarded_ids: Optional[list[int]] = None
    letter_contents: Optional[dict[str, str]] = None
