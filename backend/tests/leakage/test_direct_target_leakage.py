"""Tests for Direct Target Leakage (target_copy == target)."""

import pandas as pd
import pytest
from backend.ml.analyzer import MLAnalyzer
from backend.tests.leakage.datasets import make_direct_target_leakage_dataset
from backend.tests.leakage.helpers import extract_features_used_in_training, has_leaked_feature_in_importance


def test_direct_target_copy_is_dropped_and_never_reaches_training(analyzer):
    """Verify that an exact copy of the target column is detected, dropped,
    and NEVER reaches the model training feature set.
    """
    df = make_direct_target_leakage_dataset(n=300, seed=42)
    assert "target_copy" in df.columns
    assert (df["target_copy"] == df["target"]).all()

    results = analyzer.run(
        df=df,
        target="target",
        selected_model="logistic_regression",
        fallback_model=None,
        problem_type="classification",
        profile={"numeric_columns": ["age", "income", "target_copy"]},
    )

    assert results.status == "success", f"Training failed unexpectedly: {results.reason}"
    used_features = extract_features_used_in_training(results)
    
    # 1. Verification of Exclusion
    assert "target_copy" not in used_features, (
        f"DATA LEAKAGE FAILURE: 'target_copy' was used as a training feature! Features: {used_features}"
    )
    assert not has_leaked_feature_in_importance(results, ["target_copy"])


def test_direct_target_copy_with_arbitrary_column_name(analyzer):
    """When a column equals the target but does NOT contain 'target' in its name
    (e.g., 'customer_outcome' == target), verify if the system detects equality leakage.
    """
    df = make_direct_target_leakage_dataset(n=300, seed=42)
    df["arbitrary_column_leak"] = df["target"].copy()

    results = analyzer.run(
        df=df,
        target="target",
        selected_model="logistic_regression",
        fallback_model=None,
        problem_type="classification",
        profile={"numeric_columns": ["age", "income", "arbitrary_column_leak"]},
    )

    assert results.status == "success"
    used_features = extract_features_used_in_training(results)
    assert "arbitrary_column_leak" not in used_features, (
        f"DATA LEAKAGE FAILURE: exact target copy 'arbitrary_column_leak' reached training! Features: {used_features}"
    )


def test_direct_target_string_copy(analyzer):
    """Direct target copy with categorical/string labels."""
    df = pd.DataFrame({
        "feature_1": [1.0, 2.0, 3.0, 4.0] * 75,
        "feature_2": [10.0, 20.0, 30.0, 40.0] * 75,
        "label_dup": ["cat", "dog", "bird", "fish"] * 75,
        "target": ["cat", "dog", "bird", "fish"] * 75,
    })

    results = analyzer.run(
        df=df,
        target="target",
        selected_model="logistic_regression",
        fallback_model=None,
        problem_type="classification",
        profile={"categorical_columns": ["label_dup"], "numeric_columns": ["feature_1", "feature_2"]},
    )

    assert results.status == "success"
    used_features = extract_features_used_in_training(results)
    assert "label_dup" not in used_features, (
        f"DATA LEAKAGE FAILURE: categorical duplicate 'label_dup' reached training: {used_features}"
    )
