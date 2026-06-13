"""Pydantic request/response models.

These define and validate the JSON shapes the API accepts and returns, and they
power the automatic interactive documentation at /docs.
"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


# --- Auth ------------------------------------------------------------------
class RegisterIn(BaseModel):
    """Sign-up form: name, email and a password (min 8 chars)."""

    name: str = Field(..., min_length=1, max_length=80, examples=["Alice Smith"])
    email: EmailStr = Field(..., examples=["alice@example.com"])
    password: str = Field(..., min_length=8, max_length=128, examples=["s3cret-pw"])


class RegisterOut(BaseModel):
    message: str
    # Front-end uses this to jump to the "enter code" step.
    requires_verification: bool = True
    # Only populated in DEV_MODE so testers can verify without an inbox.
    dev_code: str | None = None


class VerifyEmailIn(BaseModel):
    """Submit the OTP that was emailed during registration."""

    email: EmailStr
    code: str = Field(..., min_length=4, max_length=8, examples=["123456"])


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(..., examples=["s3cret-pw"])


class ResendOtpIn(BaseModel):
    email: EmailStr


class ResendOtpOut(BaseModel):
    message: str
    dev_code: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str
    name: str


class MeOut(BaseModel):
    id: int
    name: str
    email: str
    verified: bool


# --- Stocks ----------------------------------------------------------------
class SupportedStockOut(BaseModel):
    ticker: str
    name: str


class SubscribeIn(BaseModel):
    ticker: str = Field(..., examples=["GOOG"])


class SubscriptionsOut(BaseModel):
    tickers: list[str]
