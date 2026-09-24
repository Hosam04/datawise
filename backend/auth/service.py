from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.database.models import User
from backend.auth.password import hash_password, verify_password
from backend.auth.jwt_handler import create_access_token, create_refresh_token


def register_user(db: Session, user_data: dict):
    raw_password = user_data.get("password")

    if not isinstance(raw_password, str):
        raise ValueError(f"Password must be a string, got {type(raw_password)}")

    hashed_pw = hash_password(raw_password)

    existing_user = db.query(User).filter(User.email == user_data["email"]).first()
    if existing_user:
        raise ValueError("Email already registered")

    new_user = User(
        name=user_data["name"],
        email=user_data["email"],
        password_hash=hashed_pw,
        provider="local",
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


def authenticate_user(db: Session, email: str, password: str):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None

    # OAuth-only accounts have no local password
    if not user.password_hash:
        return None

    if not verify_password(password, user.password_hash):
        return None

    user.last_login = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    tokens = {
        "access_token": create_access_token({"sub": str(user.id)}),
        "refresh_token": create_refresh_token({"sub": str(user.id)}),
    }
    return {"user": user, "tokens": tokens}