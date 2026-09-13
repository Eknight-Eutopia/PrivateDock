import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from .helpers import mark_mail_read, delete_mail


def handle_ask_mail_body(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_30008()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 30009, e

    mail_id = payload.mail_id
    response = protobuf.SC_30009()
    response.result = 0

    if hasattr(client.commander, "mails_map") and client.commander.mails_map is not None:
        mail = client.commander.mails_map.get(mail_id)
        if mail is None:
            response.result = 1
        else:
            commander_id = getattr(client.commander, "commander_id", 0)
            if not mark_mail_read(commander_id, mail_id):
                response.result = 1
    else:
        response.result = 1

    asyncio.create_task(client.send_message(30009, response))
    return 0, 30009, None


def handle_delete_archived_mail(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_30008()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 30009, e

    mail_id = payload.mail_id
    response = protobuf.SC_30009()
    response.result = 0

    commander_id = getattr(client.commander, "commander_id", 0)
    if hasattr(client.commander, "mails_map") and client.commander.mails_map is not None:
        mail = client.commander.mails_map.get(mail_id)
        if mail is None or not delete_mail(commander_id, mail_id):
            response.result = 1
    else:
        response.result = 1

    asyncio.create_task(client.send_message(30009, response))
    return 0, 30009, None
