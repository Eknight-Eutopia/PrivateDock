from typing import Optional

from src.connection.client import Client
from src.consts.drop_types import DROP_TYPE_ITEM, DROP_TYPE_RESOURCE
from src.orm.mail import fetch_mails_with_attachments
from src.protobuf import protobuf

# Mail list request types (client GetMailListCommand): 1 = all/new,
# 2 = important, 3 = rare.
MAIL_TYPE_ALL = 1
MAIL_TYPE_IMPORTANT = 2
MAIL_TYPE_RARE = 3

# Resource ids that do NOT make a mail "rare" (client BaseMail.IsRare):
# gold/oil/merit(exploit) and the wisdom cube item.
_RARE_EXCLUDED_RESOURCE_IDS = frozenset({1, 2, 3})
_RARE_EXCLUDED_ITEM_IDS = frozenset({20001})  # ITEM_ID_CUBE


def bool_to_uint32(b: bool) -> int:
    return 1 if b else 0


def _is_rare_mail(mail: dict) -> bool:
    """Match the client's BaseMail.IsRare: has attachments AND at least one
    attachment that is not a plain resource (gold/oil/merit) or a cube."""
    attachments = mail.get("attachments", []) or []
    if not attachments:
        return False
    for att in attachments:
        t = att.get("type", 0)
        iid = att.get("item_id", 0)
        if t == DROP_TYPE_RESOURCE and iid in _RARE_EXCLUDED_RESOURCE_IDS:
            continue
        if t == DROP_TYPE_ITEM and iid in _RARE_EXCLUDED_ITEM_IDS:
            continue
        return True
    return False


def _filter_mails_by_type(mails: list, mail_type: int) -> list:
    """Return the mails that belong to the requested folder (1=all, 2=important, 3=rare)."""
    return [
        mail for mail in mails
        if not mail.get("is_archived", False)
        and (mail_type != MAIL_TYPE_IMPORTANT or mail.get("is_important", False))
        and (mail_type != MAIL_TYPE_RARE or _is_rare_mail(mail))
    ]


def mail_title_with_sender(mail: dict) -> str:
    title = mail.get("title", "")
    custom_sender = mail.get("custom_sender")
    if custom_sender:
        title += "||" + str(custom_sender)
    return title


def mail_to_mail_info(mail: dict) -> protobuf.MAIL_INFO:
    attachments = mail.get("attachments", []) or []
    attach_flag = mail.get("attachments_collected", False)
    if len(attachments) == 0:
        attach_flag = False
    else:
        attach_flag = not attach_flag
    full_title = mail_title_with_sender(mail)
    mail_date = mail.get("date", 0)
    if hasattr(mail_date, "timestamp"):
        # asyncpg returns the timestamp column as datetime
        import datetime
        if isinstance(mail_date, datetime.datetime):
            mail_date = int(mail_date.timestamp())
    elif isinstance(mail_date, str):
        import datetime
        try:
            dt = datetime.datetime.fromisoformat(mail_date.replace("Z", "+00:00"))
            mail_date = int(dt.timestamp())
        except Exception:
            mail_date = 0
    try:
        mail_date = int(mail_date or 0)
    except Exception:
        mail_date = 0
    info = protobuf.MAIL_INFO(
        id=mail.get("id", 0),
        date=mail_date,
        title=full_title,
        content=mail.get("body", ""),
        attach_flag=bool_to_uint32(attach_flag),
        read_flag=bool_to_uint32(mail.get("read", False)),
        imp_flag=bool_to_uint32(mail.get("is_important", False)),
    )
    for att in attachments:
        info.attachment_list.append(protobuf.DROPINFO(
            type=att.get("type", 0),
            id=att.get("item_id", 0),
            number=att.get("quantity", 0),
        ))
    return info


async def handle_send_mail_list(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_30002()
    payload.ParseFromString(buffer)

    try:
        mails = fetch_mails_with_attachments(client.commander.commander_id)
    except Exception as e:
        await client.send_message(30003, protobuf.SC_30003())
        return 0, 30003, e

    # Serve only the requested folder. type=2 (important) / type=3 (rare) must
    # return ONLY the flagged subset - otherwise every mail ends up in the
    # Important tab (client SetImportantMails uses the whole response).
    mail_type = int(getattr(payload, "type", MAIL_TYPE_ALL) or MAIL_TYPE_ALL)
    mails = _filter_mails_by_type(mails, mail_type)

    commander_mails_count = len(mails)
    if commander_mails_count == 0:
        await client.send_message(30003, protobuf.SC_30003())
        return 0, 30003, None

    index_end = payload.index_end
    if index_end == 0:
        index_end = commander_mails_count + 1

    index_begin = payload.index_begin
    if index_begin == 0:
        index_begin = 1
    index_begin = index_begin - 1

    resp = protobuf.SC_30003()
    for i in range(index_begin, min(commander_mails_count, index_end)):
        resp.mail_list.append(mail_to_mail_info(mails[i]))

    await client.send_message(30003, resp)
    return 0, 30003, None
