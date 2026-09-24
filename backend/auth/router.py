import os
import re
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from backend.database.database import get_db
from backend.auth.schemas import (
    UserCreate,
    LoginRequest,
    LoginResponse,
    UserResponse,
    UserUpdateRequest,
    GoogleLoginRequest,
    RefreshTokenRequest,
    TokenResponse,
)
from backend.auth.service import register_user, authenticate_user
from backend.auth.oauth_google import verify_google_token
from backend.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
)
from backend.auth.dependencies import get_current_user
from backend.core.config import Config
from backend.database.models import User, Favorite  # noqa: F401 — register mapper


router = APIRouter(prefix="/auth", tags=["auth"])

# ─── Profile picture upload ───
# Images are stored as files under STORAGE_PATH/profiles and the users.picture
# column keeps only the public reference path (/profiles/<user>_<nonce>.<ext>),
# so huge base64 blobs never end up in PostgreSQL.
ALLOWED_PICTURE_RULES = {
    "image/jpeg": (".jpg", b"\xff\xd8\xff"),
    "image/png": (".png", b"\x89PNG\r\n\x1a\n"),
}
MAX_PROFILE_PICTURE_BYTES = 2 * 1024 * 1024  # 2 MB, matches the frontend.
_PICTURE_PATH_RE = re.compile(r"^[0-9a-f-]{36}_[0-9]{13}\.(jpg|png)$")


def _profiles_dir() -> str:
    profiles_dir = os.path.join(Config.STORAGE_PATH, "profiles")
    os.makedirs(profiles_dir, exist_ok=True)
    return profiles_dir


def _picture_filename(reference: str) -> str | None:
    """Return the filename part of a stored reference, or None if it is not ours."""
    if not reference or not reference.startswith("/profiles/"):
        return None
    name = reference[len("/profiles/"):]
    if not _PICTURE_PATH_RE.match(name):
        return None
    return name


def _remove_old_picture(reference: str) -> None:
    """Best-effort delete of a previously stored profile picture file."""
    name = _picture_filename(reference)
    if not name:
        return
    try:
        path = os.path.join(_profiles_dir(), name)
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


def _save_profile_picture(user: User, data: bytes, ext: str) -> str:
    """Write the picture file and return its public /profiles/... reference."""
    nonce = int(time.time() * 1000)
    filename = f"{user.id}_{nonce}{ext}"
    with open(os.path.join(_profiles_dir(), filename), "wb") as f:
        f.write(data)
    return f"/profiles/{filename}"


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, db: Session = Depends(get_db)):
    try:
        return register_user(db, user.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    result = authenticate_user(db, request.email, request.password)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return result

@router.post("/google", response_model=LoginResponse)
def google_login(request: GoogleLoginRequest, db: Session = Depends(get_db)):
    
    google_info = verify_google_token(request.id_token)
    if not google_info:
        raise HTTPException(status_code=401, detail="Invalid Google token")
    

    email = google_info.get("email")
    name = google_info.get("name")
    picture = google_info.get("picture")

    if not email:
        raise HTTPException(status_code=401, detail="Google token did not contain an email")
    
    user = db.query(User).filter(User.email == email).first()

    now = datetime.now(timezone.utc)
    if not user:
        # OAuth users have no local password — password_hash is nullable
        user = User(
            name=name or email.split("@")[0],
            email=email,
            picture=picture,
            provider="google",
            password_hash=None,
            last_login=now,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.last_login = now
        if picture and not user.picture:
            user.picture = picture
        db.commit()
        db.refresh(user)

    tokens = {
        "access_token": create_access_token({"sub": str(user.id)}),
        "refresh_token": create_refresh_token({"sub": str(user.id)}),
    }

    return {"user": user, "tokens": tokens}

@router.post("/refresh", response_model=TokenResponse)
def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Exchange a valid refresh token for a new access token (and a rotated refresh token)
    """

    payload = verify_refresh_token(request.refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Invalide or expired refresh token", 
            headers={"WWW-Authenticate":"Bearer"},
            )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalide or expired refresh token",
            headers={"WWW-Authenticate":"Bearer"},
        )

    try:
        user_uuid = uuid.UUID(str(user_id))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(user_id == user_uuid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found", 
            headers={"WWW-Authenticate":"bearer"}
        )

    new_access = create_access_token({"sub": str(user.id)})
    new_refresh = create_refresh_token({"sub": str(user.id)})

    return{
        "access_token" : new_access,
        "refresh_token" : new_refresh,
        "token_type" : "bearer"
    }

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """return th currently authenicated user"""
    return current_user


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the authenticated user's own display name.

    The user is resolved from the JWT (get_current_user), so this can never
    affect another account. The change is committed to PostgreSQL and the
    updated user record is returned.
    """
    current_user.name = payload.name
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/picture", response_model=UserResponse)
def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload/replace the authenticated user's profile picture (JPG/PNG, <= 2 MB).

    The image bytes are stored as a file under storage/profiles and the
    users.picture column keeps only the /profiles/... reference. An existing
    picture file is replaced (removed) when a new one is uploaded.
    """
    content_type = (file.content_type or "").lower()
    rule = ALLOWED_PICTURE_RULES.get(content_type)
    if rule is None:
        raise HTTPException(
            status_code=400, detail="Profile picture must be a JPG or PNG image"
        )
    ext, magic = rule

    data = file.file.read(MAX_PROFILE_PICTURE_BYTES + 1)
    if len(data) > MAX_PROFILE_PICTURE_BYTES:
        raise HTTPException(
            status_code=400, detail="Profile picture must be under 2 MB"
        )
    if len(data) == 0 or not data.startswith(magic):
        raise HTTPException(
            status_code=400, detail="Image content does not match its file type"
        )

    _remove_old_picture(current_user.picture)
    current_user.picture = _save_profile_picture(current_user, data, ext)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.delete("/me/picture", response_model=UserResponse)
def remove_profile_picture(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete the authenticated user's stored profile picture."""
    _remove_old_picture(current_user.picture)
    current_user.picture = None
    db.commit()
    db.refresh(current_user)
    return current_user