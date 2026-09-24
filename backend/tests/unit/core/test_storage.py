"""Storage + Config unit tests (backend.core)."""

from __future__ import annotations

import json
import os

import pytest

from backend.core.config import Config
from backend.core.storage import AnalysisRepository

COMPONENT = "Core/Storage"
STAGE = "repository"


def test_config_storage_path_is_absolute():
    assert Config.STORAGE_PATH
    assert os.path.isabs(Config.STORAGE_PATH)


def test_repository_create_and_get(isolated_storage):
    repo = isolated_storage
    repo.create("abc")
    rec = repo.get("abc")
    assert rec is not None
    assert rec["status"] == "processing"


def test_repository_complete(isolated_storage):
    repo = isolated_storage
    repo.complete("xyz", {"preview": {"rows": 5}})
    rec = repo.get("xyz")
    assert rec["status"] == "completed"
    assert rec["preview"] == {"rows": 5}


def test_repository_fail(isolated_storage):
    repo = isolated_storage
    repo.fail("bad", "boom")
    rec = repo.get("bad")
    assert rec["status"] == "failed"
    assert rec["error"] == "boom"


def test_repository_missing_returns_none(isolated_storage):
    assert isolated_storage.get("does-not-exist") is None


def test_repository_persists_to_disk(isolated_storage):
    repo = isolated_storage
    repo.create("disk1")
    # Simulate a process restart by clearing the in-memory records
    repo._records.clear()
    rec = repo.get("disk1")
    assert rec is not None, "session must be recoverable from disk after memory loss"
    assert rec["status"] == "processing"


def test_repository_get_strips_whitespace(isolated_storage):
    repo = isolated_storage
    repo.create("pad")
    assert repo.get("  pad  ") is not None


def test_repository_unchanged_input_not_mutated(isolated_storage):
    repo = isolated_storage
    artifacts = {"preview": {"a": 1}}
    repo.complete("m", artifacts)
    assert artifacts["preview"] == {"a": 1}