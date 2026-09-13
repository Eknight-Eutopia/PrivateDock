GUILD_CHAT_PLACEHOLDER_ID = 0


def build_guild_chat_player(commander: dict) -> dict:
    display = commander.get("display", commander)
    return {
        "id": commander.get("commander_id", 0),
        "name": commander.get("name", ""),
        "lv": commander.get("level", 0),
        "display": {
            "icon": display.get("display_icon_id", 0),
            "skin": display.get("display_skin_id", 0),
            "icon_frame": display.get("selected_icon_frame_id", 0),
            "chat_frame": display.get("selected_chat_frame_id", 0),
            "icon_theme": display.get("display_icon_theme_id", 0),
            "marry_flag": 0,
            "transform_flag": 0,
        },
    }
