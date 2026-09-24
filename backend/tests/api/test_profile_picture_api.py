"""API tests for the profile picture upload/delete/serve flow.

The upload endpoint persists the image as a file under Config.STORAGE_PATH/
profiles and stores only the /profiles/... reference in users.picture.
Requires a reachable PostgreSQL database (the app rejects SQLite).
"""

from __future__ import annotations

import os
import uuid

import pytest

JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01"
PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"


@pytest.fixture
def register_login(client):
    """Register + log in a fresh user; return (client, auth headers, email)."""

    def _make():
        suffix = uuid.uuid4().hex[:12]
        email = f"pic-{suffix}@example.test"
        payload = {"name": "Picture Tester", "email": email, "password": "secret123"}
        reg = client.post("/auth/register", json=payload)
        assert reg.status_code == 201, reg.text
        login = client.post(
            "/auth/login", json={"email": email, "password": "secret123"}
        )
        assert login.status_code == 200, login.text
        token = login.json()["tokens"]["access_token"]
        return client, {"Authorization": f"Bearer {token}"}, email

    return _make


def _profiles_path(client, ref: str) -> str:
    from backend.core.config import Config

    name = ref[len("/profiles/"):]
    return os.path.join(Config.STORAGE_PATH, "profiles", name)


def test_upload_requires_auth(client):
    res = client.post(
        "/auth/me/picture",
        files={"file": ("photo.jpg", JPEG_BYTES, "image/jpeg")},
    )
    assert res.status_code in (401, 403)


def test_delete_requires_auth(client):
    res = client.delete("/auth/me/picture")
    assert res.status_code in (401, 403)


def test_upload_saves_file_reference_and_serves_it(client, isolated_storage, register_login):
    c, headers, _ = register_login()

    res = c.post(
        "/auth/me/picture",
        files={"file": ("photo.jpg", JPEG_BYTES, "image/jpeg")},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["picture"].startswith("/profiles/")
    assert data["picture"].endswith(".jpg")

    # File exists on disk + reference is not the raw image bytes.
    path = _profiles_path(c, data["picture"])
    assert os.path.isfile(path)
    with open(path, "rb") as f:
        assert f.read() == JPEG_BYTES

    # Served back through the public reference URL.
    served = c.get(data["picture"])
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/jpeg"
    assert served.content == JPEG_BYTES

    # /auth/me returns the same reference for this user.
    me = c.get("/auth/me", headers=headers)
    assert me.json()["picture"] == data["picture"]


def test_replacing_picture_removes_previous_file(client, isolated_storage, register_login):
    c, headers, _ = register_login()

    first = c.post(
        "/auth/me/picture",
        files={"file": ("a.png", PNG_BYTES, "image/png")},
        headers=headers,
    )
    assert first.status_code == 200, first.text
    first_ref = first.json()["picture"]

    second = c.post(
        "/auth/me/picture",
        files={"file": ("b.jpg", JPEG_BYTES, "image/jpeg")},
        headers=headers,
    )
    assert second.status_code == 200, second.text
    second_ref = second.json()["picture"]
    assert second_ref != first_ref

    assert second.json()["picture"] == second_ref
    assert not os.path.isfile(_profiles_path(c, first_ref))
    assert os.path.isfile(_profiles_path(c, second_ref))

    assert c.get(first_ref).status_code == 404
    assert c.get(second_ref).status_code == 200


def test_delete_picture_removes_file_and_clears_reference(client, isolated_storage, register_login):
    c, headers, _ = register_login()

    up = c.post(
        "/auth/me/picture",
        files={"file": ("photo.png", PNG_BYTES, "image/png")},
        headers=headers,
    )
    ref = up.json()["picture"]
    assert os.path.isfile(_profiles_path(c, ref))

    delete = c.delete("/auth/me/picture", headers=headers)
    assert delete.status_code == 200, delete.text
    assert delete.json()["picture"] is None

    assert not os.path.isfile(_profiles_path(c, ref))
    assert c.get(ref).status_code == 404
    assert c.get("/auth/me", headers=headers).json()["picture"] is None


def test_upload_rejects_unsupported_type(client, isolated_storage, register_login):
    c, headers, _ = register_login()
    res = c.post(
        "/auth/me/picture",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        headers=headers,
    )
    assert res.status_code == 400


def test_upload_rejects_oversize(client, isolated_storage, register_login):
    c, headers, _ = register_login()
    big = b"\xff\xd8\xff" + b"x" * (2 * 1024 * 1024)  # 2 MB + header bytes
    res = c.post(
        "/auth/me/picture",
        files={"file": ("photo.jpg", big, "image/jpeg")},
        headers=headers,
    )
    assert res.status_code == 400


def test_upload_rejects_mismatched_content(client, isolated_storage, register_login):
    c, headers, _ = register_login()
    # Content type claims JPEG but the bytes are not a JPEG image.
    res = c.post(
        "/auth/me/picture",
        files={"file": ("photo.jpg", b"<!DOCTYPE html>", "image/jpeg")},
        headers=headers,
    )
    assert res.status_code == 400


def test_cannot_modify_another_user(client, isolated_storage, register_login):
    c, headers_a, _ = register_login()
    _, headers_b, _ = register_login()

    res_a = c.post(
        "/auth/me/picture",
        files={"file": ("a.jpg", JPEG_BYTES, "image/jpeg")},
        headers=headers_a,
    )
    assert res_a.status_code == 200
    ref_a = res_a.json()["picture"]

    # B uses the same shared auth-less endpoint without any target user id —
    # the operation always acts on the authenticated user only.
    me_b_before = c.get("/auth/me", headers=headers_b).json()
    assert me_b_before["picture"] is None

    res_b = c.post(
        "/auth/me/picture",
        files={"file": ("b.png", PNG_BYTES, "image/png")},
        headers=headers_b,
    )
    assert res_b.status_code == 200
    ref_b = res_b.json()["picture"]
    assert ref_b != ref_a

    # B's upload must not touch A's stored picture.
    assert c.get("/auth/me", headers=headers_a).json()["picture"] == ref_a
    assert c.get(ref_a).status_code == 200