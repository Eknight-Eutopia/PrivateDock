from typing import Optional

from pydantic import BaseModel

from src.api.types.player import PaginationMeta





class JuustagramChatGroupCreateRequest(BaseModel):
    chat_group_id: int
    op_time: int = 0





class JuustagramChatReadRequest(BaseModel):
    chat_group_ids: list[int] = []




class JuustagramChatReplyRequest(BaseModel):
    chat_id: int
    value: int = 0





class JuustagramGroupCreateRequest(BaseModel):
    group_id: int
    chat_group_id: int = 0
    skin_id: int = 0
    favorite: int = 0





class JuustagramGroupUpdateRequest(BaseModel):
    skin_id: Optional[int] = None
    favorite: Optional[int] = None
    cur_chat_group: Optional[int] = None





class JuustagramReply(BaseModel):
    sequence: int = 0
    key: int = 0
    value: int = 0





class JuustagramChatGroup(BaseModel):
    chat_group_id: int = 0
    op_time: int = 0
    read_flag: int = 0
    reply_list: list[JuustagramReply] = []





class JuustagramGroup(BaseModel):
    group_id: int = 0
    skin_id: int = 0
    favorite: int = 0
    cur_chat_group: int = 0
    chat_groups: list[JuustagramChatGroup] = []





class JuustagramGroupListResponse(BaseModel):
    groups: list[JuustagramGroup] = []
    meta: PaginationMeta = PaginationMeta()





class JuustagramGroupResponse(BaseModel):
    group: JuustagramGroup



