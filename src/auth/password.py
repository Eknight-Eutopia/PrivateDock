from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(_hash_str: str, password: str) -> bool:
    try:
        return _hasher.verify(_hash_str, password)
    except VerifyMismatchError:
        return False


def needs_rehash(hash_str: str) -> bool:
    return _hasher.check_needs_rehash(hash_str)
