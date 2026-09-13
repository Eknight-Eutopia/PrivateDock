import asyncio
import json
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from src.db.session import get_sync_session
from src.orm.exchange_code import get_exchange_code_redeem
from src.orm.mail import create_mail_sync, create_mail_attachment_sync
from sqlalchemy import text

from src.consts.drop_types import (
    DROP_TYPE_ITEM,
    DROP_TYPE_RESOURCE,
    DROP_TYPE_SHIP,
    DROP_TYPE_SKIN,
)


def build_exchange_attachments(rewards: list) -> Optional[list]:
    attachments = []
    for reward in rewards:
        rtype = reward.get("type", 0)
        rid = reward.get("id", 0)
        count = reward.get("count", 0)
        if rtype in (DROP_TYPE_RESOURCE, DROP_TYPE_ITEM, DROP_TYPE_SHIP, DROP_TYPE_SKIN):
            attachments.append({"type": rtype, "item_id": rid, "quantity": count})
        else:
            return None
    return attachments if attachments else None


def handle_exchange_code_redeem(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    PACKET_ID = 11509
    try:
        payload = protobuf.CS_11508()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, PACKET_ID, e

    response = protobuf.SC_11509(result=1)
    key = payload.key.strip() if payload.key else ""
    if not key:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    platform = payload.platform.strip() if payload.platform else ""
    normalized_key = key.upper()

    with get_sync_session() as session:
        row = session.execute(
            text("SELECT id, code, platform, quota, rewards FROM exchange_codes WHERE upper(code) = :key"),
            {"key": normalized_key},
        ).mappings().first()
        if row is None:
            session.commit()
            asyncio.create_task(client.send_message(PACKET_ID, response))
            return 0, PACKET_ID, None

        code_id = row["id"]
        code_platform = row["platform"] or ""
        code_quota = row["quota"]
        rewards_raw = row["rewards"]

    if code_platform and code_platform.lower() != platform.lower():
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    if get_exchange_code_redeem(code_id, client.commander.commander_id) is not None:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    quota_limited = code_quota >= 0
    if quota_limited and code_quota == 0:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    if rewards_raw is None:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    if isinstance(rewards_raw, str):
        rewards = json.loads(rewards_raw)
    else:
        rewards = rewards_raw
    attachments = build_exchange_attachments(rewards)
    if attachments is None:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    try:
        with get_sync_session() as session:
            session.execute(
                text("""INSERT INTO exchange_code_redeems (exchange_code_id, commander_id, redeemed_at)
                        VALUES (:ecid, :cid, NOW())"""),
                {"ecid": code_id, "cid": client.commander.commander_id},
            )
            if quota_limited:
                result = session.execute(
                    text("""UPDATE exchange_codes SET quota = quota - 1, updated_at = NOW()
                            WHERE id = :id AND quota > 0"""),
                    {"id": code_id},
                )
                if result.rowcount == 0:
                    raise RuntimeError("quota depleted")
            session.commit()
    except Exception:
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    try:
        mail_id = create_mail_sync(
            client.commander.commander_id,
            "Exchange Code Rewards",
            "Your exchange code rewards are attached.",
            None,
        )
        for att in attachments:
            create_mail_attachment_sync(mail_id, att["type"], att["item_id"], att["quantity"])
        # Refresh the mailbox badge / totals so the new mail appears.
        try:
            from src.answer.mailbox import push_mail_count_sync
            push_mail_count_sync(client)
        except Exception:
            pass
    except Exception:
        with get_sync_session() as session:
            if quota_limited:
                session.execute(
                    text("UPDATE exchange_codes SET quota = quota + 1, updated_at = NOW() WHERE id = :id"),
                    {"id": code_id},
                )
            session.execute(
                text("""DELETE FROM exchange_code_redeems
                        WHERE exchange_code_id = :ecid AND commander_id = :cid"""),
                {"ecid": code_id, "cid": client.commander.commander_id},
            )
            session.commit()
        asyncio.create_task(client.send_message(PACKET_ID, response))
        return 0, PACKET_ID, None

    response.result = 0
    asyncio.create_task(client.send_message(PACKET_ID, response))
    return 0, PACKET_ID, None
