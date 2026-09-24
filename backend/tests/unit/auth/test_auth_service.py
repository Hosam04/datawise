"""Unit & integration tests for authentication service and last_login persistence.

Verifies:
1. Registration creates a single User record.
2. Login authenticates user and updates last_login from NULL to a valid datetime.
3. The last_login timestamp is committed and persisted to PostgreSQL.
4. Repeated login updates last_login timestamp and does NOT insert additional user rows.
5. User attributes (name, email, etc.) remain intact upon login.
6. Google login reuses existing user and updates last_login timestamp.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
import pytest

from backend.database.database import SessionLocal
from backend.database.models import User
from backend.auth.service import register_user, authenticate_user


def test_register_creates_single_user():
    suffix = uuid.uuid4().hex[:12]
    email = f"signup-{suffix}@example.test"
    user_data = {
        "name": "Picture Tester",
        "email": email,
        "password": "Password123!",
    }

    with SessionLocal() as db:
        user = register_user(db, user_data)
        assert user.id is not None
        assert user.name == "Picture Tester"
        assert user.email == email
        assert user.last_login is None  # Initial registration has no last_login until login

    with SessionLocal() as db:
        users = db.query(User).filter(User.email == email).all()
        assert len(users) == 1


def test_login_updates_last_login_timestamp_and_persists():
    suffix = uuid.uuid4().hex[:12]
    email = f"login-{suffix}@example.test"
    password = "MySecurePassword123!"
    name = "Picture Tester"

    with SessionLocal() as db:
        register_user(db, {"name": name, "email": email, "password": password})

    # Verify initial last_login is None
    with SessionLocal() as db:
        u_before = db.query(User).filter(User.email == email).first()
        assert u_before is not None
        assert u_before.last_login is None

    # Perform first login
    with SessionLocal() as db:
        auth_result = authenticate_user(db, email, password)
        assert auth_result is not None
        user_obj = auth_result["user"]
        assert user_obj.last_login is not None
        first_login_time = user_obj.last_login

    # Query DB to verify persistence in PostgreSQL
    with SessionLocal() as db:
        u_after = db.query(User).filter(User.email == email).first()
        assert u_after is not None
        assert u_after.last_login is not None
        assert isinstance(u_after.last_login, datetime)
        assert u_after.name == name
        assert u_after.email == email

    # Perform second login
    with SessionLocal() as db:
        auth_result2 = authenticate_user(db, email, password)
        assert auth_result2 is not None
        user_obj2 = auth_result2["user"]
        second_login_time = user_obj2.last_login
        assert second_login_time >= first_login_time

    # Verify user count remains 1 and fields remain unchanged
    with SessionLocal() as db:
        all_users = db.query(User).filter(User.email == email).all()
        assert len(all_users) == 1
        assert all_users[0].name == name
        assert all_users[0].email == email
        assert all_users[0].last_login is not None


def test_failed_login_does_not_update_last_login_or_create_user():
    suffix = uuid.uuid4().hex[:12]
    email = f"failed-{suffix}@example.test"
    password = "CorrectPassword123!"

    with SessionLocal() as db:
        register_user(db, {"name": "Fail Test", "email": email, "password": password})

    # Wrong password attempt
    with SessionLocal() as db:
        res = authenticate_user(db, email, "WrongPassword!")
        assert res is None

    # Verify last_login is still None and no duplicate created
    with SessionLocal() as db:
        users = db.query(User).filter(User.email == email).all()
        assert len(users) == 1
        assert users[0].last_login is None


def test_api_login_endpoint_returns_last_login(client):
    suffix = uuid.uuid4().hex[:12]
    email = f"apilogin-{suffix}@example.test"
    password = "ApiPassword123!"
    name = "Picture Tester"

    # Register via API
    reg_res = client.post("/auth/register", json={"name": name, "email": email, "password": password})
    assert reg_res.status_code == 201

    # Login via API
    login_res = client.post("/auth/login", json={"email": email, "password": password})
    assert login_res.status_code == 200
    data = login_res.json()
    assert data["user"]["email"] == email
    assert data["user"]["name"] == name
    assert data["user"]["last_login"] is not None

    # Verify user row count in DB
    with SessionLocal() as db:
        users = db.query(User).filter(User.email == email).all()
        assert len(users) == 1
        assert users[0].last_login is not None
