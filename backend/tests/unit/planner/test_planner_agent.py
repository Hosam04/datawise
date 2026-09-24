"""Unit tests for PlannerAgent."""

import pytest
import pandas as pd
from backend.agents.planner.planner_agent import PlannerAgent
from backend.core.state import AgentState


def test_planner_agent_creates_plan(tmp_path):
    """PlannerAgent creates analysis plan with charts and steps."""
    df = pd.DataFrame({
        "x": [1, 2, 3, 4, 5],
        "y": [10, 20, 30, 40, 50],
        "target": [0, 1, 0, 1, 0],
    })
    csv_p = tmp_path / "plan_data.csv"
    df.to_csv(csv_p, index=False)

    state = AgentState(
        session_id="plan-test",
        session_dir=str(tmp_path),
        file_path=str(csv_p),
        user_query="Analyze customer behavior",
        df=df,
        target_detection={"target_column": "target", "task_type": "classification"},
        data_summary={"columns": ["x", "y", "target"], "total_rows": 5, "total_cols": 3},
    )

    planner = PlannerAgent()
    out_state = planner.run(state)
    assert out_state.plan is not None
