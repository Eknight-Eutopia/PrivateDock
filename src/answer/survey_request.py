import json
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from src.answer.survey_helpers import active_survey_activity, upsert_survey_state


async def handle_survey_request(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    payload = json.loads(buffer.decode("utf-8", errors="replace"))

    survey_id = payload.get("survey_id", 0)
    activity = await active_survey_activity(client.commander.level, survey_id)
    if activity is None or activity.get("survey_id") != survey_id:
        await client.send_message(11026, protobuf.SC_11026(result=1))
        return 0, 11026, None

    await upsert_survey_state(client.commander.commander_id, survey_id)
    await client.send_message(11026, protobuf.SC_11026(result=0))
    return 0, 11026, None
