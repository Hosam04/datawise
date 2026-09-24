"""Unit tests for AgentState, Config, Storage, and Exceptions."""

import pytest
import pandas as pd
from backend.core.state import AgentState
from backend.core.storage import AnalysisRepository
from backend.core.config import Config
from backend.core.exceptions import DataWiseError, FileProcessingError, CleaningError


def test_agent_state_df_and_safe_csv(tmp_path):
    """Test AgentState dataframe persistence and safe CSV export."""
    df = pd.DataFrame({"x": [1, 2, 3], "y": ["a", "b", "c"]})
    state = AgentState(
        session_id="core-test-1",
        session_dir=str(tmp_path),
        file_path=str(tmp_path / "raw.csv"),
        user_query="test",
        df=df,
    )
    assert state.get_df() is not None
    assert len(state.get_df()) == 3

    csv_out = state.save_safe_csv("safe_export.csv")
    assert csv_out is not None
    assert pd.read_csv(csv_out).shape == (3, 2)


def test_analysis_repository_lifecycle():
    """Test repository create, update, complete, and fail lifecycle."""
    repo = AnalysisRepository()
    session_id = "test-session-repo"

    repo.create(session_id)
    rec = repo.get(session_id)
    assert rec["status"] == "processing"

    repo.complete(session_id, {"result": 42})
    rec_done = repo.get(session_id)
    assert rec_done["status"] == "completed"
    assert rec_done["result"] == 42

    repo.fail("failed-session", "Memory error")
    rec_failed = repo.get("failed-session")
    assert rec_failed["status"] == "failed"
    assert rec_failed["error"] == "Memory error"
