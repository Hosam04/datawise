"""Unit tests for VisualizationAgent and Chart Tools."""

import os
import pytest
import pandas as pd
import numpy as np
from backend.agents.visualization.viz_agent import VisualizationAgent
from backend.core.state import AgentState
from backend.models.plan import Plan
from backend.models.chart import ChartConfig


def test_viz_agent_renders_charts(tmp_path):
    """VisualizationAgent generates valid chart files (.png)."""
    df = pd.DataFrame({
        "category": ["A", "B", "C", "D", "E"] * 10,
        "value": np.random.normal(50, 10, 50),
    })
    csv_p = tmp_path / "viz_data.csv"
    df.to_csv(csv_p, index=False)

    plan = Plan(
        steps=[],
        requires_cleaning=False,
        requires_report=True,
        charts=[
            ChartConfig(
                chart_type="bar",
                x_axis="category",
                y_axis="value",
                title="Category vs Value",
                x_label="Category",
                y_label="Value",
            ),
            ChartConfig(
                chart_type="box",
                x_axis="category",
                y_axis="value",
                title="Value Distribution by Category",
                x_label="Category",
                y_label="Value",
            ),
        ],
    )

    state = AgentState(
        session_id="viz-test",
        session_dir=str(tmp_path),
        file_path=str(csv_p),
        user_query="Plot charts",
        df=df,
        plan=plan,
    )

    agent = VisualizationAgent()
    out_state = agent.run(state)

    assert out_state.visualization_paths
    for path in out_state.visualization_paths:
        assert os.path.exists(path), f"Chart file was not created at {path}"
