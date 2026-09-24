"""AgentState unit tests (backend.core.state)."""

from __future__ import annotations

import os

import pandas as pd
import pytest

from backend.core.state import AgentState
from backend.tests.assertions import check

COMPONENT = "Core/State"
STAGE = "AgentState"


def test_state_requires_core_fields():
    with pytest.raises(Exception):
        AgentState()


def test_state_defaults(state_factory):
    s = state_factory()
    assert s.session_id == "session-test"
    assert s.df is None
    assert s.df_path is None
    assert s.processed_columns == []
    assert s.visualization_paths == []
    assert s.insights is None
    assert s.final_report == ""
    assert s.analysis_type == "exploratory"
    assert s.error is None
    assert s.ml_results is None


def test_state_df_excluded_from_serialization(state_factory):
    s = state_factory()
    s.df = pd.DataFrame({"a": [1, 2]})
    payload = s.model_dump()
    assert "df" not in payload
    assert "session_id" in payload


def test_state_stores_ml_results(state_factory):
    from backend.ml.schemas import MLResults

    s = state_factory()
    s.ml_results = MLResults(status="success", problem_type="classification")
    assert s.ml_results.status == "success"


def test_state_get_df_from_path(state_factory, tmp_path):
    path = str(tmp_path / "df.pkl")
    pd.DataFrame({"a": [1, 2, 3]}).to_pickle(path)
    s = state_factory(file_path=path, df=None)
    s.df_path = path
    df = s.get_df()
    assert df is not None
    assert len(df) == 3


def test_state_get_df_missing_returns_none(state_factory, tmp_path):
    s = state_factory(file_path=str(tmp_path / "nope.pkl"))
    s.df_path = str(tmp_path / "nope.pkl")
    assert s.get_df() is None


def test_state_save_safe_csv(state_factory, tmp_path):
    s = state_factory()
    s.df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    out = s.save_safe_csv()
    assert out is not None
    assert os.path.exists(out)
    loaded = pd.read_csv(out)
    assert loaded.shape == (3, 2)