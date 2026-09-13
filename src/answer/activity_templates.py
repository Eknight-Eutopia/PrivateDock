from typing import Any, Optional


class ActivityTemplate:
    def __init__(self, data: dict):
        self.id: int = data.get("id", 0)
        self.type: int = data.get("type", 0)
        self.config_id: int = data.get("config_id", 0)
        self.time: Any = data.get("time")
        self.config_client: Any = data.get("config_client")
        self.config_data: Any = data.get("config_data")


def load_activity_template(activity_id: int) -> Optional[ActivityTemplate]:
    from src.orm.config_entry import get_config_entry
    raw = get_config_entry("ShareCfg/activity_template.json", str(activity_id))
    return ActivityTemplate(raw.data) if raw else None
