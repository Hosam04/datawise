"""E2E Test: Dataset G — Dataset Containing Target Leakage."""

import pathlib
import tempfile
import pytest
import pandas as pd
import numpy as np
from backend.agents.master.orchestrator import create_workflow
from backend.core.state import AgentState


def test_leakage_dataset_pipeline_e2e():
    """End-to-End run on dataset containing direct and derived target leakage."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="e2e-leak-"))
    n = 150
    df = pd.DataFrame({
        "feature_1": np.random.normal(10, 2, n),
        "target": np.random.choice([0, 1], n),
        "target_copy": np.random.choice([0, 1], n),  # Copy
        "target_scaled": np.random.normal(0, 1, n),
    })
    df["target_copy"] = df["target"].copy()

    csv_path = tmp / "leakage_dataset.csv"
    df.to_csv(csv_path, index=False)

    state = AgentState(
        session_id="e2e-leak-sess",
        session_dir=str(tmp),
        file_path=str(csv_path),
        user_query="Run analysis on dataset with leakage",
    )

    graph = create_workflow()
    result = graph.invoke(state)
    result_state = AgentState.model_validate(result)

    assert result_state.final_report != ""
    assert result_state.ml_results is not None
