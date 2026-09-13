from pydantic import BaseModel

from src.api.types.admin_authz import PermissionPolicyEntry

class MePermissionsResponse(BaseModel):
    roles: list[str] = []
    permissions: list[PermissionPolicyEntry] = []
