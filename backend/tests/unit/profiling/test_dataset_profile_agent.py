"""Unit tests for DatasetProfileAgent and data profiling capabilities."""

import pytest
import pandas as pd
import numpy as np
from backend.agents.profile.dataset_profile_agent import DatasetProfileAgent
from backend.core.state import AgentState


def test_profile_agent_numeric_and_categorical_detection(tmp_path):
    """Test profiling correctly classifies numeric vs categorical columns."""
    df = pd.DataFrame({
        "id": [1, 2, 3, 4, 5],
        "age": [25, 30, 35, 40, 45],
        "salary": [50000.0, 60000.0, 75000.0, 80000.0, 95000.0],
        "department": ["Sales", "Engineering", "Sales", "HR", "Engineering"],
        "is_active": [True, False, True, True, False],
    })
    
    csv_path = tmp_path / "profile_data.csv"
    df.to_csv(csv_path, index=False)

    state = AgentState(
        session_id="profile-test-1",
        session_dir=str(tmp_path),
        file_path=str(csv_path),
        user_query="Profile this dataset",
        df=df,
    )

    agent = DatasetProfileAgent()
    out_state = agent.run(state)

    profile = out_state.dataset_profile
    assert profile is not None
    assert "numeric_columns" in profile or "columns" in profile
    assert out_state.data_summary.get("total_rows") == 5


def test_profile_agent_handles_empty_dataframe(tmp_path):
    """Test profiling gracefully handles an empty DataFrame without raising unhandled exceptions."""
    df = pd.DataFrame()
    csv_path = tmp_path / "empty_profile.csv"
    df.to_csv(csv_path, index=False)

    state = AgentState(
        session_id="empty-profile-test",
        session_dir=str(tmp_path),
        file_path=str(csv_path),
        user_query="Profile empty dataset",
        df=df,
    )

    agent = DatasetProfileAgent()
    out_state = agent.run(state)
    assert out_state is not None


def test_profile_agent_single_column(tmp_path):
    """Test profiling single column dataset."""
    df = pd.DataFrame({"single_col": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]})
    csv_path = tmp_path / "single_col.csv"
    df.to_csv(csv_path, index=False)

    state = AgentState(
        session_id="single-col-test",
        session_dir=str(tmp_path),
        file_path=str(csv_path),
        user_query="Profile single col",
        df=df,
    )

    agent = DatasetProfileAgent()
    out_state = agent.run(state)
    assert out_state.data_summary.get("total_cols") == 1
    assert out_state.data_summary.get("total_rows") == 10
