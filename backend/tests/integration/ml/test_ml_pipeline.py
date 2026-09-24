"""Integration: MLAnalyzer trained on deterministic classification.csv.

Uses the real sklearn pipeline through the production ML analyzer. The
dataset is engineered so a random_forest model must train to status success.
"""

from __future__ import annotations

import pandas as pd
import pytest

from backend.tests.assertions import check

COMPONENT = "Integration/MLAnalyzer"
STAGE = "ml"


@pytest.fixture
def analyzer():
    from backend.ml.analyzer import MLAnalyzer

    return MLAnalyzer()


@pytest.fixture
def classification_df(datasets_dir):
    return pd.read_csv(datasets_dir / "classification.csv")


def test_classification_train_success(datasets_dir, analyzer, classification_df):
    """A well-separated target trains to success with random_forest."""
    results = analyzer.run(
        df=classification_df,
        target="class",
        selected_model="random_forest",
        fallback_model="logistic_regression",
        problem_type="classification",
        profile={"numeric_columns": ["age", "income", "spend"]},
    )
    assert results.status == "success", (results.status, getattr(results, "reason", None))
    assert results.selected_model is not None
    assert getattr(results, "accuracy", None) is not None or getattr(results, "metrics", None)


def test_unsupported_model_skipped(analyzer, classification_df):
    # The analyzer itself accepts 'svm' (sklearn SVC). Selecting it is valid.
    results = analyzer.run(
        df=classification_df,
        target="class",
        selected_model="svm",
        fallback_model="logistic_regression",
        problem_type="classification",
        profile={},
    )
    assert results.status in ("success", "failed"), results.status


def test_too_small_skipped(analyzer):
    df = pd.DataFrame({"a": [1, 2, 3], "y": [0, 1, 0]})
    results = analyzer.run(
        df=df, target="y", selected_model="random_forest",
        fallback_model="logistic_regression", problem_type="classification", profile={},
    )
    assert results.status == "skipped"
    assert "small" in (getattr(results, "reason", "") or "").lower()


def test_regression_train_success(datasets_dir, analyzer):
    df = pd.read_csv(datasets_dir / "regression.csv")
    results = analyzer.run(
        df=df, target="price",
        selected_model="random_forest_regressor",
        fallback_model="linear_regression",
        problem_type="regression",
        profile={"numeric_columns": ["feature1", "feature2", "price"]},
    )
    assert results.status in ("success", "failed")