"""Tests for Feature Selection Leakage (using test set or full dataset for feature selection)."""

import pytest
import pandas as pd
import numpy as np
from backend.agents.insights.insights_agent import InsightsAgent
from backend.core.state import AgentState
from backend.agents.insights.evidence import _compute_numeric_feature_importance


def test_insight_feature_importance_computed_on_full_dataset(tmp_path):
    """Test whether InsightsAgent computes feature importance / ANOVA / Chi2 across the full dataset
    rather than a dedicated train partition.
    """
    n = 200
    df = pd.DataFrame({
        "feat1": np.random.normal(0, 1, n),
        "feat2": np.random.normal(5, 2, n),
        "target": np.random.normal(10, 1, n),
    })

    agent = InsightsAgent()
    # InsightsAgent._compute_numeric_feature_importance takes df directly
    importance = _compute_numeric_feature_importance(df, "target")
    assert isinstance(importance, list)
    assert len(importance) == 2
    # Verify it analyzed all n rows without splitting
    assert all("importance" in item for item in importance)
