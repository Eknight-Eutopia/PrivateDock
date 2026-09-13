from __future__ import annotations
from datetime import datetime
from typing import Any, Optional, Sequence

from sqlalchemy import BigInteger, Boolean, DateTime, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session
from src.db.store import get_default_store
from src.orm.mail_attachment import fetch_mail_attachments, afetch_mail_attachments


class Mail(Base):
    __tablename__ = 'mails'
    __table_args__ = {}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    receiver_id: Mapped[int] = mapped_column(BigInteger)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    attachments_collected: Mapped[bool] = mapped_column(Boolean, default=False)
    is_important: Mapped[bool] = mapped_column(Boolean, default=False)
    custom_sender: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


async def afetch_mails(commander_id: int, archived_only: bool = False) -> list[dict[str, Any]]:
    store = get_default_store()
    if store is None:
        return []
    query = (
        "SELECT id, receiver_id, read, date, title, body, "
        "attachments_collected, is_important, custom_sender, is_archived "
        "FROM mails WHERE receiver_id = $1"
    )
    if archived_only:
        query += " AND is_archived = true"
    query += " ORDER BY id"
    try:
        rows = await store.afetch(query, commander_id)
        return [dict(r) for r in rows]
    except Exception:
        return []


def fetch_mails(commander_id: int, archived_only: bool = False) -> list[dict[str, Any]]:
    store = get_default_store()
    if store is None:
        return []
    query = (
        "SELECT id, receiver_id, read, date, title, body, "
        "attachments_collected, is_important, custom_sender, is_archived "
        "FROM mails WHERE receiver_id = $1"
    )
    if archived_only:
        query += " AND is_archived = true"
    query += " ORDER BY id"
    try:
        rows = store.fetch(query, commander_id)
        return [dict(r) for r in rows]
    except Exception:
        return []


async def afetch_mails_with_attachments(commander_id: int, archived_only: bool = False) -> list[dict[str, Any]]:
    mails = await afetch_mails(commander_id, archived_only=archived_only)
    mail_ids = [m["id"] for m in mails]
    if mail_ids:
        att_rows = await afetch_mail_attachments(mail_ids)
        att_map: dict[int, list[dict[str, Any]]] = {}
        for a in att_rows:
            mid = a["mail_id"]
            if mid not in att_map:
                att_map[mid] = []
            att_map[mid].append(a)
        for m in mails:
            m["attachments"] = att_map.get(m["id"], [])
    else:
        for m in mails:
            m["attachments"] = []
    return mails


def fetch_mails_with_attachments(commander_id: int, archived_only: bool = False) -> list[dict[str, Any]]:
    mails = fetch_mails(commander_id, archived_only=archived_only)
    mail_ids = [m["id"] for m in mails]
    if mail_ids:
        att_rows = fetch_mail_attachments(mail_ids)
        att_map: dict[int, list[dict[str, Any]]] = {}
        for a in att_rows:
            mid = a["mail_id"]
            if mid not in att_map:
                att_map[mid] = []
            att_map[mid].append(a)
        for m in mails:
            m["attachments"] = att_map.get(m["id"], [])
    else:
        for m in mails:
            m["attachments"] = []
    return mails


def get_mailbox_counts(commander_id: int) -> tuple[int, int]:
    store = get_default_store()
    if store is None:
        return 0, 0
    try:
        rows = store.fetch(
            "SELECT read FROM mails WHERE receiver_id = $1 AND is_archived = false",
            commander_id,
        )
        total = len(rows)
        unread = sum(1 for r in rows if not r[0])
        return total, unread
    except Exception:
        return 0, 0


async def aget_mailbox_counts(commander_id: int) -> tuple[int, int]:
    store = get_default_store()
    if store is None:
        return 0, 0
    try:
        rows = await store.afetch(
            "SELECT read FROM mails WHERE receiver_id = $1 AND is_archived = false",
            commander_id,
        )
        total = len(rows)
        unread = sum(1 for r in rows if not r[0])
        return total, unread
    except Exception:
        return 0, 0


async def aupdate_mail_field(commander_id: int, mail_id: int, field: str, value: Any) -> None:
    allowed = {"read", "is_important", "is_archived", "attachments_collected"}
    if field not in allowed:
        return
    store = get_default_store()
    if store is None:
        return
    try:
        await store.aexecute(
            f"UPDATE mails SET {field} = $1 WHERE id = $2 AND receiver_id = $3",
            value, mail_id, commander_id,
        )
    except Exception:
        pass


