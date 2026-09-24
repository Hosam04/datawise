"""E2E Test: Dataset B — Mixed Numeric & Categorical Dataset."""

import pathlib
import tempfile
import pytest
import pandas as pd
import numpy as np
from backend.agents.master.orchestrator import create_workflow
from backend.core.state import AgentState


def test_mixed_categorical_pipeline_e2e():
    """End-to-End run on mixed dataset."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="e2e-mixed-"))
    n = 150
    df = pd.DataFrame({
        "age": np.random.randint(18, 65, n),
        "department": np.random.choice(["Engineering", "Sales", "HR", "Support"], n),
        "education": np.random.choice(["Bachelor", "Master", "PhD"], n),
        "salary": np.random.normal(60000, 15000, n).round(2),
        "target": np.random.choice([0, 1], n),
    })
    csv_path = tmp / "mixed_dataset.csv"
    df.to_csv(csv_path, index=False)

    state = AgentState(
        session_id="e2e-mixed-sess",
        session_dir=str(tmp),
        file_path=str(csv_path),
        user_query="Analyze mixed dataset",
    )

    graph = create_workflow()
    result = graph.invoke(state)
    result_state = AgentState.model_validate(result)

    assert result_state.data_summary.get("total_rows") == n
    assert result_state.visualization_paths
    assert result_state.final_report != ""
