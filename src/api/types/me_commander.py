from pydantic import BaseModel

class MeCommanderResponse(BaseModel):
    commander_id: int
    name: str
    level: int
