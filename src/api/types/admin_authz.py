
from pydantic import BaseModel






class AccountOverrideEntry(BaseModel):
    key: str
    mode: str
    read_self: bool
    read_any: bool
    write_self: bool
    write_any: bool






class AccountOverridesResponse(BaseModel):
    account_id: str
    overrides: list[AccountOverrideEntry]






class AccountOverridesUpdateRequest(BaseModel):
    overrides: list[AccountOverrideEntry]




class AccountRolesResponse(BaseModel):
    account_id: str
    roles: list[str]






class AccountRolesUpdateRequest(BaseModel):
    roles: list[str]






class PermissionPolicyEntry(BaseModel):
    key: str
    read_self: bool = False
    read_any: bool = False
    write_self: bool = False
    write_any: bool = False






class PermissionSummary(BaseModel):
    key: str
    description: str






class PermissionListResponse(BaseModel):
    permissions: list[PermissionSummary]






class RolePolicyResponse(BaseModel):
    role: str
    permissions: list[PermissionPolicyEntry]
    available_keys: list[str]
    updated_at: str
    updated_by: str






class RolePolicyUpdateRequest(BaseModel):
    permissions: list[PermissionPolicyEntry]






class RoleSummary(BaseModel):
    name: str
    description: str
    updated_at: str
    updated_by: str






class RoleListResponse(BaseModel):
    roles: list[RoleSummary]




