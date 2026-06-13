"""Authentication routes: registration (email-verified via OTP) + login.

Flow:
    POST /api/auth/register      { name, email, password }  -> emails an OTP
    POST /api/auth/verify-email  { email, code }            -> activates + JWT
    POST /api/auth/login         { email, password }        -> JWT
    POST /api/auth/resend-otp    { email }                  -> re-emails an OTP
    GET  /api/auth/me            (Bearer token)             -> current user

The OTP's job is to verify the email address **at registration time** — a new
account stays `verified = 0` and cannot log in until the code is confirmed.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from .. import database as db
from .. import otp as otp_service
from ..deps import get_current_user
from ..schemas import (
    LoginIn,
    MeOut,
    RegisterIn,
    RegisterOut,
    ResendOtpIn,
    ResendOtpOut,
    TokenOut,
    VerifyEmailIn,
)
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=RegisterOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn) -> RegisterOut:
    """Create an unverified account and email a verification code.

    * Brand-new email      -> create the user (verified = 0).
    * Existing & unverified -> refresh their details and re-send a code
      (lets someone who abandoned signup simply try again).
    * Existing & verified   -> reject; they should log in instead.
    """
    email = body.email.strip().lower()
    existing = db.get_user_by_email(email)

    if existing and existing["verified"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists. Please log in.",
        )

    pw_hash = hash_password(body.password)
    if existing:
        db.update_user_credentials(email, body.name, pw_hash)
    else:
        db.create_user(body.name, email, pw_hash)

    dev_code = otp_service.generate_and_send_otp(email)
    return RegisterOut(
        message="Account created. Enter the code we emailed to verify your address.",
        requires_verification=True,
        dev_code=dev_code,  # None unless DEV_MODE
    )


@router.post("/verify-email", response_model=TokenOut)
def verify_email(body: VerifyEmailIn) -> TokenOut:
    """Confirm the registration OTP, activate the account, and log the user in."""
    email = body.email.strip().lower()
    user = db.get_user_by_email(email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No registration found for this email.",
        )

    result = otp_service.verify_otp(email, body.code)
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=result.reason
        )

    db.set_user_verified(email)
    token = create_access_token(user_id=user["id"], email=email)
    # Auto-login after successful verification for a smooth UX.
    return TokenOut(access_token=token, email=email, name=user["name"])


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn) -> TokenOut:
    """Email + password login. Requires a verified account."""
    email = body.email.strip().lower()
    user = db.get_user_by_email(email)

    # Use the same generic message for "no user" and "wrong password" so we
    # don't reveal which emails are registered.
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password.",
    )
    if user is None or not verify_password(body.password, user["password_hash"]):
        raise invalid

    if not user["verified"]:
        # 403 (distinct from bad creds) so the UI can offer to re-send a code.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please verify your email to continue.",
        )

    token = create_access_token(user_id=user["id"], email=email)
    return TokenOut(access_token=token, email=email, name=user["name"])


@router.post("/resend-otp", response_model=ResendOtpOut)
def resend_otp(body: ResendOtpIn) -> ResendOtpOut:
    """Re-send a verification code for an unverified account."""
    email = body.email.strip().lower()
    user = db.get_user_by_email(email)
    # Respond the same way whether or not the account exists / is verified,
    # to avoid leaking which emails are registered.
    if user is None or user["verified"]:
        return ResendOtpOut(
            message="If that account needs verification, a new code has been sent."
        )
    dev_code = otp_service.generate_and_send_otp(email)
    return ResendOtpOut(
        message="A new verification code has been sent.", dev_code=dev_code
    )


@router.get("/me", response_model=MeOut)
def me(user: dict = Depends(get_current_user)) -> MeOut:
    return MeOut(
        id=user["id"],
        name=user["name"],
        email=user["email"],
        verified=bool(user["verified"]),
    )
