from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from src.authz import Capability, known_permissions, merge_capabilities
from src.authz.keys import RoleAdmin
from src.orm.role import Role
from src.orm.permission import Permission
from src.db.permission_override import PermissionOverrideAllow, PermissionOverrideDeny


def _get_store():
    """Lazy import to avoid circular dependency: authz_store -> db.store -> orm.session -> orm.__init__ -> authz_store"""
    from src.db.store import get_default_store
    return get_default_store()


def _not_found(msg: str):
    from src.db.store import NotFoundError
    return NotFoundError(msg)


@dataclass
class AccountOverrideEntry:
    key: str
    mode: str
    capability: Capability


@dataclass
class RolePolicyEntry:
    key: str
    capability: Capability


async def list_roles() -> list[Role]:
    store = _get_store()
    rows = await store.afetch("SELECT id, name, description, created_at, updated_at, updated_by FROM roles ORDER BY name")
    return [_role_from_row(r) for r in rows]


async def get_role_by_name(role_name: str) -> Optional[Role]:
    if not role_name:
        raise _not_found("role name empty")
    store = _get_store()
    row = await store.afetchrow("SELECT id, name, description, created_at, updated_at, updated_by FROM roles WHERE name = $1", role_name)
    if row is None:
        raise _not_found("role not found")
    return _role_from_row(row)


async def list_permissions() -> list[Permission]:
    store = _get_store()
    rows = await store.afetch("SELECT id, key, description, created_at, updated_at FROM permissions ORDER BY key")
    return [_permission_from_row(r) for r in rows]


async def get_permission_by_key(key: str) -> Optional[Permission]:
    store = _get_store()
    row = await store.afetchrow("SELECT id, key, description, created_at, updated_at FROM permissions WHERE key = $1", key)
    if row is None:
        raise _not_found("permission not found")
    return _permission_from_row(row)


async def list_account_role_names(account_id: str) -> list[str]:
    store = _get_store()
    if not account_id:
        return []
    rows = await store.afetch(
        "SELECT r.name FROM roles r JOIN account_roles ar ON r.id = ar.role_id WHERE ar.account_id = $1 ORDER BY r.name",
        account_id,
    )
    return [r["name"] for r in rows]


async def list_account_role_ids(account_id: str) -> list[str]:
    store = _get_store()
    rows = await store.afetch("SELECT role_id FROM account_roles WHERE account_id = $1", account_id)
    return [r["role_id"] for r in rows]


async def replace_account_roles_by_name(account_id: str, role_names: list[str]):
    if not account_id:
        return
    seen: set[str] = set()
    unique: list[str] = []
    for name in role_names:
        name = name.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        unique.append(name)

    store = _get_store()

    current = await store.afetch(
        "SELECT r.name FROM roles r JOIN account_roles ar ON r.id = ar.role_id WHERE ar.account_id = $1", account_id,
    )
    current_set = {r["name"] for r in current}
    next_set = set(unique)

    if RoleAdmin in current_set and RoleAdmin not in next_set:
        count = await store.afetchval(
            "SELECT COUNT(*) FROM account_roles ar JOIN roles r ON r.id = ar.role_id WHERE r.name = $1 AND ar.account_id != $2",
            RoleAdmin, account_id,
        )
        if count == 0:
            raise ValueError("cannot remove last admin role")

    await store.aexecute("DELETE FROM account_roles WHERE account_id = $1", account_id)
    now = datetime.now(timezone.utc)
    for name in unique:
        row = await store.afetchrow("SELECT id FROM roles WHERE name = $1", name)
        if row is None:
            continue
        await store.aexecute(
            "INSERT INTO account_roles (account_id, role_id, created_at) VALUES ($1, $2, $3)",
            account_id, row["id"], now,
        )


