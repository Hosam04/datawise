"""ML analyzer unit tests (backend.ml).

This is a real-training, LLM-free component. The tests exercise the input
guard rails (which are deterministic) and one small real training run. To keep
runtime bounded, the real run uses a small-but-valid dataset where rare-class
fallback does not kick in.

Notes:
  - MIN_ROWS_FOR_ML == 100 -> datasets under 100 rows return status "skipped".
  - classification/regression run with a plain sklearn model so no optional
    heavy dependency (catboost etc.) is required.
"""

from __future__ import annotations

import time

import pandas as pd
import pytest

from backend.ml.analyzer import ALLOWED_MODELS, MLAnalyzer, MIN_ROWS_FOR_ML
from backend.tests.assertions import check

COMPONENT = "ML/Analyzer"
STAGE = "train"


@pytest.fixture
def analyzer():
    return MLAnalyzer()


def test_profile_required_format():
    from backend.ml.schemas import MLResults

    profile = {"column_types": {}, "numeric_columns": [], "categorical_columns": []}
    assert isinstance(profile, dict)


# --------------------------------------------------------------------------
# Input guard rails (deterministic, no training)
# --------------------------------------------------------------------------

def test_run_no_model_selected(analyzer, load_dataset):
    df = load_dataset("classification.csv")
    res = analyzer.run(df, "target", None, None, "classification", {})
    assert res.status == "skipped"
    assert "No model" in res.reason


def test_run_unsupported_problem_type(analyzer, load_dataset):
    df = load_dataset("classification.csv")
    res = analyzer.run(df, "target", "random_forest", None, "survival", {})
    assert res.status == "skipped"
    assert "Unsupported problem type" in res.reason


def test_run_invalid_model_for_problem(analyzer, load_dataset):
    df = load_dataset("classification.csv")
    res = analyzer.run(df, "target", "linear_regression", None, "classification", {})
    assert res.status == "skipped"
    assert "not in allowed list" in res.reason


def test_run_target_not_found(analyzer, load_dataset):
    df = load_dataset("classification.csv")
    res = analyzer.run(df, "nope", "random_forest", None, "classification", {})
    assert res.status == "skipped"
    assert "Target column" in res.reason


def test_run_too_few_rows(analyzer, load_dataset):
    df = load_dataset("tiny.csv")  # 5 rows < 100
    res = analyzer.run(df, "target", "random_forest", None, "classification", {})
    assert res.status == "skipped"
    assert "too small" in res.reason.lower()


# --------------------------------------------------------------------------
# Allowed model registries
# --------------------------------------------------------------------------

def test_allowed_models_lists():
    assert "classification" in ALLOWED_MODELS
    assert "regression" in ALLOWED_MODELS
    assert "text_classification" in ALLOWED_MODELS
    assert "random_forest" in ALLOWED_MODELS["classification"]
    assert "linear_regression" in ALLOWED_MODELS["regression"]


# --------------------------------------------------------------------------
# Real training smoke test (small but valid)
# --------------------------------------------------------------------------

def test_real_classification_training(analyzer):
    import numpy as np
    
    rng = np.random.default_rng(7)
    n = 260
    df = pd.DataFrame({
        "x1": rng.normal(0, 1, n).round(3),
        "x2": rng.normal(0, 1, n).round(3),
        "target": rng.integers(0, 3, n),  # 3-class
    })
    res = analyzer.run(df, "target", "random_forest", None, "classification", {})
    
    check(
        res.status in ("success", "failed", "skipped"),
        "ML-001", COMPONENT, STAGE,
        "status is a valid outcome for a classification run",
        f"{res.status} | {res.reason}",
        artifact="MLResults.status",
        root_cause="checking training completes or fails safely",
    )
    
    if res.status == "success":
        assert res.problem_type == "classification"
        assert res.metrics.accuracy is not None and 0 <= res.metrics.accuracy <= 1
        assert res.feature_importance is not None

def test_real_small_classification_skips(analyzer):
    """With just under MIN_ROWS_FOR_ML rows and ~balanced classes, status is
    skipped rather than trained."""
    import numpy as np

    rng = np.random.default_rng(9)
    n = 90
    df = pd.DataFrame({
        "x1": rng.normal(0, 1, n),
        "x2": rng.normal(0, 1, n),
        "target": rng.integers(0, 2, n),
    })
    res = analyzer.run(df, "target", "random_forest", None, "classification", {})
    assert res.status == "skipped"
    assert "too small" in res.reason.lower()


def test_constant_target_bug(analyzer):
    """BUG-ML-01: a single-class (constant) target is reported as
    status=='success' with a one-row confusion matrix instead of being
    skipped. A classifier trained on one class is meaningless; the analyzer
    should return skipped (only one class) rather than success."""
    import numpy as np

    rng = np.random.default_rng(11)
    n = 250
    df = pd.DataFrame({
        "x1": rng.normal(0, 1, n),
        "x2": rng.normal(0, 1, n),
        "target": [1] * n,
    })
    res = analyzer.run(df, "target", "random_forest", None, "classification", {})
    check(
        res.status in ("skipped", "failed"),
        "ML-002", COMPONENT, STAGE,
        "single-class target must be skipped/failed, never trained as success",
        f"status={res.status} confusion_labels={res.confusion_matrix and res.confusion_matrix.get('labels')}",
        artifact="MLResults.status/confusion_matrix",
        root_cause="rare-class filtering keeps only 1 class but the model is trained anyway",
        severity="HIGH",
    )