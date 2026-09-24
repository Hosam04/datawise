"""E2E Test: Dataset A — Clean Numeric Dataset."""

import pathlib
import tempfile
import pytest
import pandas as pd
import numpy as np
from backend.agents.master.orchestrator import create_workflow
from backend.core.state import AgentState


def test_clean_numeric_pipeline_e2e():
    """End-to-End run on clean numeric dataset."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="e2e-num-"))
    n = 150
    df = pd.DataFrame({
        "feature_1": np.linspace(1, 100, n),
        "feature_2": np.linspace(10, 500, n),
        "target": np.linspace(5, 50, n) + np.random.normal(0, 1, n),
    })
    csv_path = tmp / "numeric_dataset.csv"
    df.to_csv(csv_path, index=False)

    state = AgentState(
        session_id="e2e-numeric-sess",
        session_dir=str(tmp),
        file_path=str(csv_path),
        user_query="Analyze numeric dataset",
    )

    graph = create_workflow()
    result = graph.invoke(state)
    result_state = AgentState.model_validate(result)

    assert result_state.data_summary.get("total_rows") == n
    assert result_state.final_report != ""
