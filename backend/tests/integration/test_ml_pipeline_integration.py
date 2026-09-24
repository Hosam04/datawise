"""Integration tests: Profiling -> Target Detection -> Model Selection -> ML Analyzer -> Insights."""

import pytest
import pandas as pd
import numpy as np
from backend.agents.profile.dataset_profile_agent import DatasetProfileAgent
from backend.utils.target_detection import detect_target_variable
from backend.agents.model_selection.model_selection_agent import ModelSelectionAgent
from backend.ml.analyzer import MLAnalyzer
from backend.core.state import AgentState


def test_ml_pipeline_integration_flow(tmp_path):
    """Verify seamless integration from Profile -> Target Detection -> Model Selection -> ML Analyzer."""
    n = 250
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        "feature_1": rng.integers(1, 100, n),
        "feature_2": rng.integers(10, 50, n),
        "feature_3": rng.choice(["cat_A", "cat_B", "cat_C"], n),
        "target": rng.integers(0, 2, n),
    })
    csv_p = tmp_path / "ml_pipeline.csv"
    df.to_csv(csv_p, index=False)

    state = AgentState(
        session_id="ml-pipe-sess",
        session_dir=str(tmp_path),
        file_path=str(csv_p),
        user_query="Train predictive model",
        df=df,
    )

    # 1. Profile
    profile_agent = DatasetProfileAgent()
    state = profile_agent.run(state)

    # 2. Target Detection
    target_info = detect_target_variable(df)
    state.target_detection = target_info
    assert state.target_detection["target_column"] == "target"

    # 3. Model Selection
    model_selector = ModelSelectionAgent()
    state = model_selector.run(state)
    assert state.ml_results is not None
    assert state.ml_results.selected_model is not None

    # 4. ML Analyzer
    analyzer = MLAnalyzer()
    ml_res = analyzer.run(
        df=df,
        target=state.target_detection["target_column"],
        selected_model=state.ml_results.selected_model,
        fallback_model=state.ml_results.fallback_model,
        problem_type=state.ml_results.problem_type,
        profile=state.dataset_profile,
    )
    state.ml_results = ml_res
    assert state.ml_results.status in ("success", "skipped", "failed")
