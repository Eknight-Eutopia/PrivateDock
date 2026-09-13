from typing import Any

from pydantic import BaseModel

class CommanderTBPayload(BaseModel):
    commander_id: int = 0
    tb: Any = None
    permanent: Any = None

class CommanderTBRequest(BaseModel):
    tb: Any = None
    permanent: Any = None
