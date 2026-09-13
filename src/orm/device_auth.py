from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from src.db.session import get_session, get_sync_session
from src.orm.auth_identity_map import AuthIdentityMap
from src.orm.device_auth_map import DeviceAuthMap
from src.orm.yostarus_map import YostarusMap

# ── Async CRUD ──


async def get_device_auth_map(device_id: str) -> Optional[DeviceAuthMap]:
    async with get_session() as session:
        result = await session.execute(
            select(DeviceAuthMap).where(DeviceAuthMap.device_id == device_id)
        )
        return result.scalar_one_or_none()


async def upsert_device_auth_map(device_id: str, arg2: str, account_id: str) -> DeviceAuthMap:
    async with get_session() as session:
        existing = await session.execute(
            select(DeviceAuthMap).where(DeviceAuthMap.device_id == device_id)
        )
        row = existing.scalar_one_or_none()
        if row:
            row.arg2 = arg2
            row.account_id = account_id
            result = row
        else:
            result = DeviceAuthMap(device_id=device_id, arg2=arg2, account_id=account_id)
            session.add(result)
        await session.commit()
        await session.refresh(result)
        return result


async def get_yostarus_map(arg2: int) -> Optional[YostarusMap]:
    async with get_session() as session:
        result = await session.execute(
            select(YostarusMap).where(YostarusMap.arg2 == arg2)
        )
        return result.scalar_one_or_none()


async def create_yostarus_map(arg2: int, account_id: str) -> YostarusMap:
    async with get_session() as session:
        obj = YostarusMap(arg2=arg2, account_id=int(account_id))
        session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return obj


# ── Sync CRUD ──


def get_yostarus_map_by_arg2(arg2: str) -> Optional[dict]:
    with get_sync_session() as session:
        result = session.execute(
            select(AuthIdentityMap).where(AuthIdentityMap.arg2 == int(arg2))
        )
        obj = result.scalar_one_or_none()
        if obj is None:
            return None
        return {"arg2": obj.arg2, "account_id": obj.account_id}


def get_device_auth_map_by_device_id(device_id: str) -> Optional[dict]:
    with get_sync_session() as session:
        result = session.execute(
            select(DeviceAuthMap).where(DeviceAuthMap.device_id == device_id)
        )
        obj = result.scalar_one_or_none()
        if obj is None:
            return None
        return {"device_id": obj.device_id, "arg2": obj.arg2, "account_id": obj.account_id}


def upsert_device_auth_map(device_id: str, arg2: str, account_id: str):
    with get_sync_session() as session:
        existing = session.execute(
            select(DeviceAuthMap).where(DeviceAuthMap.device_id == device_id)
        )
        row = existing.scalar_one_or_none()
        if row:
            row.arg2 = arg2
            row.account_id = account_id
        else:
            session.add(DeviceAuthMap(device_id=device_id, arg2=arg2, account_id=account_id))
        session.commit()
