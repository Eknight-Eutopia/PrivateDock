from fastapi import APIRouter, Request

from src.api.handlers.juustagram import (
    list_templates, template_detail, create_template, update_template, delete_template,
    list_npc_templates, npc_template_detail, create_npc_template, update_npc_template, delete_npc_template,
    list_ship_groups, ship_group_detail, create_ship_group, update_ship_group, delete_ship_group,
    list_language, language_detail, create_language, update_language, delete_language,
    list_messages, message_detail, update_message,
    list_message_states, message_state_detail, update_message_state, delete_message_state,
    list_player_discuss, get_player_discuss, update_player_discuss, discuss_message,
    list_player_groups, get_player_group, create_player_group, update_player_group, delete_player_group,
    create_chat_group, delete_chat_group, create_chat_reply, delete_chat_reply, mark_chat_groups_read,
)

router = APIRouter(prefix="/api/v1/juustagram", tags=["juustagram"])
player_router = APIRouter(prefix="/api/v1/players/{player_id}/juustagram", tags=["juustagram_player"])


@router.get("/templates")
async def list_templates_route(req: Request):
    return await list_templates(req)


@router.get("/templates/{id}")
async def template_detail_route(req: Request):
    return await template_detail(req)


@router.post("/templates")
async def create_template_route(req: Request):
    return await create_template(req)


@router.put("/templates")
async def update_template_route(req: Request):
    return await update_template(req)


@router.delete("/templates")
async def delete_template_route(req: Request):
    return await delete_template(req)


@router.get("/npc-templates")
async def list_npc_templates_route(req: Request):
    return await list_npc_templates(req)


@router.get("/npc-templates/{id}")
async def npc_template_detail_route(req: Request):
    return await npc_template_detail(req)


@router.post("/npc-templates")
async def create_npc_template_route(req: Request):
    return await create_npc_template(req)


@router.put("/npc-templates")
async def update_npc_template_route(req: Request):
    return await update_npc_template(req)


@router.delete("/npc-templates")
async def delete_npc_template_route(req: Request):
    return await delete_npc_template(req)


@router.get("/ship-groups")
async def list_ship_groups_route(req: Request):
    return await list_ship_groups(req)


@router.get("/ship-groups/{id}")
async def ship_group_detail_route(req: Request):
    return await ship_group_detail(req)


@router.post("/ship-groups")
async def create_ship_group_route(req: Request):
    return await create_ship_group(req)


@router.put("/ship-groups")
async def update_ship_group_route(req: Request):
    return await update_ship_group(req)


@router.delete("/ship-groups")
async def delete_ship_group_route(req: Request):
    return await delete_ship_group(req)


@router.get("/language")
async def list_language_route(req: Request):
    return await list_language(req)


@router.get("/language/{key}")
async def language_detail_route(req: Request):
    return await language_detail(req)


@router.post("/language")
async def create_language_route(req: Request):
    return await create_language(req)


@router.put("/language")
async def update_language_route(req: Request):
    return await update_language(req)


@router.delete("/language")
async def delete_language_route(req: Request):
    return await delete_language(req)


@router.get("/messages")
async def list_messages_route(req: Request):
    return await list_messages(req)


@router.get("/messages/{message_id}")
async def message_detail_route(req: Request):
    return await message_detail(req)


@router.patch("/messages/{message_id}")
async def update_message_route(req: Request):
    return await update_message(req)


@router.get("/message-states")
async def list_message_states_route(req: Request):
    return await list_message_states(req)


@router.get("/message-states/{message_id}")
async def message_state_detail_route(req: Request):
    return await message_state_detail(req)


@router.put("/message-states/{message_id}")
async def update_message_state_route(req: Request):
    return await update_message_state(req)


@router.delete("/message-states/{message_id}")
async def delete_message_state_route(req: Request):
    return await delete_message_state(req)


@player_router.get("/messages")
async def list_messages_player_route(req: Request):
    return await list_messages(req)


@player_router.get("/messages/{message_id}")
async def message_detail_player_route(req: Request):
    return await message_detail(req)


@player_router.patch("/messages/{message_id}")
async def update_message_player_route(req: Request):
    return await update_message(req)


@player_router.get("/message-states")
async def list_message_states_player_route(req: Request):
    return await list_message_states(req)


@player_router.get("/message-states/{message_id}")
async def message_state_detail_player_route(req: Request):
    return await message_state_detail(req)


@player_router.put("/message-states/{message_id}")
async def update_message_state_player_route(req: Request):
    return await update_message_state(req)


@player_router.delete("/message-states/{message_id}")
async def delete_message_state_player_route(req: Request):
    return await delete_message_state(req)


@player_router.get("/discuss")
async def list_player_discuss_route(req: Request):
    return await list_player_discuss(req)


@player_router.get("/discuss/{discuss_id}")
async def get_player_discuss_route(req: Request):
    return await get_player_discuss(req)


@player_router.put("/discuss/{discuss_id}")
async def update_player_discuss_route(req: Request):
    return await update_player_discuss(req)


@player_router.post("/discuss/{discuss_id}/discuss")
async def discuss_message_route(req: Request):
    return await discuss_message(req)


@player_router.get("/groups")
async def list_player_groups_route(req: Request):
    return await list_player_groups(req)


@player_router.get("/groups/{group_id}")
async def get_player_group_route(req: Request):
    return await get_player_group(req)


@player_router.post("/groups")
async def create_player_group_route(req: Request):
    return await create_player_group(req)


@player_router.patch("/groups/{group_id}")
async def update_player_group_route(req: Request):
    return await update_player_group(req)


@player_router.delete("/groups/{group_id}")
async def delete_player_group_route(req: Request):
    return await delete_player_group(req)


@player_router.post("/groups/{group_id}/chat-groups")
async def create_chat_group_route(req: Request):
    return await create_chat_group(req)


@player_router.delete("/chat-groups/{chat_group_id}")
async def delete_chat_group_route(req: Request):
    return await delete_chat_group(req)


@player_router.post("/chat-groups/{chat_group_id}/reply")
async def create_chat_reply_route(req: Request):
    return await create_chat_reply(req)


@player_router.delete("/chat-groups/{chat_group_id}/replies/{sequence}")
async def delete_chat_reply_route(req: Request):
    return await delete_chat_reply(req)


@player_router.patch("/chat-groups/read")
async def mark_chat_groups_read_route(req: Request):
    return await mark_chat_groups_read(req)
