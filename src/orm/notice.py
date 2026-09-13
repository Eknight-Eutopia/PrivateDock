from __future__ import annotations
from typing import Optional
from sqlalchemy import text as sa_text
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


class Notice(Base):
    __tablename__ = 'notices'
    __table_args__ = {}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    version: Mapped[str] = mapped_column(String, default='')
    btn_title: Mapped[str] = mapped_column(String, default='')
    title: Mapped[str] = mapped_column(String, default='')
    title_image: Mapped[str] = mapped_column(String, default='')
    time_desc: Mapped[str] = mapped_column(String, default='')
    content: Mapped[str] = mapped_column(String, default='')
    tag_type: Mapped[int] = mapped_column(BigInteger, default=0)
    icon: Mapped[int] = mapped_column(BigInteger, default=0)
    track: Mapped[str] = mapped_column(String, default='')


def _row_to_notice(row) -> Notice:
    return Notice(
        id=row[0],
        version=row[1],
        btn_title=row[2],
        title=row[3],
        title_image=row[4],
        time_desc=row[5],
        content=row[6],
        tag_type=row[7],
        icon=row[8],
        track=row[9],
    )


def notice_create(notice: Notice) -> None:
    with get_sync_session() as session:
        session.execute(
            sa_text("""
                INSERT INTO notices (id, version, btn_title, title, title_image, time_desc, content, tag_type, icon, track)
                VALUES (:id, :ver, :bt, :t, :ti, :td, :c, :tt, :ic, :tr)
                ON CONFLICT (id)
                DO UPDATE SET version = EXCLUDED.version,
                    btn_title = EXCLUDED.btn_title,
                    title = EXCLUDED.title,
                    title_image = EXCLUDED.title_image,
                    time_desc = EXCLUDED.time_desc,
                    content = EXCLUDED.content,
                    tag_type = EXCLUDED.tag_type,
                    icon = EXCLUDED.icon,
                    track = EXCLUDED.track
            """),
            {
                "id": notice.id,
                "ver": notice.version,
                "bt": notice.btn_title,
                "t": notice.title,
                "ti": notice.title_image,
                "td": notice.time_desc,
                "c": notice.content,
                "tt": notice.tag_type,
                "ic": notice.icon,
                "tr": notice.track,
            },
        )
        session.commit()


def notice_update(notice: Notice) -> None:
    with get_sync_session() as session:
        session.execute(
            sa_text("""
                UPDATE notices
                SET version = :ver, btn_title = :bt, title = :t, title_image = :ti,
                    time_desc = :td, content = :c, tag_type = :tt, icon = :ic, track = :tr
                WHERE id = :id
            """),
            {
                "id": notice.id,
                "ver": notice.version,
                "bt": notice.btn_title,
                "t": notice.title,
                "ti": notice.title_image,
                "td": notice.time_desc,
                "c": notice.content,
                "tt": notice.tag_type,
                "ic": notice.icon,
                "tr": notice.track,
            },
        )
        session.commit()


def notice_retrieve(notice_id: int) -> Optional[Notice]:
    with get_sync_session() as session:
        row = session.execute(
            sa_text("""
                SELECT id, version, btn_title, title, title_image, time_desc, content, tag_type, icon, track
                FROM notices WHERE id = :id
            """),
            {"id": notice_id},
        ).fetchone()
        if row is None:
            return None
        return _row_to_notice(row)


def notice_delete(notice_id: int) -> bool:
    with get_sync_session() as session:
        result = session.execute(
            sa_text("DELETE FROM notices WHERE id = :id"),
            {"id": notice_id},
        )
        session.commit()
        return result.rowcount > 0


def list_notices() -> list[Notice]:
    with get_sync_session() as session:
        rows = session.execute(
            sa_text("""
                SELECT id, version, btn_title, title, title_image, time_desc, content, tag_type, icon, track
                FROM notices ORDER BY id ASC
            """),
        ).fetchall()
        return [_row_to_notice(r) for r in rows]

# ── SQLAlchemy model ──