def update_mail_field(commander_id: int, mail_id: int, field: str, value: Any) -> None:
    allowed = {"read", "is_important", "is_archived", "attachments_collected"}
    if field not in allowed:
        return
    store = get_default_store()
    if store is None:
        return
    try:
        store.execute(
            f"UPDATE mails SET {field} = $1 WHERE id = $2 AND receiver_id = $3",
            value, mail_id, commander_id,
        )
    except Exception:
        pass


async def adelete_mails(commander_id: int, mail_ids: Sequence[int]) -> None:
    if not mail_ids:
        return
    store = get_default_store()
    if store is None:
        return
    try:
        await store.aexecute(
            "DELETE FROM mails WHERE receiver_id = $1 AND id = ANY($2::bigint[])",
            commander_id, list(mail_ids),
        )
    except Exception:
        pass


def delete_mails(commander_id: int, mail_ids: Sequence[int]) -> None:
    if not mail_ids:
        return
    store = get_default_store()
    if store is None:
        return
    try:
        store.execute(
            "DELETE FROM mails WHERE receiver_id = $1 AND id = ANY($2::bigint[])",
            commander_id, list(mail_ids),
        )
    except Exception:
        pass


def fetch_mail_titles(commander_id: int, mail_ids: Sequence[int]) -> list[dict[str, Any]]:
    if not mail_ids:
        return []
    store = get_default_store()
    if store is None:
        return []
    try:
        rows = store.fetch(
            "SELECT id, title, custom_sender FROM mails WHERE receiver_id = $1 AND id = ANY($2::bigint[]) ORDER BY id",
            commander_id, list(mail_ids),
        )
        return [dict(r) for r in rows]
    except Exception:
        return []


async def afetch_mail_titles(commander_id: int, mail_ids: Sequence[int]) -> list[dict[str, Any]]:
    if not mail_ids:
        return []
    store = get_default_store()
    if store is None:
        return []
    try:
        rows = await store.afetch(
            "SELECT id, title, custom_sender FROM mails WHERE receiver_id = $1 AND id = ANY($2::bigint[]) ORDER BY id",
            commander_id, list(mail_ids),
        )
        return [dict(r) for r in rows]
    except Exception:
        return []



async def list_mails_for_commander(commander_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, receiver_id, read, date, title, body, attachments_collected, is_important, custom_sender, is_archived, created_at "
                 "FROM mails WHERE receiver_id = :cid ORDER BY created_at DESC"),
            {"cid": commander_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def get_mail(mail_id: int, commander_id: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT * FROM mails WHERE id = :mid AND receiver_id = :cid"),
            {"mid": mail_id, "cid": commander_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def update_mail_dynamic(mail_id: int, **fields) -> None:
    if not fields:
        return
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    params = {"mid": mail_id}
    params.update(fields)
    async with get_session() as session:
        await session.execute(
            text(f"UPDATE mails SET {set_clause} WHERE id = :mid"),
            params,
        )
        await session.commit()


async def create_mail(receiver_id: int, title: str, body: str, custom_sender: Optional[str]) -> int:
    async with get_session() as session:
        result = await session.execute(
            text("INSERT INTO mails (receiver_id, title, body, custom_sender, created_at) "
                 "VALUES (:rid, :t, :b, :cs, NOW()) RETURNING id"),
            {"rid": receiver_id, "t": title, "b": body, "cs": custom_sender},
        )
        await session.commit()
        return result.scalar_one()


async def create_mail_attachment(mail_id: int, att_type: int, item_id: int, quantity: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("INSERT INTO mail_attachments (mail_id, type, item_id, quantity) VALUES (:mid, :t, :iid, :q)"),
            {"mid": mail_id, "t": att_type, "iid": item_id, "q": quantity},
        )
        await session.commit()


def create_mail_sync(receiver_id: int, title: str, body: str, custom_sender: Optional[str]) -> int:
    from src.db.session import get_sync_session
    with get_sync_session() as session:
        result = session.execute(
            text("INSERT INTO mails (receiver_id, title, body, custom_sender, created_at) "
                 "VALUES (:rid, :t, :b, :cs, NOW()) RETURNING id"),
            {"rid": receiver_id, "t": title, "b": body, "cs": custom_sender},
        )
        # sqlite: an unexhausted RETURNING cursor keeps the write transaction
        # open ("cannot commit transaction - SQL statements in progress"), so
        # drain+close before commit.
        mail_id = result.scalar_one()
        result.close()
        session.commit()
        return mail_id


def create_mail_attachment_sync(mail_id: int, att_type: int, item_id: int, quantity: int) -> None:
    from src.db.session import get_sync_session
    with get_sync_session() as session:
        session.execute(
            text("INSERT INTO mail_attachments (mail_id, type, item_id, quantity) VALUES (:mid, :t, :iid, :q)"),
            {"mid": mail_id, "t": att_type, "iid": item_id, "q": quantity},
        )
        session.commit()
