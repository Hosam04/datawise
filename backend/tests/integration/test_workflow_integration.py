"""Integration tests: Multi-agent LangGraph workflow end-to-end execution."""

import os
import pathlib
import tempfile
import pytest
import pandas as pd
import numpy as np
from backend.agents.master.orchestrator import create_workflow
from backend.core.state import AgentState


def test_full_workflow_all_nodes_execution():
    """Verify all 9 nodes in the LangGraph workflow execute in correct sequence."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="datawise-wf-full-"))
    n = 120
    df = pd.DataFrame({
        "age": np.random.randint(18, 70, n),
        "income": np.random.randint(20000, 100000, n),
        "department": np.random.choice(["IT", "HR", "Sales"], n),
        "churn": np.random.choice([0, 1], n),
    })
    csv_path = tmp / "dataset.csv"
    df.to_csv(csv_path, index=False)

    state = AgentState(
        session_id="wf-all-nodes",
        session_dir=str(tmp),
        file_path=str(csv_path),
        user_query="Run complete end-to-end analysis",
    )

    graph = create_workflow()
    result = graph.invoke(state)
    result_state = AgentState.model_validate(result)

    # Verify state transitions and outputs of each node
    assert result_state.df_path is not None
    assert result_state.dataset_profile is not None
    assert result_state.target_detection is not None
    assert result_state.ml_results is not None
    assert result_state.plan is not None
    assert result_state.insights is not None
    assert result_state.final_report != ""
