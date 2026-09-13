from __future__ import annotations

from sqlalchemy import BigInteger, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


class CommanderStoreupAwardProgress(Base):
    __tablename__ = "commander_storeup_award_progresses"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    storeup_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    last_award_index: Mapped[int] = mapped_column(BigInteger, default=0)


def list_commander_storeup_awards(commander_id: int) -> list[tuple[int, int]]:
    with get_sync_session() as session:
        rp = session.execute(
            text(
                "SELECT storeup_id, last_award_index "
                "FROM commander_storeup_award_progresses "
                "WHERE commander_id = :cid ORDER BY storeup_id ASC"
            ),
            {"cid": commander_id},
        )
        return [(int(row[0]), int(row[1])) for row in rp.fetchall()]


def get_last_commander_storeup_award_index(commander_id: int, storeup_id: int) -> int:
    with get_sync_session() as session:
        rp = session.execute(
            text(
                "SELECT last_award_index "
                "FROM commander_storeup_award_progresses "
                "WHERE commander_id = :cid AND storeup_id = :sid"
            ),
            {"cid": commander_id, "sid": storeup_id},
        )
        row = rp.fetchone()
        if row is None:
            return 0
        return int(row[0])


def set_commander_storeup_award_index(
    commander_id: int, storeup_id: int, last_award_index: int,
) -> None:
    with get_sync_session() as session:
        session.execute(
            text(
                "INSERT INTO commander_storeup_award_progresses "
                "(commander_id, storeup_id, last_award_index) "
                "VALUES (:cid, :sid, :idx) "
                "ON CONFLICT (commander_id, storeup_id) "
                "DO UPDATE SET last_award_index = EXCLUDED.last_award_index"
            ),
            {"cid": commander_id, "sid": storeup_id, "idx": last_award_index},
        )
        session.commit()


def try_advance_commander_storeup_award_index(
    commander_id: int, storeup_id: int, award_index: int,
) -> bool:
    """Atomically advances the storeup progress by exactly one tier.

    Returns True only if the index was advanced from (award_index-1) -> award_index.
    Used to prevent duplicate claims on concurrent requests.
    """
    if award_index <= 0:
        return False

    with get_sync_session() as session:
        if award_index == 1:
            rp = session.execute(
                text(
                    "INSERT INTO commander_storeup_award_progresses "
                    "(commander_id, storeup_id, last_award_index) "
                    "VALUES (:cid, :sid, 1) "
                    "ON CONFLICT (commander_id, storeup_id) "
                    "DO UPDATE SET last_award_index = 1 "
                    "WHERE commander_storeup_award_progresses.last_award_index = 0"
                ),
                {"cid": commander_id, "sid": storeup_id},
            )
            session.commit()
            return rp.rowcount == 1

        previous_index = award_index - 1
        rp = session.execute(
            text(
                "UPDATE commander_storeup_award_progresses "
                "SET last_award_index = :idx "
                "WHERE commander_id = :cid AND storeup_id = :sid "
                "AND last_award_index = :prev"
            ),
            {
                "cid": commander_id,
                "sid": storeup_id,
                "idx": award_index,
                "prev": previous_index,
            },
        )
        session.commit()
        return rp.rowcount == 1