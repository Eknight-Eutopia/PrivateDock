import json


def extract_challenge(client_data_base64: str) -> str:
    import base64
    decoded = base64.urlsafe_b64decode(client_data_base64 + "==")
    payload = json.loads(decoded)
    return payload["challenge"]
