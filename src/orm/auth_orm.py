from sqlalchemy import select, text

from src.db.session import get_session
from src.orm.auth_identity_map import AuthIdentityMap
from src.orm.device_auth_map import DeviceAuthMap


def _orm_to_dict(obj):
    if obj is None:
        return None
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


async def get_yostarus_map_by_arg2(arg2: int):
    async with get_session() as session:
        result = await session.execute(
            select(AuthIdentityMap).where(AuthIdentityMap.arg2 == arg2)
        )
        obj = result.scalar_one_or_none()
        if obj is None:
            return None
        return {"arg2": obj.arg2, "account_id": obj.account_id}


def get_yostarus_map_by_arg2_sync(arg2: int):
    from src.db.session import get_sync_session as gss
    with gss() as session:
        result = session.execute(
            select(AuthIdentityMap).where(AuthIdentityMap.arg2 == arg2)
        )
        obj = result.scalar_one_or_none()
        if obj is None:
            return None
        return {"arg2": obj.arg2, "account_id": obj.account_id}


async def get_device_auth_map_by_device_id(device_id: str):
    async with get_session() as session:
        result = await session.execute(
            select(DeviceAuthMap).where(DeviceAuthMap.device_id == device_id)
        )
        obj = result.scalar_one_or_none()
        if obj is None:
            return None
        return {"device_id": obj.device_id, "arg2": obj.arg2, "account_id": obj.account_id}


async def upsert_device_auth_map(device_id: str, arg2: int, account_id: int):
    async with get_session() as session:
        existing = await session.execute(
            select(DeviceAuthMap).where(DeviceAuthMap.device_id == device_id)
        )
        row = existing.scalar_one_or_none()
        if row:
            row.arg2 = arg2
            row.account_id = account_id
        else:
            session.add(DeviceAuthMap(device_id=device_id, arg2=arg2, account_id=account_id))
        await session.commit()


async def get_local_account_by_account(account: str):
    async with get_session() as session:
        result = await session.execute(
            text("SELECT arg2, account, password, mail_box FROM local_accounts WHERE account = :acc"),
            {"acc": account},
        )
        row = result.fetchone()
        if row is None:
            return None
        return {"arg2": row[0], "account": row[1], "password": row[2], "mail_box": row[3]}


async def update_local_account_password(account: str, password_hash: str):
    async with get_session() as session:
        await session.execute(
            text("UPDATE local_accounts SET password = :pw WHERE account = :acc"),
            {"acc": account, "pw": password_hash},
        )
        await session.commit()
