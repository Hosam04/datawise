"""Extended unit tests for InsightsAgent, Ranking, and Validation."""

import pytest
import pandas as pd
import numpy as np
from backend.agents.insights.insights_agent import InsightsAgent
from backend.agents.insights.insight_ranker import rank_insights
from backend.agents.insights.statistical_validator import validate_insights
from backend.core.state import AgentState


def test_insights_agent_with_empty_dataframe():
    """InsightsAgent handles empty dataframe without crashing."""
    state = AgentState(
        session_id="ins-empty",
        session_dir="storage/sessions/ins-empty",
        file_path="storage/sessions/ins-empty/data.csv",
        user_query="Generate insights",
        df=pd.DataFrame(),
    )
    agent = InsightsAgent()
    out_state = agent.run(state)
    assert out_state.insights is not None
    assert "executive_summary" in out_state.insights


def test_insights_agent_normal_dataset(tmp_path):
    """InsightsAgent extracts valid findings and summaries on tabular data."""
    n = 100
    df = pd.DataFrame({
        "age": np.random.randint(20, 60, n),
        "income": np.random.normal(50000, 10000, n),
        "department": np.random.choice(["Tech", "Sales", "Support"], n),
        "target": np.random.choice([0, 1], n),
    })
    csv_p = tmp_path / "df.csv"
    df.to_csv(csv_p, index=False)

    state = AgentState(
        session_id="ins-norm",
        session_dir=str(tmp_path),
        file_path=str(csv_p),
        user_query="Generate insights",
        df=df,
        target_detection={"target_column": "target", "is_numeric": True, "task_type": "classification"},
    )
    agent = InsightsAgent()
    out_state = agent.run(state)
    assert out_state.insights is not None
    assert "executive_summary" in out_state.insights
    assert isinstance(out_state.insights.get("key_findings"), list)
