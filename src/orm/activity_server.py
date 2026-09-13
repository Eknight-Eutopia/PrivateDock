from __future__ import annotations


from sqlalchemy import BigInteger, Boolean, Integer, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session

# Fallback used only when the server_activities table is missing or empty
# (migrations/import not yet run against a fresh DB). It mirrors the historical
# hard-coded "always visible" allowlist so a pre-imported database still serves
# the baseline activities instead of nothing.
FALLBACK_ACTIVITY_IDS = [
    2, 3, 4, 6, 7, 9, 21, 7104, 980001, 30011, 30017, 30105, 30209, 30445,
    *range(30500, 30509),
]


class ServerActivity(Base):
    __tablename__ = "server_activities"
    activity_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_permanent: Mapped[bool] = mapped_column(Boolean, default=False)
    start_time: Mapped[int] = mapped_column(BigInteger, default=0)
    end_time: Mapped[int] = mapped_column(BigInteger, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(Text, default="")


def _row_to_dict(r: ServerActivity) -> dict:
    return {
        "activity_id": int(r.activity_id),
        "enabled": bool(r.enabled),
        "is_permanent": bool(r.is_permanent),
        "start_time": int(r.start_time or 0),
        "end_time": int(r.end_time or 0),
        "sort_order": int(r.sort_order or 0),
        "note": r.note or "",
    }


def get_server_activities_sync(enabled_only: bool = True) -> list[dict]:
    """Server-registered activities (SC_11200 candidates), sorted by
    sort_order then activity_id. ``enabled`` rows are the ones the server is
    asked to serve; the rest are seeded-but-disabled inventory."""
    with get_sync_session() as session:
        q = select(ServerActivity)
        if enabled_only:
            q = q.where(ServerActivity.enabled == True)  # noqa: E712
        q = q.order_by(ServerActivity.sort_order, ServerActivity.activity_id)
        rows = session.execute(q).scalars().all()
    return [_row_to_dict(r) for r in rows]


def set_server_activity_enabled_sync(activity_id: int, enabled: bool) -> bool:
    """Flip one activity's ``enabled`` flag. Returns True if the activity is
    registered (updated), False if it is not in the table."""
    with get_sync_session() as session:
        r = session.execute(
            select(ServerActivity).where(ServerActivity.activity_id == activity_id)
        ).scalar_one_or_none()
        if r is None:
            return False
        r.enabled = bool(enabled)
        session.commit()
        return True