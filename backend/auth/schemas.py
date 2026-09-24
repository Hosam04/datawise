from datetime import datetime
from typing import Optional, Any
from uuid import UUID
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email(v: Any) -> str:
    if not isinstance(v, str):
        raise ValueError("Email must be a string")
    email = v.strip().lower()
    if not email or not _EMAIL_RE.match(email):
        raise ValueError("Please enter a valid email address")
    return email


def _validate_name(v: Any) -> str:
    if not isinstance(v, str):
        raise ValueError("Name must be a string")
    name = v.strip()
    if len(name) < 2:
        raise ValueError("Name must be at least 2 characters")
    if len(name) > 100:
        raise ValueError("Name must be at most 100 characters")
    return name


class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: str
    password: str = Field(..., min_length=6)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: Any) -> str:
        return _validate_email(v)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: Any) -> str:
        return _validate_name(v)


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: Any) -> str:
        return _validate_email(v)

    @field_validator("password", mode="before")
    @classmethod
    def require_password(cls, v: Any) -> str:
        if not isinstance(v, str) or not v:
            raise ValueError("Password is required")
        return v


class GoogleLoginRequest(BaseModel):
    id_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    picture: Optional[str] = None
    provider: Optional[str] = None
    created_at: datetime
    last_login: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id_to_str(cls, v: Any) -> str:
        if isinstance(v, UUID):
            return str(v)
        return str(v)


class UserUpdateRequest(BaseModel):
    """Fields the authenticated user may update on their own record."""

    name: str

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: Any) -> str:
        return _validate_name(v)


class LoginResponse(BaseModel):
    user: UserResponse
    tokens: TokenResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class MessageResponse(BaseModel):
    message: str