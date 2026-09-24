from __future__ import annotations

import uuid
from typing import Optional

from fastapi import Depends, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.auth.jwt_handler import verify_access_token
from backend.database.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

# Shared guest account used when no valid JWT is present (keeps FK constraint happy
# without forcing every caller to be authenticated).
_GUEST_EMAIL = "admin@admin.local"


def get_or_create_guest_user(db: Session) -> User:
    """Return a persistent guest user, creating it once if needed."""
    guest = db.query(User).filter(User.email == _GUEST_EMAIL).first()
    if guest:
        return guest
    guest = User(
        name="Guest",
        email=_GUEST_EMAIL,
        password_hash=None,
        provider="guest",
    )
    db.add(guest)
    db.commit()
    db.refresh(guest)
    return guest


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_uuid = uuid.UUID(str(user_id))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Soft auth for endpoints that should keep working even without a token
    (e.g. dataset upload while frontend still uses local auth).
    Falls back to a shared guest user instead of raising 401.
    """
    if not token:
        return get_or_create_guest_user(db)

    payload = verify_access_token(token)
    if not payload:
        return get_or_create_guest_user(db)

    user_id = payload.get("sub")
    if not user_id:
        return get_or_create_guest_user(db)

    try:
        user_uuid = uuid.UUID(str(user_id))
    except (ValueError, TypeError):
        return get_or_create_guest_user(db)

    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        return get_or_create_guest_user(db)

    return user