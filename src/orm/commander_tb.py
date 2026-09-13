from __future__ import annotations
from typing import Any, Optional

from sqlalchemy import BigInteger, LargeBinary, select, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session, get_sync_session
from src.protobuf import protobuf as proto


async def get_commander_tb_row(commander_id: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT state, permanent FROM commander_tbs WHERE commander_id = :cid"),
            {"cid": commander_id},
        )
        row = result.mappings().first()
        if row is None:
            return None
        return dict(row)


async def exists_commander_tb(commander_id: int) -> bool:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT 1 FROM commander_tbs WHERE commander_id = :cid"),
            {"cid": commander_id},
        )
        return result.first() is not None


async def insert_commander_tb(commander_id: int, state: Any, permanent: Any) -> None:
    async with get_session() as session:
        await session.execute(
            text("INSERT INTO commander_tbs (commander_id, state, permanent) VALUES (:cid, :state, :permanent)"),
            {"cid": commander_id, "state": state, "permanent": permanent},
        )
        await session.commit()


async def update_commander_tb(commander_id: int, state: Any, permanent: Any) -> None:
    async with get_session() as session:
        await session.execute(
            text("UPDATE commander_tbs SET state = :state, permanent = :permanent WHERE commander_id = :cid"),
            {"state": state, "permanent": permanent, "cid": commander_id},
        )
        await session.commit()


async def delete_commander_tb_row(commander_id: int) -> bool:
    async with get_session() as session:
        result = await session.execute(
            text("DELETE FROM commander_tbs WHERE commander_id = :cid"),
            {"cid": commander_id},
        )
        await session.commit()
        return result.rowcount > 0


def get_commander_tb(commander_id: int) -> Optional[CommanderTB]:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderTB).where(CommanderTB.commander_id == commander_id)
        )
        return result.scalar_one_or_none()


def new_commander_tb(commander_id: int, info: proto.TBINFO, permanent: proto.TBPERMANENT) -> CommanderTB:
    state_bytes = info.SerializeToString()
    permanent_bytes = permanent.SerializeToString()
    return CommanderTB(
        commander_id=commander_id,
        state=state_bytes,
        permanent=permanent_bytes,
    )


def save_commander_tb(entry: CommanderTB) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO commander_tbs (commander_id, state, permanent)
                VALUES (:commander_id, :state, :permanent)
                ON CONFLICT (commander_id)
                DO UPDATE SET
                    state = EXCLUDED.state,
                    permanent = EXCLUDED.permanent
            """),
            {
                "commander_id": entry.commander_id,
                "state": entry.state,
                "permanent": entry.permanent,
            },
        )
        session.commit()


def delete_commander_tb(commander_id: int) -> bool:
    with get_sync_session() as session:
        result = session.execute(
            text("""
                DELETE FROM commander_tbs
                WHERE commander_id = :commander_id
            """),
            {"commander_id": commander_id},
        )
        session.commit()
        return result.rowcount > 0


def decode_commander_tb(entry: CommanderTB) -> tuple:
    state = proto.TBINFO()
    state.ParseFromString(bytes(entry.state))
    permanent = proto.TBPERMANENT()
    permanent.ParseFromString(bytes(entry.permanent))
    return state, permanent


class CommanderTB(Base):
    __tablename__ = "commander_tbs"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    state: Mapped[bytes] = mapped_column(LargeBinary, default=b"")
    permanent: Mapped[bytes] = mapped_column(LargeBinary, default=b"")
