from __future__ import annotations

import base64
import binascii
import hashlib
import secrets
import math
import uuid
import hmac
from typing import Tuple, Optional

# Secure defaults
SALT_SIZE = 16
PBKDF2_DKLEN = 32
DEFAULT_ITERATIONS = 100_000


def generate_api_key(length: int = 64) -> str:

    if not isinstance(length, int):
        raise TypeError("length must be an int")

    if length < 8:
        raise ValueError("length must be >= 8")

    nbytes = math.ceil(length * 3 / 4)
    token = secrets.token_urlsafe(nbytes)
    while len(token) < length:
        token += secrets.token_urlsafe(nbytes)
    token = token[:length]
    return f"sk_{token}"


def generate_key_id() -> str:

    return uuid.uuid4().hex


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(s: str) -> bytes:
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)


def hash_api_key(api_key: str, *, iterations: int = DEFAULT_ITERATIONS, method: str = "pbkdf2") -> str:
    if not isinstance(api_key, str):
        raise TypeError("api_key must be a str")
    if not isinstance(iterations, int):
        raise TypeError("iterations must be an int")
    if method != "pbkdf2":
        raise ValueError("unsupported hashing method: only 'pbkdf2' is implemented")

    salt = secrets.token_bytes(SALT_SIZE)
    dk = hashlib.pbkdf2_hmac("sha256", api_key.encode("utf-8"), salt, iterations, dklen=PBKDF2_DKLEN)
    return f"pbkdf2_sha256${iterations}${_b64(salt)}${_b64(dk)}"


def verify_api_key(api_key: str, stored: str) -> bool:
    if not isinstance(api_key, str) or not isinstance(stored, str):
        return False

    if not stored or "$" not in stored:
        return False

    try:
        algo, iter_s, salt_b64, dk_b64 = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iter_s)
        salt = _unb64(salt_b64)
        expected = _unb64(dk_b64)
    except (ValueError, TypeError, binascii.Error):
        # Bad stored format or base64 decoding error
        return False

    derived = hashlib.pbkdf2_hmac("sha256", api_key.encode("utf-8"), salt, iterations, dklen=len(expected))
    return hmac.compare_digest(derived, expected)


def new_api_key_record(length: int = 32, *, iterations: int = DEFAULT_ITERATIONS, method: str = "pbkdf2") -> Tuple[str, str, str]:

    key = generate_api_key(length=length)
    stored = hash_api_key(key, iterations=iterations, method=method)
    return generate_key_id(), key, stored


# Compatibility: keep the old function
def new_api_key_pair(length: int = 32, *, iterations: int = DEFAULT_ITERATIONS) -> Tuple[str, str]:

    key = generate_api_key(length=length)
    stored = hash_api_key(key, iterations=iterations)
    return key, stored


__all__ = [
    "generate_api_key",
    "generate_key_id",
    "hash_api_key",
    "verify_api_key",
    "new_api_key_record",
    "new_api_key_pair",
]