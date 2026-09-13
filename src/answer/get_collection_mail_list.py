from typing import Optional

from src.connection.client import Client
from src.orm.mail import afetch_mails_with_attachments
from src.protobuf import protobuf


def mail_to_simple_mail_info(mail: dict) -> protobuf.MAIL_SIMPLE_INFO:
    attachments = mail.get("attachments", []) or []
    mail_date = mail.get("date", 0)
    if isinstance(mail_date, str):
        import datetime
        try:
            dt = datetime.datetime.fromisoformat(mail_date.replace("Z", "+00:00"))
            mail_date = int(dt.timestamp())
        except Exception:
            mail_date = 0
    info = protobuf.MAIL_SIMPLE_INFO(
        id=mail.get("id", 0),
        date=mail_date,
        title=mail.get("title", ""),
        content=mail.get("body", ""),
    )
    for att in attachments:
        info.attachment_list.append(protobuf.DROPINFO(
            type=att.get("type", 0),
            id=att.get("item_id", 0),
            number=att.get("quantity", 0),
        ))
    return info


async def handle_get_collection_mail_list(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_30004()
    payload.ParseFromString(buffer)

    try:
        mails = await afetch_mails_with_attachments(client.commander.commander_id, archived_only=True)
    except Exception as e:
        await client.send_message(30005, protobuf.SC_30005())
        return 0, 30005, e

    commander_mails_count = len(mails)
    if commander_mails_count == 0:
        await client.send_message(30005, protobuf.SC_30005())
        return 0, 30005, None

    index_end = payload.index_end
    if index_end == 0:
        index_end = commander_mails_count + 1

    index_begin = payload.index_begin
    if index_begin == 0:
        index_begin = 1
    index_begin = index_begin - 1

    resp = protobuf.SC_30005()
    for i in range(index_begin, min(commander_mails_count, index_end)):
        resp.mail_list.append(mail_to_simple_mail_info(mails[i]))

    await client.send_message(30005, resp)
    return 0, 30005, None