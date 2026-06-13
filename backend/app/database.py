"""SQLite persistence layer (standard library `sqlite3`, no ORM).

Three tables:

  users          — one row per email that has ever logged in
  subscriptions  — many-to-one: which tickers each user watches
  otp_codes      — outstanding one-time login codes (hashed), with expiry

We keep the access pattern simple: every call opens a short-lived connection
via a context manager. SQLite handles the file locking. `check_same_thread`
is left at its default because each connection is used within a single call.
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from typing import Iterator

from .config import settings


# --- Connection helper -----------------------------------------------------
@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    """Yield a connection with Row access and foreign keys enabled."""
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# --- Schema ----------------------------------------------------------------
def init_db() -> None:
    """Create tables if they do not yet exist. Safe to call on every startup."""
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                name           TEXT NOT NULL,
                email          TEXT NOT NULL UNIQUE,
                password_hash  TEXT NOT NULL,
                verified       INTEGER NOT NULL DEFAULT 0,
                created_at     REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                ticker      TEXT NOT NULL,
                created_at  REAL NOT NULL,
                UNIQUE(user_id, ticker),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS otp_codes (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                email        TEXT NOT NULL,
                code_hash    TEXT NOT NULL,
                expires_at   REAL NOT NULL,
                attempts     INTEGER NOT NULL DEFAULT 0,
                consumed     INTEGER NOT NULL DEFAULT 0,
                created_at   REAL NOT NULL
            );
            """
        )


# --- User helpers ----------------------------------------------------------
def create_user(name: str, email: str, password_hash: str) -> dict:
    """Insert a new (unverified) user. Caller must ensure email is free."""
    email = email.strip().lower()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (name, email, password_hash, verified, created_at) "
            "VALUES (?, ?, ?, 0, ?)",
            (name.strip(), email, password_hash, time.time()),
        )
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        return dict(row)


def update_user_credentials(email: str, name: str, password_hash: str) -> None:
    """Overwrite name + password for an existing (still unverified) user.

    Used when someone re-submits the registration form before verifying — we
    refresh their details rather than erroring out.
    """
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET name = ?, password_hash = ? WHERE email = ?",
            (name.strip(), password_hash, email.strip().lower()),
        )


def set_user_verified(email: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET verified = 1 WHERE email = ?",
            (email.strip().lower(),),
        )


def get_user_by_email(email: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.strip().lower(),)
        ).fetchone()
        return dict(row) if row else None


# --- Subscription helpers --------------------------------------------------
def list_subscriptions(user_id: int) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT ticker FROM subscriptions WHERE user_id = ? ORDER BY ticker",
            (user_id,),
        ).fetchall()
        return [r["ticker"] for r in rows]


def add_subscription(user_id: int, ticker: str) -> bool:
    """Add a ticker to a user's watchlist. Returns False if already present."""
    with get_conn() as conn:
        try:
            conn.execute(
                "INSERT INTO subscriptions (user_id, ticker, created_at) "
                "VALUES (?, ?, ?)",
                (user_id, ticker, time.time()),
            )
            return True
        except sqlite3.IntegrityError:
            return False  # UNIQUE(user_id, ticker) violated -> already subscribed


def remove_subscription(user_id: int, ticker: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM subscriptions WHERE user_id = ? AND ticker = ?",
            (user_id, ticker),
        )
        return cur.rowcount > 0


# --- OTP helpers -----------------------------------------------------------
def save_otp(email: str, code_hash: str, ttl_seconds: int) -> None:
    """Store a new OTP, invalidating any previous unconsumed codes for email."""
    now = time.time()
    with get_conn() as conn:
        # Burn older codes so only the most recent one is valid.
        conn.execute(
            "UPDATE otp_codes SET consumed = 1 WHERE email = ? AND consumed = 0",
            (email,),
        )
        conn.execute(
            "INSERT INTO otp_codes (email, code_hash, expires_at, created_at) "
            "VALUES (?, ?, ?, ?)",
            (email, code_hash, now + ttl_seconds, now),
        )


def get_active_otp(email: str) -> dict | None:
    """Return the latest unconsumed, unexpired OTP row for email (or None)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM otp_codes "
            "WHERE email = ? AND consumed = 0 AND expires_at > ? "
            "ORDER BY id DESC LIMIT 1",
            (email, time.time()),
        ).fetchone()
        return dict(row) if row else None


def increment_otp_attempts(otp_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE otp_codes SET attempts = attempts + 1 WHERE id = ?", (otp_id,)
        )


def consume_otp(otp_id: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE otp_codes SET consumed = 1 WHERE id = ?", (otp_id,))