async def list_account_overrides(account_id: str) -> list[AccountOverrideEntry]:
    if not account_id:
        return []
    store = _get_store()
    rows = await store.afetch(
        "SELECT p.key, apo.mode, apo.can_read_self, apo.can_read_any, apo.can_write_self, apo.can_write_any "
        "FROM account_permission_overrides apo JOIN permissions p ON p.id = apo.permission_id WHERE apo.account_id = $1 ORDER BY p.key",
        account_id,
    )
    return [
        AccountOverrideEntry(
            key=r["key"], mode=r["mode"],
            capability=Capability(read_self=r["can_read_self"], read_any=r["can_read_any"], write_self=r["can_write_self"], write_any=r["can_write_any"]),
        )
        for r in rows
    ]


async def replace_account_overrides(account_id: str, overrides: list[AccountOverrideEntry]):
    if not account_id:
        return
    seen: set[str] = set()
    unique: list[AccountOverrideEntry] = []
    for entry in overrides:
        key = entry.key.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        entry.key = key
        unique.append(entry)

    store = _get_store()
    await store.aexecute("DELETE FROM account_permission_overrides WHERE account_id = $1", account_id)
    now = datetime.now(timezone.utc)
    for entry in unique:
        perm = await store.afetchrow("SELECT id FROM permissions WHERE key = $1", entry.key)
        if perm is None:
            continue
        mode = entry.mode
        if mode not in (PermissionOverrideAllow, PermissionOverrideDeny):
            mode = PermissionOverrideAllow
        await store.aexecute(
            "INSERT INTO account_permission_overrides (account_id, permission_id, mode, can_read_self, can_read_any, can_write_self, can_write_any, updated_at) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
            account_id, perm["id"], mode,
            entry.capability.read_self, entry.capability.read_any, entry.capability.write_self, entry.capability.write_any,
            now,
        )


async def ensure_authz_defaults():
    known = known_permissions()
    if not known:
        return

    store = _get_store()
    permission_ids: dict[str, str] = {}
    now = datetime.now(timezone.utc)
    for key, description in known.items():
        row = await store.afetchrow("SELECT id FROM permissions WHERE key = $1", key)
        if row:
            permission_ids[key] = row["id"]
        else:
            import uuid
            pid = str(uuid.uuid4())
            await store.aexecute(
                "INSERT INTO permissions (id, key, description, created_at, updated_at) VALUES ($1, $2, $3, $4, $5)",
                pid, key, description, now, now,
            )
            permission_ids[key] = pid

    admin_role_id = await _ensure_role(store, "admin", "Full access")
    await _ensure_role(store, "player", "Default player role")

    for perm_id in permission_ids.values():
        await store.aexecute(
            "INSERT INTO role_permissions (role_id, permission_id, can_read_self, can_read_any, can_write_self, can_write_any, updated_at) "
            "VALUES ($1, $2, true, true, true, true, $3) "
            "ON CONFLICT (role_id, permission_id) DO UPDATE SET can_read_self=true, can_read_any=true, can_write_self=true, can_write_any=true, updated_at=$3",
            admin_role_id, perm_id, now,
        )


async def assign_role_by_name(account_id: str, role_name: str):
    if not account_id or not role_name:
        return
    store = _get_store()
    role = await store.afetchrow("SELECT id FROM roles WHERE name = $1", role_name)
    if role is None:
        return
    now = datetime.now(timezone.utc)
    await store.aexecute(
        "INSERT INTO account_roles (account_id, role_id, created_at) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
        account_id, role["id"], now,
    )


async def load_role_policy_by_name(role_name: str) -> list[RolePolicyEntry]:
    known = known_permissions()
    keys = sorted(known.keys())
    store = _get_store()
    role = await store.afetchrow("SELECT id FROM roles WHERE name = $1", role_name)
    if role is None:
        raise _not_found("role not found")
    rows = await store.afetch(
        "SELECT p.key, rp.can_read_self, rp.can_read_any, rp.can_write_self, rp.can_write_any "
        "FROM permissions p JOIN role_permissions rp ON p.id = rp.permission_id WHERE rp.role_id = $1 AND p.key = ANY($2) ORDER BY p.key",
        role["id"], keys,
    )
    lookup: dict[str, Capability] = {}
    for r in rows:
        lookup[r["key"]] = Capability(read_self=r["can_read_self"], read_any=r["can_read_any"], write_self=r["can_write_self"], write_any=r["can_write_any"])
    return [RolePolicyEntry(key=k, capability=lookup.get(k, Capability())) for k in keys]


