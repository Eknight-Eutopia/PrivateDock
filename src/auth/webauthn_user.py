
from src.orm.account import Account
from src.orm.web_authn_credential import WebAuthnCredential


class WebAuthnUser:
    def __init__(self, user_id: bytes, name: str, display_name: str, credentials: list):
        self.id = user_id
        self.name = name
        self.display_name = display_name
        self.credentials = credentials

    def web_authn_id(self) -> bytes:
        return self.id

    def web_authn_name(self) -> str:
        return self.name

    def web_authn_display_name(self) -> str:
        return self.display_name

    def web_authn_credentials(self) -> list:
        return self.credentials


def build_webauthn_user(account: Account, credentials: list[WebAuthnCredential]):
    if not account.web_authn_user_handle:
        raise ValueError("missing webauthn user handle")
    webauthn_creds = []
    for cred in credentials:
        webauthn_creds.append(build_credential(cred))
    name = account.username or ""
    if not name and account.commander_id:
        name = f"commander:{account.commander_id}"
    if not name:
        name = account.id
    return WebAuthnUser(
        user_id=account.web_authn_user_handle,
        name=name,
        display_name=name,
        credentials=webauthn_creds,
    )


def build_credential(record: WebAuthnCredential) -> dict:
    import base64
    cred_id = base64.urlsafe_b64decode(record.credential_id + "==")
    aaguid = None
    if record.aaguid:
        aaguid = base64.urlsafe_b64decode(record.aaguid + "==")
    return {
        "id": cred_id,
        "public_key": record.public_key,
        "attestation_type": record.attestation_fmt,
        "transports": record.transports[:],
        "flags": {
            "backup_eligible": record.backup_eligible,
            "backup_state": record.backup_state,
        },
        "authenticator": {
            "aaguid": aaguid or b"",
            "sign_count": record.sign_count,
        },
    }
