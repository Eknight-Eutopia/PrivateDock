from typing import Any, Optional

from pydantic import BaseModel

from src.api.types.player import PaginationMeta






class AdminUser(BaseModel):
    id: str
    username: str
    is_admin: bool
    disabled: bool
    last_login_at: str
    created_at: str






class AdminUserCreateRequest(BaseModel):
    username: str
    password: str






class AdminUserListResponse(BaseModel):
    users: list[AdminUser]
    meta: PaginationMeta






class AdminUserPasswordUpdateRequest(BaseModel):
    password: str






class AdminUserResponse(BaseModel):
    user: AdminUser






class AdminUserUpdateRequest(BaseModel):
    username: Optional[str] = None
    disabled: Optional[bool] = None






class AuthBootstrapRequest(BaseModel):
    username: str
    password: str






class AuthBootstrapStatusResponse(BaseModel):
    can_bootstrap: bool
    admin_count: int






class AuthLoginRequest(BaseModel):
    username: str
    password: str






class AuthPasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str






class AuthSession(BaseModel):
    id: str
    expires_at: str






class AuthLoginResponse(BaseModel):
    user: AdminUser
    session: AuthSession






class AuthSessionResponse(BaseModel):
    user: AdminUser
    session: AuthSession
    csrf_token: str






class PasskeyAssertionResponse(BaseModel):
    client_data_json: str
    authenticator_data: str
    signature: str
    user_handle: str = ""






class PasskeyAttestationResponse(BaseModel):
    client_data_json: str
    attestation_object: str






class PasskeyAuthenticateOptionsRequest(BaseModel):
    username: Optional[str] = None






class PasskeyAuthenticateOptionsResponse(BaseModel):
    public_key: Any






class PasskeyAuthenticationCredential(BaseModel):
    id: str
    raw_id: str
    type: str
    response: PasskeyAssertionResponse






class PasskeyAuthenticateVerifyRequest(BaseModel):
    credential: PasskeyAuthenticationCredential
    username: Optional[str] = None






class PasskeyRegisterOptionsRequest(BaseModel):
    label: Optional[str] = None
    user_verification: Optional[str] = None
    resident_key: Optional[str] = None






class PasskeyRegisterOptionsResponse(BaseModel):
    public_key: Any






class PasskeyRegisterResponse(BaseModel):
    credential_id: str
    label: str
    created_at: str




class PasskeyRegistrationCredential(BaseModel):
    id: str
    raw_id: str
    type: str
    response: PasskeyAttestationResponse






class PasskeyRegisterVerifyRequest(BaseModel):
    credential: PasskeyRegistrationCredential
    label: Optional[str] = None






class PasskeySummary(BaseModel):
    credential_id: str
    label: str
    created_at: str
    last_used_at: str
    transports: list[str]
    aaguid: str
    backup_eligible: Optional[bool] = None
    backup_state: Optional[bool] = None






class PasskeyListResponse(BaseModel):
    passkeys: list[PasskeySummary]




