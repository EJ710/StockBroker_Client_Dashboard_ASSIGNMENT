"""Application configuration.

All settings are read from environment variables (optionally loaded from a
`.env` file) with safe defaults, so the app runs with zero configuration.

We deliberately avoid extra dependencies (like pydantic-settings) and just use
the standard library here — it keeps the config layer small and obvious.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Tiny .env loader ------------------------------------------------------
# We parse a `.env` file by hand (KEY=VALUE lines) instead of pulling in a
# third-party library. Lines starting with '#' and blank lines are ignored.
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Existing real environment variables take precedence over the file.
        os.environ.setdefault(key, value)


_load_dotenv(_ENV_PATH)


def _get_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


class Settings:
    """Strongly-named accessors for every configurable value."""

    # Security
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-insecure-secret-change-me")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = _get_int("JWT_EXPIRE_MINUTES", 720)

    # OTP
    OTP_TTL_SECONDS: int = _get_int("OTP_TTL_SECONDS", 300)
    OTP_LENGTH: int = 6
    OTP_MAX_ATTEMPTS: int = 5  # wrong guesses allowed before a code is burned
    DEV_MODE: bool = _get_bool("DEV_MODE", True)

    # SMTP (only used when DEV_MODE is false AND SMTP_HOST is set)
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = _get_int("SMTP_PORT", 587)
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "no-reply@stockbroker.local")

    # CORS
    CORS_ORIGINS: list[str] = [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if o.strip()
    ]

    # Price engine
    PRICE_TICK_SECONDS: float = float(os.getenv("PRICE_TICK_SECONDS", "1"))

    # Where the SQLite file lives (next to the backend folder).
    DB_PATH: str = str(Path(__file__).resolve().parent.parent / "stockbroker.db")


settings = Settings()
