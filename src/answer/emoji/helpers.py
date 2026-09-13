from src.orm.config_entry import fetch_config_entries_data


def list_emoji_templates() -> list[dict]:
    rows = fetch_config_entries_data("ShareCfg/emoji_template.json")
    return [r for r in rows if isinstance(r, dict)]
