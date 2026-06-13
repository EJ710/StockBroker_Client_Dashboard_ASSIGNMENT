"""Shared FastAPI dependencies — chiefly 'who is the current user?'.

`get_current_user` reads the `Authorization: Bearer <token>` header, validates
the JWT, and returns the user record. Any route that depends on it is therefore
protected: a missing or bad token yields 401.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import database as db
from .security import decode_access_token

# `HTTPBearer` makes the Swagger "Authorize" button appear and parses the header.
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    payload = decode_access_token(creds.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    user = db.get_user_by_email(payload.get("email", ""))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
        )
    return user
