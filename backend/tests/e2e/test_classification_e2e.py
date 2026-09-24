"""E2E Test: Dataset E — Classification Dataset."""

import pathlib
import tempfile
import pytest
import pandas as pd
import numpy as np
from backend.agents.master.orchestrator import create_workflow
from backend.core.state import AgentState


def test_classification_pipeline_e2e():
    """End-to-End run on binary and multiclass classification."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="e2e-cls-"))
    n = 150
    df = pd.DataFrame({
        "age": np.random.randint(18, 70, n),
        "credit_score": np.random.randint(300, 850, n),
        "debt_ratio": np.random.uniform(0.1, 0.9, n).round(2),
        "default": np.random.choice([0, 1], n),
    })
    csv_path = tmp / "classification_dataset.csv"
    df.to_csv(csv_path, index=False)

    state = AgentState(
        session_id="e2e-cls-sess",
        session_dir=str(tmp),
        file_path=str(csv_path),
        user_query="Predict loan default",
    )

    graph = create_workflow()
    result = graph.invoke(state)
    result_state = AgentState.model_validate(result)

    assert result_state.target_detection is not None
    assert result_state.ml_results is not None
    assert result_state.final_report != ""
