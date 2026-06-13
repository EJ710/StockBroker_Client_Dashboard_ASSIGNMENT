"""One-Time-Password (OTP) generation, delivery and verification.

Flow:
  1. User submits their email  -> generate_and_send_otp()
  2. We create a random 6-digit code, store only its SHA-256 hash, and deliver
     the plaintext code by email (or to the console in DEV_MODE).
  3. User submits email + code -> verify_otp() checks the hash, expiry and
     attempt count, then burns the code.

Security notes (why this is "realistic", not a toy):
  * The plaintext code is never stored — only a salted-by-secret hash.
  * Codes expire (default 5 min) and are single-use.
  * A limited number of wrong attempts burns the code (anti-brute-force).
  * Previous codes for an email are invalidated when a new one is requested.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import smtplib
from email.message import EmailMessage

from . import database as db
from .config import settings


def _hash_code(code: str) -> str:
    """Hash an OTP using HMAC-SHA256 keyed by the app secret.

    Using HMAC keyed with JWT_SECRET means a leaked database alone is not
    enough to validate codes — an attacker would also need the secret.
    """
    return hmac.new(
        settings.JWT_SECRET.encode(), code.encode(), hashlib.sha256
    ).hexdigest()


def _generate_code() -> str:
    """Cryptographically-strong N-digit numeric code (zero-padded)."""
    upper = 10 ** settings.OTP_LENGTH
    return str(secrets.randbelow(upper)).zfill(settings.OTP_LENGTH)


def _deliver(email: str, code: str) -> None:
    """Send the code by email, or print it to the console in DEV_MODE."""
    subject = "Your StockBroker login code"
    body = (
        f"Your one-time login code is: {code}\n\n"
        f"It expires in {settings.OTP_TTL_SECONDS // 60} minutes.\n"
        "If you did not request this, you can ignore this email."
    )

    # If SMTP isn't configured, fall back to console delivery regardless of mode
    # so the app never silently fails to deliver a code.
    if settings.SMTP_HOST:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM
        msg["To"] = email
        msg.set_content(body)
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        print(f"[OTP] Sent login code to {email} via SMTP.")
    else:
        # Console delivery — visible in the server logs.
        print("=" * 60)
        print(f"[OTP] Login code for {email}: {code}")
        print(f"[OTP] (expires in {settings.OTP_TTL_SECONDS}s)")
        print("=" * 60)


def generate_and_send_otp(email: str) -> str | None:
    """Create, store and deliver a fresh OTP for `email`.

    Returns the plaintext code ONLY in DEV_MODE (so the API can echo it back
    for easy testing); returns None otherwise.
    """
    email = email.strip().lower()
    code = _generate_code()
    db.save_otp(email, _hash_code(code), settings.OTP_TTL_SECONDS)
    _deliver(email, code)
    return code if settings.DEV_MODE else None


class OtpResult:
    """Tiny result object so callers can distinguish failure reasons."""

    def __init__(self, ok: bool, reason: str = "") -> None:
        self.ok = ok
        self.reason = reason


def verify_otp(email: str, code: str) -> OtpResult:
    """Validate a submitted code against the stored hash."""
    email = email.strip().lower()
    row = db.get_active_otp(email)
    if row is None:
        return OtpResult(False, "No active code. Please request a new one.")

    if row["attempts"] >= settings.OTP_MAX_ATTEMPTS:
        db.consume_otp(row["id"])
        return OtpResult(False, "Too many attempts. Please request a new code.")

    # Constant-time comparison to avoid timing attacks.
    if not hmac.compare_digest(row["code_hash"], _hash_code(code.strip())):
        db.increment_otp_attempts(row["id"])
        return OtpResult(False, "Incorrect code.")

    db.consume_otp(row["id"])  # single-use: burn it on success
    return OtpResult(True)
