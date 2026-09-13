import json
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from src.db.store import get_default_store
from src.answer.survey_helpers import active_survey_activity


async def handle_survey_state(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    payload = json.loads(buffer.decode("utf-8", errors="replace"))

    survey_id = payload.get("survey_id", 0)
    activity = await active_survey_activity(client.commander.level, survey_id)
    if activity is None or activity.get("survey_id") != survey_id:
        await client.send_message(11028, protobuf.SC_11028(result=0))
        return 0, 11028, None

    store = get_default_store()
    if store is None:
        await client.send_message(11028, protobuf.SC_11028(result=0))
        return 0, 11028, None

    result = 0
    try:
        row = await store.afetchrow(
            "SELECT survey_id FROM survey_states WHERE commander_id = $1",
            client.commander.commander_id,
        )
        stored_survey_id = row["survey_id"] if row else None
    except Exception:
        await client.send_message(11028, protobuf.SC_11028(result=0))
        return 0, 11028, None

    if stored_survey_id == survey_id:
        result = survey_id

    await client.send_message(11028, protobuf.SC_11028(result=result))
    return 0, 11028, None
