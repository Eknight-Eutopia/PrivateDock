from pydantic import BaseModel

from src.api.types.admin_authz import PermissionPolicyEntry


class UserPermissionPolicyResponse(BaseModel):
    role: str
    permissions: list[PermissionPolicyEntry]
    available_keys: list[str]
    updated_at: str
    updated_by: str


class UserPermissionPolicyUpdateRequest(BaseModel):
    permissions: list[PermissionPolicyEntry]
