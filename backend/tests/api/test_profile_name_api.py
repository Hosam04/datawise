"""API tests for updating the authenticated user's display name (PATCH /auth/me).

The update reuses the existing users row (never creates a second record) and the
caller is identified purely by the JWT, so one user can never rename another.
"""

from __future__ import annotations

import uuid

import pytest


@pytest.fixture
def register_login(client):
    """Register + log in a fresh user; return (client, auth headers, email)."""

    def _make():
        suffix = uuid.uuid4().hex[:12]
        email = f"name-{suffix}@example.test"
        payload = {"name": "Original Name", "email": email, "password": "secret123"}
        reg = client.post("/auth/register", json=payload)
        assert reg.status_code == 201, reg.text
        login = client.post(
            "/auth/login", json={"email": email, "password": "secret123"}
        )
        assert login.status_code == 200, login.text
        token = login.json()["tokens"]["access_token"]
        return client, {"Authorization": f"Bearer {token}"}, email

    return _make


def test_update_name_requires_auth(client):
    res = client.patch("/auth/me", json={"name": "Hacker"})
    assert res.status_code in (401, 403)


def test_update_name_persists_to_postgres(client, register_login):
    c, headers, _ = register_login()

    res = c.patch("/auth/me", json={"name": "  New Name  "}, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["name"] == "New Name"
    assert data["email"].endswith("@example.test")

    # The same user record is returned by GET /auth/me (reads from PostgreSQL),
    # proving the change survived the write to the users table.
    me = c.get("/auth/me", headers=headers)
    assert me.json()["id"] == data["id"]
    assert me.json()["name"] == "New Name"

    # Direct DB check: exactly one users row for this address, with new name.
    from backend.database.database import SessionLocal
    from backend.database.models import User

    with SessionLocal() as db:
        rows = (
            db.query(User).filter(User.email == data["email"]).all()
        )
        assert len(rows) == 1
        assert rows[0].name == "New Name"
        assert str(rows[0].id) == data["id"]


def test_update_name_rejects_short_or_blank(client, register_login):
    c, headers, _ = register_login()
    for bad in ["", "   ", "A", "x"]:
        res = c.patch("/auth/me", json={"name": bad}, headers=headers)
        assert res.status_code == 422, f"expected 422 for {bad!r}, got {res.status_code}"
    # Nothing changed for any rejected value.
    me = c.get("/auth/me", headers=headers)
    assert me.json()["name"] == "Original Name"


def test_update_name_cannot_touch_other_user(client, register_login):
    c, headers_a, _ = register_login()
    _, headers_b, _ = register_login()

    res_a = c.patch("/auth/me", json={"name": "Renamed A"}, headers=headers_a)
    assert res_a.status_code == 200

    # There is no user-id in the request URL/body — the token fully determines
    # which account is updated, so B's name is untouched.
    me_b = c.get("/auth/me", headers=headers_b)
    assert me_b.json()["name"] == "Original Name"
    me_a = c.get("/auth/me", headers=headers_a)
    assert me_a.json()["name"] == "Renamed A"