async def replace_role_policy_by_name(role_name: str, capabilities: dict[str, Capability], updated_by: Optional[str] = None):
    known = known_permissions()
    if not known:
        return
    store = _get_store()
    role = await store.afetchrow("SELECT id FROM roles WHERE name = $1", role_name)
    if role is None:
        raise _not_found("role not found")
    now = datetime.now(timezone.utc)
    await store.aexecute(
        "UPDATE roles SET updated_by = $1, updated_at = $2 WHERE id = $3",
        updated_by, now, role["id"],
    )
    for key in known:
        perm = await store.afetchrow("SELECT id FROM permissions WHERE key = $1", key)
        if perm is None:
            continue
        cap = capabilities.get(key, Capability())
        await store.aexecute(
            "INSERT INTO role_permissions (role_id, permission_id, can_read_self, can_read_any, can_write_self, can_write_any, updated_at) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7) "
            "ON CONFLICT (role_id, permission_id) DO UPDATE SET can_read_self=$3, can_read_any=$4, can_write_self=$5, can_write_any=$6, updated_at=$7",
            role["id"], perm["id"], cap.read_self, cap.read_any, cap.write_self, cap.write_any, now,
        )


async def load_effective_permissions(account_id: str) -> dict[str, Capability]:
    if not account_id:
        return {}
    store = _get_store()
    role_ids = await store.afetch("SELECT role_id FROM account_roles WHERE account_id = $1", account_id)
    if not role_ids:
        return {}
    ids = [r["role_id"] for r in role_ids]
    rows = await store.afetch(
        "SELECT p.key, rp.can_read_self, rp.can_read_any, rp.can_write_self, rp.can_write_any "
        "FROM permissions p JOIN role_permissions rp ON p.id = rp.permission_id WHERE rp.role_id = ANY($1)",
        ids,
    )
    result: dict[str, Capability] = {}
    for r in rows:
        current = result.get(r["key"], Capability())
        result[r["key"]] = merge_capabilities(current, Capability(
            read_self=r["can_read_self"], read_any=r["can_read_any"],
            write_self=r["can_write_self"], write_any=r["can_write_any"],
        ))

    overrides = await store.afetch(
        "SELECT p.key, apo.mode, apo.can_read_self, apo.can_read_any, apo.can_write_self, apo.can_write_any "
        "FROM account_permission_overrides apo JOIN permissions p ON p.id = apo.permission_id WHERE apo.account_id = $1",
        account_id,
    )
    for ov in overrides:
        cap = result.get(ov["key"], Capability())
        mask = Capability(read_self=ov["can_read_self"], read_any=ov["can_read_any"], write_self=ov["can_write_self"], write_any=ov["can_write_any"])
        if ov["mode"] == PermissionOverrideAllow:
            cap = merge_capabilities(cap, mask)
        elif ov["mode"] == PermissionOverrideDeny:
            if mask.read_self:
                cap.read_self = False
            if mask.read_any:
                cap.read_any = False
            if mask.write_self:
                cap.write_self = False
            if mask.write_any:
                cap.write_any = False
        result[ov["key"]] = cap

    return result


async def _ensure_role(store, name: str, description: str) -> str:
    row = await store.afetchrow("SELECT id, description FROM roles WHERE name = $1", name)
    if row:
        if row["description"] != description:
            await store.aexecute("UPDATE roles SET description = $1 WHERE id = $2", description, row["id"])
        return row["id"]
    import uuid
    rid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await store.aexecute(
        "INSERT INTO roles (id, name, description, created_at, updated_at) VALUES ($1, $2, $3, $4, $5)",
        rid, name, description, now, now,
    )
    return rid


def _role_from_row(row) -> Role:
    return Role(
        id=row["id"],
        name=row["name"],
        description=row.get("description", ""),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
        updated_by=row.get("updated_by"),
    )


def _permission_from_row(row) -> Permission:
    return Permission(
        id=row["id"],
        key=row["key"],
        description=row.get("description", ""),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )
