import asyncio
import json
from typing import Optional

from src.db.store import get_default_store
from src.orm.commander_common_flag import clear_commander_common_flag, set_commander_common_flag
from src.orm.config_entry import fetch_config_entry_data
from src.protobuf import protobuf

GUILD_DUTY_COMMANDER = 1
GUILD_DUTY_DEPUTY = 2
GUILD_DUTY_ORDINARY = 3
GUILD_DUTY_RECRUIT = 4


def send_common_flag_push(client, flag_id: int, enabled: bool) -> None:
    response = protobuf.SC_11802()
    response.id = flag_id
    response.value = 1 if enabled else 0
    asyncio.create_task(client.send_message(11802, response))


get_config_entry = fetch_config_entry_data



def add_commander_story(commander_id: int, story_id: int) -> None:
    store = get_default_store()
    store.execute(
        "INSERT INTO commander_stories (commander_id, story_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
        commander_id, story_id
    )


def commander_has_living_area_cover(commander_id: int, cover_id: int) -> bool:
    store = get_default_store()
    row = store.fetchrow(
        "SELECT cover_id FROM commander_living_area_covers WHERE commander_id = $1 AND cover_id = $2",
        commander_id, cover_id
    )
    return row is not None


def is_valid_guild_duty(duty: int) -> bool:
    return duty in (GUILD_DUTY_COMMANDER, GUILD_DUTY_DEPUTY, GUILD_DUTY_ORDINARY, GUILD_DUTY_RECRUIT)


def update_guild_duty(commander_id: int, target_commander_id: int, duty: int) -> Optional[Exception]:
    if not is_valid_guild_duty(duty):
        return Exception("invalid guild duty")
    if commander_id == target_commander_id:
        return Exception("cannot target self")

    async def _do_update():
        store = get_default_store()
        actor_row = await store.afetchrow(
            "SELECT guild_id, duty FROM guild_members WHERE commander_id = $1",
            commander_id
        )
        if actor_row is None:
            return
        actor_guild_id = actor_row["guild_id"]
        actor_duty = actor_row["duty"]

        target_row = await store.afetchrow(
            "SELECT guild_id, commander_id FROM guild_members WHERE commander_id = $1",
            target_commander_id
        )
        if target_row is None:
            return
        target_guild_id = target_row["guild_id"]

        if actor_guild_id != target_guild_id:
            return

        if actor_duty != GUILD_DUTY_COMMANDER:
            return

        if duty == GUILD_DUTY_DEPUTY:
            guild_row = await store.afetchrow(
                "SELECT id, level FROM guilds WHERE id = $1",
                actor_guild_id
            )
            if guild_row is None:
                return
            guild_level = guild_row["level"]
            limit = guild_level * 2 + 1
            count_row = await store.afetchrow(
                "SELECT COUNT(*) AS cnt FROM guild_members WHERE guild_id = $1 AND duty = $2",
                actor_guild_id, GUILD_DUTY_DEPUTY
            )
            count = count_row["cnt"] if count_row else 0
            if target_row["commander_id"] != target_commander_id or count >= limit:
                return

        if duty == GUILD_DUTY_COMMANDER:
            target_duty_row = await store.afetchrow(
                "SELECT duty FROM guild_members WHERE commander_id = $1 AND guild_id = $2",
                target_commander_id, actor_guild_id
            )
            if target_duty_row is None or target_duty_row["duty"] != GUILD_DUTY_DEPUTY:
                return
            await store.aexecute(
                "UPDATE guild_members SET duty = $3 WHERE guild_id = $1 AND commander_id = $2",
                actor_guild_id, commander_id, GUILD_DUTY_DEPUTY
            )

        await store.aexecute(
            "UPDATE guild_members SET duty = $3 WHERE guild_id = $1 AND commander_id = $2",
            actor_guild_id, target_commander_id, duty
        )

    asyncio.create_task(_do_update())
    return None
