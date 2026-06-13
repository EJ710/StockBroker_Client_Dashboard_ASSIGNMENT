"""JWT session tokens.

After a user proves ownership of their email via OTP, we issue a signed JWT.
The frontend stores it and sends it back as `Authorization: Bearer <token>`
on REST calls, or as a `?token=` query param when opening the WebSocket.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time

import jwt  # PyJWT

from .config import settings

# --- Password hashing (stdlib PBKDF2-HMAC-SHA256, no extra dependency) ------
# Stored format:  pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
_PBKDF2_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    """Hash a plaintext password with a random per-user salt."""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt, _PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check of a plaintext password against a stored hash."""
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iters)
        )
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


def create_access_token(user_id: int, email: str) -> str:
    """Create a signed JWT carrying the user's id and email."""
    now = int(time.time())
    payload = {
        "sub": str(user_id),          # standard "subject" claim = user id
        "email": email,
        "iat": now,                    # issued-at
        "exp": now + settings.JWT_EXPIRE_MINUTES * 60,  # expiry
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Return the token payload, or None if invalid/expired."""
    try:
        return jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.PyJWTError:
        return None
