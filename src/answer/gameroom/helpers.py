import json
from datetime import datetime, timezone, timedelta

from src.db.store import get_default_store
from src.orm.config_entry import fetch_config_entries_data, fetch_config_entry_data

GAME_ROOM_COIN_RESOURCE_ID = 11
GAME_ROOM_TICKET_RESOURCE_ID = 12


def load_game_room_templates():
    rows = fetch_config_entries_data("ShareCfg/game_room_template.json")
    templates = [d for d in rows if isinstance(d, dict)]
    templates.sort(key=lambda t: t.get("id", 0))
    return templates


def load_game_room_template_ids():
    return [t["id"] for t in load_game_room_templates()]


def load_game_room_template(room_id: int):
    for t in load_game_room_templates():
        if t.get("id") == room_id:
            return t, True, None
    return None, False, None


def load_game_room_gameset_value(key: str) -> int:
    entry = fetch_config_entry_data("ShareCfg/gameset.json", key)
    if not isinstance(entry, dict):
        return 0
    return entry.get("key_value", 0)


def load_game_room_settings():
    coin_initial = load_game_room_gameset_value("game_coin_initial")
    coin_max = load_game_room_gameset_value("game_coin_max")
    ticket_monthly_max = load_game_room_gameset_value("game_ticket_month")
    ticket_total_max = load_game_room_gameset_value("game_room_remax")

    entry = fetch_config_entry_data("ShareCfg/gameset.json", "game_coin_gold")
    tiers = []
    if isinstance(entry, dict):
        desc = entry.get("description", "[]")
        if isinstance(desc, str):
            desc = json.loads(desc)
        tiers = parse_game_room_coin_gold_tiers(desc)

    return {
        "coin_initial": coin_initial,
        "coin_max": coin_max,
        "ticket_monthly_max": ticket_monthly_max,
        "ticket_total_max": ticket_total_max,
        "coin_gold_tiers": tiers,
    }


def parse_game_room_coin_gold_tiers(raw):
    tiers = []
    for entry in raw:
        if len(entry) >= 2:
            tiers.append({"threshold": entry[0], "price": entry[1]})
    tiers.sort(key=lambda t: t["threshold"])
    return tiers


def game_room_exchange_price_by_count(tiers, count: int) -> int:
    if not tiers:
        return 0
    price = tiers[0]["price"]
    for tier in tiers:
        if count >= tier["threshold"]:
            price = tier["price"]
    return price


def game_room_multiplier_for_score(thresholds, score: int) -> float:
    if not thresholds:
        return 0.0
    best_threshold = 0
    multiplier = thresholds[0][1]
    for entry in thresholds:
        if len(entry) < 2:
            continue
        threshold = int(entry[0])
        if score >= threshold and threshold >= best_threshold:
            best_threshold = threshold
            multiplier = entry[1]
    return multiplier


def game_room_month_key(now=None) -> int:
    if now is None:
        now = datetime.now(timezone.utc)
    return now.year * 100 + now.month


from src.shopreset.framework import current_weekly_reset_unix


def load_game_room_state(commander_id: int, now=None):
    if now is None:
        now = datetime.now(timezone.utc)
    week_start_unix = current_weekly_reset_unix(now)
    month_key = game_room_month_key(now)

    store = get_default_store()
    row = store.fetchrow(
        """SELECT week_start_unix, weekly_claimed, pay_coin_count,
           first_enter_claimed, month_key, monthly_ticket
           FROM game_room_states
           WHERE commander_id = $1""",
        commander_id
    )

    if row is None:
        state = {
            "commander_id": commander_id,
            "week_start_unix": week_start_unix,
            "weekly_claimed": False,
            "pay_coin_count": 0,
            "first_enter_claimed": False,
            "month_key": month_key,
            "monthly_ticket": 0,
        }
        store.execute(
            """INSERT INTO game_room_states
               (commander_id, week_start_unix, weekly_claimed, pay_coin_count,
                first_enter_claimed, month_key, monthly_ticket)
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            commander_id, week_start_unix, False, 0, False, month_key, 0
        )
        return state

    state = {
        "commander_id": commander_id,
        "week_start_unix": row["week_start_unix"],
        "weekly_claimed": bool(row["weekly_claimed"]),
        "pay_coin_count": row["pay_coin_count"],
        "first_enter_claimed": bool(row["first_enter_claimed"]),
        "month_key": row["month_key"],
        "monthly_ticket": row["monthly_ticket"],
    }

    dirty = False
    if state["week_start_unix"] != week_start_unix:
        state["week_start_unix"] = week_start_unix
        state["weekly_claimed"] = False
        state["pay_coin_count"] = 0
        dirty = True
    if state["month_key"] != month_key:
        state["month_key"] = month_key
        state["monthly_ticket"] = 0
        dirty = True

    if dirty:
        save_game_room_state(state)

    return state


async def load_game_room_state_for_update(commander_id: int, now=None):
    return load_game_room_state(commander_id, now)


def list_game_room_scores(commander_id: int):
    store = get_default_store()
    rows = store.fetch(
        "SELECT room_id, max_score FROM game_room_scores WHERE commander_id = $1",
        commander_id
    )
    return [{"room_id": r["room_id"], "max_score": r["max_score"]} for r in rows]


def save_game_room_state(state):
    store = get_default_store()
    store.execute(
        """UPDATE game_room_states
           SET week_start_unix = $2, weekly_claimed = $3, pay_coin_count = $4,
               first_enter_claimed = $5, month_key = $6, monthly_ticket = $7,
               updated_at = CURRENT_TIMESTAMP
           WHERE commander_id = $1""",
        state["commander_id"], state["week_start_unix"], state["weekly_claimed"],
        state["pay_coin_count"], state["first_enter_claimed"],
        state["month_key"], state["monthly_ticket"]
    )


def upsert_game_room_score(commander_id: int, room_id: int, score: int):
    store = get_default_store()
    store.execute(
        """INSERT INTO game_room_scores (commander_id, room_id, max_score)
           VALUES ($1, $2, $3)
           ON CONFLICT (commander_id, room_id)
           DO UPDATE SET max_score = GREATEST(game_room_scores.max_score, EXCLUDED.max_score),
                         updated_at = CURRENT_TIMESTAMP""",
        commander_id, room_id, score
    )


def consume_commander_gold(commander_id: int, amount: int) -> bool:
    store = get_default_store()
    row = store.fetchrow(
        "SELECT coin FROM commanders WHERE commander_id = $1",
        commander_id
    )
    if row is None or row["coin"] < amount:
        return False
    store.execute(
        "UPDATE commanders SET coin = coin - $1 WHERE commander_id = $2",
        amount, commander_id
    )
    return True


def add_commander_resource(commander_id: int, resource_id: int, amount: int):
    from src.orm.resource import add_resource
    add_resource(commander_id, resource_id, amount)


def consume_commander_resource(commander_id: int, resource_id: int, amount: int) -> bool:
    from src.orm.resource import get_owned_resource_amount, consume_resource
    curr = get_owned_resource_amount(commander_id, resource_id)
    if curr < amount:
        return False
    consume_resource(commander_id, resource_id, amount)
    return True

