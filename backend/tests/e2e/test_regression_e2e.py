"""E2E Test: Dataset F — Regression Dataset."""

import pathlib
import tempfile
import pytest
import pandas as pd
import numpy as np
from backend.agents.master.orchestrator import create_workflow
from backend.core.state import AgentState


def test_regression_pipeline_e2e():
    """End-to-End run on continuous numeric prediction."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="e2e-reg-"))
    n = 150
    df = pd.DataFrame({
        "square_feet": np.random.randint(500, 4000, n),
        "bedrooms": np.random.randint(1, 6, n),
        "bathrooms": np.random.randint(1, 4, n),
        "charges": np.random.uniform(50000, 500000, n).round(2),
    })
    csv_path = tmp / "regression_dataset.csv"
    df.to_csv(csv_path, index=False)

    state = AgentState(
        session_id="e2e-reg-sess",
        session_dir=str(tmp),
        file_path=str(csv_path),
        user_query="Predict house price and charges",
    )

    graph = create_workflow()
    result = graph.invoke(state)
    result_state = AgentState.model_validate(result)

    assert result_state.target_detection is not None
    assert result_state.target_detection.get("target_column") == "charges"
    assert result_state.final_report != ""
