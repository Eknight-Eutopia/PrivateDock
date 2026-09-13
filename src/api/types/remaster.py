from typing import Optional

from pydantic import BaseModel





class PlayerRemasterProgressCreateRequest(BaseModel):
    chapter_id: int
    pos: int
    count: int = 0
    received: Optional[bool] = None





class PlayerRemasterProgressEntry(BaseModel):
    chapter_id: int = 0
    pos: int = 0
    count: int = 0
    received: bool = False
    updated_at: str = ""





class PlayerRemasterProgressResponse(BaseModel):
    progress: list[PlayerRemasterProgressEntry] = []





class PlayerRemasterProgressUpdateRequest(BaseModel):
    count: Optional[int] = None
    received: Optional[bool] = None




class PlayerRemasterStateResponse(BaseModel):
    ticket_count: int = 0
    daily_count: int = 0
    last_daily_reset_at: str = ""





class PlayerRemasterStateUpdateRequest(BaseModel):
    ticket_count: Optional[int] = None
    daily_count: Optional[int] = None
    last_daily_reset_at: Optional[str] = None



