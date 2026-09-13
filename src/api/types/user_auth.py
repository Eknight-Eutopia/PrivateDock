
from pydantic import BaseModel





class UserAccount(BaseModel):
    id: int = 0
    commander_id: int = 0
    disabled: bool = False
    last_login_at: str = ""
    created_at: str = ""





class UserAuthLoginRequest(BaseModel):
    commander_id: int
    password: str





class UserRegistrationChallengeRequest(BaseModel):
    commander_id: int
    password: str





class UserRegistrationChallengeResponse(BaseModel):
    challenge_id: str = ""
    expires_at: str = ""





class UserRegistrationStatusResponse(BaseModel):
    status: str = ""





class UserRegistrationVerifyRequest(BaseModel):
    pin: str




class UserSession(BaseModel):
    id: str = ""
    expires_at: str = ""





class UserAuthLoginResponse(BaseModel):
    user: UserAccount
    session: UserSession





class UserAuthSessionResponse(BaseModel):
    user: UserAccount
    session: UserSession
    csrf_token: str = ""



