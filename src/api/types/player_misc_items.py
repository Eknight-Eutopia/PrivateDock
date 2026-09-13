
from pydantic import BaseModel



class PlayerMiscItemEntry(BaseModel):
    item_id: int = 0
    data: int = 0
    name: str = ""



class PlayerMiscItemResponse(BaseModel):
    items: list[PlayerMiscItemEntry] = []



class PlayerMiscItemUpdateRequest(BaseModel):
    data: int

