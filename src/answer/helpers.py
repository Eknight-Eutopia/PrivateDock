

def bool_to_uint32(b: bool) -> int:
    return 1 if b else 0


def tb_info_placeholder() -> dict:
    return {
        "id": 0,
        "fsm": {
            "system_no": 0,
            "current_node": 0,
            "priority_fsm": [],
            "tarot_selects": [],
            "cache": [
                {
                    "cache_plan": [{"cur_index": 0, "plans": []}],
                    "cache_talent": [{"finished": 0, "talents": [], "retalents": []}],
                    "cache_site": [
                        {
                            "events": [],
                            "shops": [],
                            "buys": [],
                            "state": {"key": 0, "value": 0},
                            "character_this_round": [],
                            "refresh_count": 0,
                        }
                    ],
                    "cache_chat": [{"finished": 0, "chats": []}],
                    "cache_end": [{"ends": [], "select": 0}],
                    "cache_mind": [{}],
                    "cache_nin1": [],
                    "cache_affix_up": [],
                    "cache_tarot": [],
                    "cache_eval": [],
                }
            ],
        },
        "round": {"round": 1, "in_temp": 0, "temp_round": 0},
        "res": {"attrs": [], "resource": []},
        "talent": {"talents": []},
        "plan": {"plan_upgrade": []},
        "site": {"characters": [], "work_counter": [], "works": [], "event_counter": []},
        "evaluations": [],
        "name": "",
        "favor_lv": 0,
        "benefit": {"actives": []},
        "difficulty": 0,
        "eval_fail": 0,
        "display": empty_tb_display(),
    }


def tb_permanent_placeholder() -> dict:
    return {
        "ng_plus_count": 1,
        "polaroids": [],
        "endings": [],
        "active_endings": [],
        "tarot_archive": [],
        "max_round": 0,
    }


def empty_tb_display() -> dict:
    return {
        "benefit_display": [],
        "dollar_num_display": [],
        "counter": [],
    }


def push_new_ships(client, ships: list) -> None:
    pass


def merge_drop_list(drops: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for drop in drops:
        key = f"{drop.get('type', 0)}_{drop.get('id', 0)}"
        existing = merged.get(key)
        if existing is None:
            merged[key] = {
                "type": drop.get("type", 0),
                "id": drop.get("id", 0),
                "number": drop.get("number", 0),
            }
        else:
            existing["number"] = existing.get("number", 0) + drop.get("number", 0)
    out = list(merged.values())
    out.sort(key=lambda x: (x.get("type", 0), x.get("id", 0)))
    return out
