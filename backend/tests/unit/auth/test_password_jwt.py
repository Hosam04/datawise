"""Auth micro-services unit tests (backend.auth.password / jwt_handler).

bcrypt and python-jose are self-contained: no DB or network is involved for
these helpers.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from backend.auth.password import _truncate_password, hash_password, verify_password
from backend.auth.jwt_handler import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_access_token,
    verify_refresh_token,
)

COMPONENT = "Auth"
STAGE = "password/jwt"


# --------------------------------------------------------------------------
# Password hashing
# --------------------------------------------------------------------------

def test_hash_and_verify():
    hashed = hash_password("S3cret!pass")
    assert hashed
    assert verify_password("S3cret!pass", hashed) is True


def test_verify_wrong_password():
    hashed = hash_password("correct horse")
    assert verify_password("wrong", hashed) is False


def test_hash_is_salted():
    h1 = hash_password("same-pass")
    h2 = hash_password("same-pass")
    assert h1 != h2  # unique salt per call


def test_truncate_password_limits_to_72_bytes():
    long_pw = "x" * 200
    truncated = _truncate_password(long_pw)
    assert len(truncated) <= 72


def test_truncate_respects_utf8_boundary_bug():
    """BUG-AUTH-01: when the 72-byte slice ends exactly on the FIRST byte of a
    multi-byte UTF-8 character, _truncate_password does not strip it. The
    loop only removes continuation bytes (0b10xxxxxx), so a trailing lead
    byte survives, producing an undecodable password fragment."""
    from backend.auth.password import _truncate_password

    pw = "é" * 100  # 2-byte chars -> 200 bytes
    truncated = _truncate_password(pw)
    try:
        truncated.decode("utf-8")
        ok = True
    except UnicodeDecodeError:
        ok = False
    assert ok, (
        "[AUTH-001] Auth | stage=password | severity=MEDIUM\n"
        "  expected _truncate_password to never split a UTF-8 codepoint\n"
        f"  actual: {len(truncated)} bytes that fail to decode\n"
        "  likely root cause: password.py:12 while-loop only strips continuation "
        "bytes, not a trailing lead byte"
    )


def test_hash_verify_with_multibyte():
    hashed = hash_password("pässwörd-مرحبا")
    assert verify_password("pässwörd-مرحبا", hashed) is True


# --------------------------------------------------------------------------
# JWT
# --------------------------------------------------------------------------

def test_create_and_verify_access_token():
    token = create_access_token({"sub": "user-1"})
    payload = verify_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user-1"
    assert payload["type"] == "access"


def test_create_and_verify_refresh_token():
    token = create_refresh_token({"sub": "user-1"})
    payload = verify_refresh_token(token)
    assert payload is not None
    assert payload["type"] == "refresh"


def test_access_token_rejected_as_refresh():
    token = create_access_token({"sub": "u"})
    assert verify_refresh_token(token) is None


def test_refresh_token_rejected_as_access():
    token = create_refresh_token({"sub": "u"})
    assert verify_access_token(token) is None


def test_decode_garbage_token_returns_none():
    assert decode_token("not.a.jwt") is None


def test_expired_token_returns_none():
    token = create_access_token({"sub": "u"}, expires_delta=timedelta(seconds=-10))
    assert verify_access_token(token) is None


def test_algorithm_is_hs256():
    assert ALGORITHM.lower() == "hs256"


def test_access_expiry_configured():
    assert ACCESS_TOKEN_EXPIRE_MINUTES > 0