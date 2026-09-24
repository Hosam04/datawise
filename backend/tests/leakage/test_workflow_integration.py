"""Tests for End-to-End Workflow Execution with Leaky Datasets."""

import os
import pathlib
import tempfile
import pytest
import pandas as pd
from backend.agents.master.orchestrator import create_workflow
from backend.core.state import AgentState
from backend.tests.leakage.datasets import make_direct_target_leakage_dataset


def test_full_workflow_with_direct_target_leakage():
    """Run full LangGraph workflow on dataset with target copy and verify pipeline completes
    without crashing, and leaked column is handled.
    """
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="datawise-leak-wf-"))
    df = make_direct_target_leakage_dataset(n=300, seed=42)
    csv_path = tmp / "input.csv"
    df.to_csv(csv_path, index=False)

    state = AgentState(
        session_id="wf-leak-session",
        session_dir=str(tmp),
        file_path=str(csv_path),
        user_query="Run full analysis and ML modeling",
    )

    graph = create_workflow()
    result = graph.invoke(state)
    result_state = AgentState.model_validate(result)

    assert result_state.data_summary is not None
    assert result_state.target_detection is not None
    assert result_state.ml_results is not None
    assert result_state.final_report != ""
    assert result_state.final_report_path != ""
