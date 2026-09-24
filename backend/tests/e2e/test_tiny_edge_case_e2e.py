"""E2E Test: Dataset H & I — Tiny (5 rows) and Extreme Edge Cases."""

import pathlib
import tempfile
import pytest
import pandas as pd
import numpy as np
from backend.agents.master.orchestrator import create_workflow
from backend.core.state import AgentState


def test_tiny_dataset_pipeline_e2e():
    """End-to-End run on very small (5 rows) dataset."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="e2e-tiny-"))
    df = pd.DataFrame({
        "a": [1, 2, 3, 4, 5],
        "b": [10, 20, 30, 40, 50],
        "target": [0, 1, 0, 1, 0],
    })
    csv_path = tmp / "tiny.csv"
    df.to_csv(csv_path, index=False)

    state = AgentState(
        session_id="e2e-tiny-sess",
        session_dir=str(tmp),
        file_path=str(csv_path),
        user_query="Analyze tiny 5-row dataset",
    )

    graph = create_workflow()
    result = graph.invoke(state)
    result_state = AgentState.model_validate(result)

    assert result_state.data_summary.get("total_rows") == 5
    # ML should be skipped because dataset < 100 rows
    if result_state.ml_results:
        assert result_state.ml_results.status in ("skipped", "failed")
    assert result_state.final_report != ""


def test_constant_columns_edge_case_e2e():
    """End-to-End run on dataset where features and target are constant."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="e2e-const-"))
    df = pd.DataFrame({
        "const_feat": [42.0] * 120,
        "target": [1] * 120,
    })
    csv_path = tmp / "constant.csv"
    df.to_csv(csv_path, index=False)

    state = AgentState(
        session_id="e2e-const-sess",
        session_dir=str(tmp),
        file_path=str(csv_path),
        user_query="Analyze constant dataset",
    )

    graph = create_workflow()
    result = graph.invoke(state)
    result_state = AgentState.model_validate(result)

    assert result_state.final_report != ""
