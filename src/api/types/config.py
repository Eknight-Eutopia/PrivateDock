from typing import Any

from pydantic import BaseModel






class ConfigEntryMutationRequest(BaseModel):
    category: str
    key: str
    data: Any






class ConfigEntryPayload(BaseModel):
    id: int
    category: str
    key: str
    data: Any






class ConfigEntryListResponse(BaseModel):
    entries: list[ConfigEntryPayload]


