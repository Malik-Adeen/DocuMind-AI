from __future__ import annotations

import hashlib
import hmac
import os
import time
import uuid
from typing import Any

import jwt

ALGORITHM = "HS256"
ITERATIONS = 600_000
ROLE_RANK = {"viewer": 0, "reviewer": 1, "admin": 2}


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
    )
    return hmac.compare_digest(candidate.hex(), digest_hex)


def create_access_token(*, user_id: uuid.UUID, role: str, secret: str, expires_in: int) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + expires_in,
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(token: str, *, secret: str) -> dict[str, Any]:
    claims: dict[str, Any] = jwt.decode(token, secret, algorithms=[ALGORITHM])
    return claims


def outranks(role: str, minimum: str) -> bool:
    return ROLE_RANK.get(role, -1) >= ROLE_RANK[minimum]
