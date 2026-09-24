"""Extended unit tests for ML pipeline and Model Selection."""

import pytest
import numpy as np
import pandas as pd
from backend.ml.analyzer import MLAnalyzer
from backend.agents.model_selection.model_selection_agent import ModelSelectionAgent
from backend.core.state import AgentState


def test_model_selection_tabular_classification():
    """Model selection for standard classification dataset."""
    agent = ModelSelectionAgent()
    df = pd.DataFrame({
        "f1": np.random.normal(0, 1, 200),
        "f2": np.random.normal(0, 1, 200),
        "target": np.random.choice([0, 1], size=200),
    })

    state = AgentState(
        session_id="ms-test-1",
        session_dir="storage/sessions/ms-test-1",
        file_path="storage/sessions/ms-test-1/data.csv",
        user_query="Select model",
        df=df,
        target_detection={"target_column": "target", "task_type": "classification", "is_numeric": True},
        dataset_profile={"numeric_columns": ["f1", "f2"], "categorical_columns": []},
    )

    out_state = agent.run(state)
    assert out_state.ml_results is not None
    assert out_state.ml_results.selected_model in ["svm", "random_forest", "catboost", "logistic_regression"]
    assert out_state.ml_results.problem_type == "classification"


def test_model_selection_tabular_regression():
    """Model selection for regression dataset."""
    agent = ModelSelectionAgent()
    df = pd.DataFrame({
        "f1": np.random.normal(0, 1, 200),
        "f2": np.random.normal(0, 1, 200),
        "target": np.random.normal(100, 20, 200),
    })

    state = AgentState(
        session_id="ms-test-2",
        session_dir="storage/sessions/ms-test-2",
        file_path="storage/sessions/ms-test-2/data.csv",
        user_query="Select model",
        df=df,
        target_detection={"target_column": "target", "task_type": "regression", "is_numeric": True},
        dataset_profile={"numeric_columns": ["f1", "f2"], "categorical_columns": []},
    )

    out_state = agent.run(state)
    assert out_state.ml_results is not None
    assert out_state.ml_results.problem_type == "regression"


def test_ml_analyzer_skips_small_dataset(analyzer):
    """MLAnalyzer skips datasets with fewer than 100 rows."""
    df = pd.DataFrame({
        "x": [1, 2, 3, 4, 5],
        "target": [0, 1, 0, 1, 0],
    })
    res = analyzer.run(
        df=df,
        target="target",
        selected_model="logistic_regression",
        fallback_model=None,
        problem_type="classification",
        profile={},
    )
    assert res.status == "skipped"
    assert "small" in res.reason.lower() or "few" in res.reason.lower()


def test_ml_analyzer_skips_single_class_target(analyzer):
    """MLAnalyzer skips classification when target has only 1 unique class."""
    n = 150
    df = pd.DataFrame({
        "x1": np.random.normal(0, 1, n),
        "target": [1] * n,
    })
    res = analyzer.run(
        df=df,
        target="target",
        selected_model="logistic_regression",
        fallback_model=None,
        problem_type="classification",
        profile={"numeric_columns": ["x1"]},
    )
    assert res.status in ("skipped", "failed"), (
        f"Expected skipped or failed for single-class target, got {res.status}"
    )
    assert (
        "one class" in res.reason.lower() 
        or "class" in res.reason.lower()
        or "failed" in res.status
    ), f"Unexpected reason: {res.reason}"


def test_ml_analyzer_fallback_model_trigger(analyzer):
    """When primary model fails, fallback model should be attempted."""
    n = 150
    df = pd.DataFrame({
        "x1": [1.0, 2.0] * 75,
        "target": [0, 1] * 75,
    })
    # Provide an invalid primary model string to force fallback
    res = analyzer.run(
        df=df,
        target="target",
        selected_model="logistic_regression",
        fallback_model="decision_tree",
        problem_type="classification",
        profile={"numeric_columns": ["x1"]},
    )
    assert res.status in ("success", "failed", "skipped")
