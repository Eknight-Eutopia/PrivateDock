from sqlalchemy import text

from src.db.session import get_session


async def check_equip_code_share_exists(share_id: int) -> bool:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT EXISTS(SELECT 1 FROM equip_code_shares WHERE id = :sid)"),
            {"sid": share_id},
        )
        return result.scalar() or False


async def try_insert_equip_code_share(commander_id: int, share_data: dict):
    async with get_session() as session:
        await session.execute(
            text("""
                INSERT INTO equip_code_shares (creator_id, data)
                VALUES (:cid, :data)
            """),
            {"cid": commander_id, "data": share_data},
        )
        await session.commit()


async def try_insert_equip_code_like(commander_id: int, share_id: int):
    async with get_session() as session:
        await session.execute(
            text("INSERT INTO equip_code_likes (commander_id, share_id) VALUES (:cid, :sid) ON CONFLICT DO NOTHING"),
            {"cid": commander_id, "sid": share_id},
        )
        await session.commit()


async def try_insert_equip_code_report(commander_id: int, share_id: int, reason: str):
    async with get_session() as session:
        await session.execute(
            text("INSERT INTO equip_code_reports (commander_id, share_id, reason) VALUES (:cid, :sid, :reason)"),
            {"cid": commander_id, "sid": share_id, "reason": reason},
        )
        await session.commit()


async def count_equip_code_reports_since(share_id: int, since) -> int:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM equip_code_reports WHERE share_id = :sid AND created_at >= :since"),
            {"sid": share_id, "since": since},
        )
        return result.scalar() or 0
