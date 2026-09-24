"""Pytest fixtures for the DataWise test suite.

The suite runs *against the real backend*: no backend module is patched in
these fixtures unless required to isolate filesystem/storage side effects that
would otherwise bleed across tests (session storage directory, repository
singleton, FastAPI test client).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]  # repo root (contains backend/)
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@pytest.fixture(scope="session")
def datasets_dir() -> Path:
    return Path(__file__).resolve().parent / "datasets"


@pytest.fixture
def load_dataset(datasets_dir):
    """Return a callable that reads a dataset CSV by name."""

    def _load(name: str, **kwargs) -> pd.DataFrame:
        path = datasets_dir / name
        assert path.is_file(), f"dataset file not found: {path}"
        return pd.read_csv(path, **kwargs)

    return _load


@pytest.fixture
def read_any_file():
    """Thin wrapper over the production CSV reader for convenience."""
    from backend.tools.csv_reader import read_any_file

    return read_any_file


@pytest.fixture
def cleaning_engine():
    from backend.cleaning import CleaningEngine

    return CleaningEngine(add_outlier_flags=True)

@pytest.fixture
def stats_engine():
    from backend.statistics import StatisticalEngine

    return StatisticalEngine(correlation_method="spearman", outlier_method="iqr", outlier_threshold=1.5)


@pytest.fixture
def isolated_storage(tmp_path, monkeypatch):
    """Point Config.STORAGE_PATH at a temp dir and reset the analysis repo.

    This keeps every test (especially API tests) from touching the real
    ``storage/`` directory of the repository.
    """
    from backend.core.config import Config
    from backend.core.storage import analysis_repository

    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Config, "STORAGE_PATH", str(storage_dir))
    analysis_repository._records.clear()
    yield analysis_repository
    analysis_repository._records.clear()


@pytest.fixture(scope="module")
def repository_isolation(monkeypatch):
    """Module-scoped isolation: unique storage path + cleared repository."""
    import tempfile

    from backend.core.config import Config
    from backend.core.storage import analysis_repository

    storage_dir = Path(tempfile.mkdtemp(prefix="datawise-tests-"))
    monkeypatch.setattr(Config, "STORAGE_PATH", str(storage_dir))
    analysis_repository._records.clear()
    return analysis_repository


@pytest.fixture
def state_factory(tmp_path):
    """Factory for a minimal AgentState pointing at a temp session dir."""
    from backend.core.state import AgentState

    def _make(**overrides):
        session_id = overrides.pop("session_id", "session-test")
        session_dir = overrides.pop("session_dir", str(tmp_path / "sessions" / session_id))
        file_path = overrides.pop("file_path", str(tmp_path / "dataset.csv"))
        user_query = overrides.pop("user_query", "Analyze this dataset")
        os.makedirs(session_dir, exist_ok=True)
        return AgentState(
            session_id=session_id,
            session_dir=session_dir,
            file_path=file_path,
            user_query=user_query,
            **overrides,
        )

    return _make


@pytest.fixture
def client():
    """FastAPI TestClient against the real app (no startup lifespan)."""
    from fastapi.testclient import TestClient

    from backend.app.main import app

    return TestClient(app)  # no context manager -> no startup side effects


@pytest.fixture
def disable_logging():
    """Silence noisy backend INFO logs during a test."""
    import logging

    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)


@pytest.fixture
def analyzer():
    """Fixture to provide an MLAnalyzer instance for unit tests."""
    from backend.ml.analyzer import MLAnalyzer
    return MLAnalyzer()