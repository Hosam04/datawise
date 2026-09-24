"""E2E Test: Dataset C — Dirty Dataset (Missing values, duplicates, outliers)."""

import pathlib
import tempfile
import pytest
import pandas as pd
import numpy as np
from backend.agents.master.orchestrator import create_workflow
from backend.core.state import AgentState


def test_dirty_dataset_pipeline_e2e():
    """End-to-End run on dirty dataset requiring cleaning engine repairs."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="e2e-dirty-"))
    n = 150
    df = pd.DataFrame({
        "id": list(range(n - 10)) + list(range(10)),
        "age": [np.nan if i % 10 == 0 else (120 if i == 5 else 20 + i % 40) for i in range(n)],
        "income": [np.nan if i % 15 == 0 else 30000 + i * 200 for i in range(n)],
        "category": [np.nan if i % 20 == 0 else f"cat_{i % 3}" for i in range(n)],
        "target": [i % 2 for i in range(n)],
    })
    csv_path = tmp / "dirty_dataset.csv"
    df.to_csv(csv_path, index=False)

    state = AgentState(
        session_id="e2e-dirty-sess",
        session_dir=str(tmp),
        file_path=str(csv_path),
        user_query="Clean and analyze dirty dataset",
    )

    graph = create_workflow()
    result = graph.invoke(state)
    result_state = AgentState.model_validate(result)

    assert result_state.final_report != ""
    assert result_state.df_path is not None
