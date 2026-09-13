from __future__ import annotations
from typing import Any, Sequence
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class MailAttachment(Base):
    __tablename__ = 'mail_attachments'
    __table_args__ = {}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    mail_id: Mapped[int] = mapped_column(BigInteger)
    type: Mapped[int] = mapped_column(BigInteger, default=0)
    item_id: Mapped[int] = mapped_column(BigInteger, default=0)
    quantity: Mapped[int] = mapped_column(BigInteger, default=0)


async def afetch_mail_attachments(mail_ids: Sequence[int]) -> list[dict[str, Any]]:
    if not mail_ids:
        return []
    from src.db.store import get_default_store
    store = get_default_store()
    if store is None:
        return []
    try:
        rows = await store.afetch(
            "SELECT id, mail_id, type, item_id, quantity FROM mail_attachments "
            "WHERE mail_id = ANY($1::bigint[]) ORDER BY id",
            list(mail_ids),
        )
        return [dict(r) for r in rows]
    except Exception:
        return []


def fetch_mail_attachments(mail_ids: Sequence[int]) -> list[dict[str, Any]]:
    if not mail_ids:
        return []
    from src.db.store import get_default_store
    store = get_default_store()
    if store is None:
        return []
    try:
        rows = store.fetch(
            "SELECT id, mail_id, type, item_id, quantity FROM mail_attachments "
            "WHERE mail_id = ANY($1::bigint[]) ORDER BY id",
            list(mail_ids),
        )
        return [dict(r) for r in rows]
    except Exception:
        return []

