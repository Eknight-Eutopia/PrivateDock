from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import BigInteger, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session


async def list_groups_by_commander(commander_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, commander_id, group_id, skin_id, favorite, cur_chat_group "
                 "FROM juustagram_groups WHERE commander_id = :cid ORDER BY group_id ASC"),
            {"cid": commander_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def get_group(commander_id: int, group_id: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, commander_id, group_id, skin_id, favorite, cur_chat_group "
                 "FROM juustagram_groups WHERE commander_id = :cid AND group_id = :gid"),
            {"cid": commander_id, "gid": group_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def create_group(commander_id: int, group_id: int, skin_id: int, favorite: int, cur_chat_group: int) -> int:
    async with get_session() as session:
        result = await session.execute(
            text("INSERT INTO juustagram_groups (commander_id, group_id, skin_id, favorite, cur_chat_group) "
                 "VALUES (:cid, :gid, :sk, :fav, :ccg) RETURNING id"),
            {"cid": commander_id, "gid": group_id, "sk": skin_id, "fav": favorite, "ccg": cur_chat_group},
        )
        await session.commit()
        return result.scalar_one()


async def update_group_dynamic(commander_id: int, group_id: int, **fields) -> None:
    if not fields:
        return
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    params = {"cid": commander_id, "gid": group_id}
    params.update(fields)
    async with get_session() as session:
        await session.execute(
            text(f"UPDATE juustagram_groups SET {set_clause} WHERE commander_id = :cid AND group_id = :gid"),
            params,
        )
        await session.commit()


async def update_group_current_chat(record_id: int, commander_id: int, cur_chat_group: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("UPDATE juustagram_groups SET cur_chat_group = :ccg WHERE id = :rid AND commander_id = :cid"),
            {"ccg": cur_chat_group, "rid": record_id, "cid": commander_id},
        )
        await session.commit()


async def delete_group(commander_id: int, group_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("DELETE FROM juustagram_groups WHERE commander_id = :cid AND group_id = :gid"),
            {"cid": commander_id, "gid": group_id},
        )
        await session.commit()


class JuustagramGroup(Base):
    __tablename__ = 'juustagram_groups'
    __table_args__ = {}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    commander_id: Mapped[int] = mapped_column(BigInteger)
    group_id: Mapped[int] = mapped_column(BigInteger, default=0)
    skin_id: Mapped[int] = mapped_column(BigInteger, default=0)
    favorite: Mapped[int] = mapped_column(BigInteger, default=0)
    cur_chat_group: Mapped[int] = mapped_column(BigInteger, default=0)


# ── sync (store-based) access for game-packet handlers ────────────────────

from src.db.store import get_default_store


def get_commander_group_tree_sync(commander_id: int) -> list[dict[str, Any]]:
    """juustagram_groups + nested chat_groups + nested reply_list in three
    batched queries (groups, chat groups, replies), assembled into the tree
    the SC builder walks."""
    store = get_default_store()
    group_rows = store.fetch(
        "SELECT id, commander_id, group_id, skin_id, favorite, cur_chat_group "
        "FROM juustagram_groups WHERE commander_id = $1",
        commander_id,
    )
    groups = [dict(zip(r._cols, r._values)) for r in group_rows]
    if not groups:
        return groups
    group_ids = [g["id"] for g in groups]
    chat_rows = store.fetch(
        "SELECT id, commander_id, group_record_id, chat_group_id, op_time, read_flag "
        "FROM juustagram_chat_groups WHERE commander_id = $1 AND group_record_id = ANY($2)",
        commander_id, group_ids,
    )
    chat_groups = [dict(r) for r in chat_rows]
    chat_ids = [cg["id"] for cg in chat_groups]
    reply_rows = []
    if chat_ids:
        reply_rows = list(store.fetch(
            "SELECT id, chat_group_record_id, sequence, key, value "
            "FROM juustagram_replies WHERE chat_group_record_id = ANY($1) ORDER BY sequence",
            chat_ids,
        ))
    group_map = {g["id"]: g for g in groups}
    for cg in chat_groups:
        cg["reply_list"] = []
        gid = cg["group_record_id"]
        if gid in group_map:
            group = group_map[gid]
            if "chat_groups" not in group:
                group["chat_groups"] = []
            group["chat_groups"].append(cg)
    for rr in reply_rows:
        rr = dict(rr)
        for cg in chat_groups:
            if cg["id"] == rr["chat_group_record_id"]:
                cg["reply_list"].append(rr)
                break
    return groups


def ensure_juustagram_group_sync(commander_id: int, group_id: int, chat_group_id: int) -> dict[str, Any]:
    store = get_default_store()
    row = store.fetchrow(
        "SELECT id, commander_id, group_id, skin_id, favorite, cur_chat_group "
        "FROM juustagram_groups WHERE commander_id = $1 AND group_id = $2",
        commander_id, group_id,
    )
    if row is not None:
        return dict(row)
    row = store.fetchrow(
        "INSERT INTO juustagram_groups (commander_id, group_id, skin_id, favorite, cur_chat_group) "
        "VALUES ($1, $2, 0, 0, $3) RETURNING id, commander_id, group_id, skin_id, favorite, cur_chat_group",
        commander_id, group_id, chat_group_id,
    )
    return dict(row)


def create_group_with_chat_group_sync(commander_id: int, group_id: int, chat_group_id: int) -> dict[str, Any]:
    store = get_default_store()
    group = ensure_juustagram_group_sync(commander_id, group_id, chat_group_id)
    chat_row = store.fetchrow(
        "INSERT INTO juustagram_chat_groups (commander_id, group_record_id, chat_group_id, op_time, read_flag) "
        "VALUES ($1, $2, $3, 0, 0) RETURNING id, commander_id, group_record_id, chat_group_id, op_time, read_flag",
        commander_id, group["id"], chat_group_id,
    )
    cg = dict(chat_row)
    cg["reply_list"] = []
    group["chat_groups"] = [cg]
    return group
