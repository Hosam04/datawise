"""Tests for Target-Derived Feature Leakage (target_squared, target_rank, target_scaled, etc.)."""

import pytest
import pandas as pd
from backend.ml.analyzer import MLAnalyzer
from backend.tests.leakage.datasets import make_derived_target_leakage_dataset
from backend.tests.leakage.helpers import extract_features_used_in_training, has_leaked_feature_in_importance


def test_target_derived_keyword_columns_detected_and_dropped(analyzer):
    """Features named target_squared, target_scaled should be dropped if name-based leakage
    or keyword-based leakage detection is active.
    """
    df = make_derived_target_leakage_dataset(n=300, seed=42)
    leaked_cols = ["target_squared", "target_scaled", "target_rank", "target_category"]
    
    results = analyzer.run(
        df=df,
        target="target",
        selected_model="linear_regression",
        fallback_model=None,
        problem_type="regression",
        profile={"numeric_columns": ["feature_1", "feature_2", "target_squared", "target_scaled", "target_rank"]},
    )

    assert results.status == "success"
    used_features = extract_features_used_in_training(results)

    for col in leaked_cols:
        assert col not in used_features, (
            f"DATA LEAKAGE FAILURE: target-derived feature '{col}' reached training! Used features: {used_features}"
        )


def test_unnamed_target_transformations_leakage(analyzer):
    """Transformations of the target column that do NOT contain the word 'target' in their name
    (e.g., 'f_squared_outcome', 'rank_outcome').
    Tests whether the system detects derived leakage via mathematical dependence or correlation.
    """
    df = make_derived_target_leakage_dataset(n=300, seed=42)
    # Rename so name-based filter cannot trivially drop by keyword "target"
    df["math_outcome_sq"] = df["target_squared"]
    df = df.drop(columns=["target_squared", "target_scaled", "target_rank", "target_category"])

    results = analyzer.run(
        df=df,
        target="target",
        selected_model="linear_regression",
        fallback_model=None,
        problem_type="regression",
        profile={"numeric_columns": ["feature_1", "feature_2", "math_outcome_sq"]},
    )

    assert results.status == "success"
    used_features = extract_features_used_in_training(results)
    
    assert "math_outcome_sq" not in used_features, (
        f"DATA LEAKAGE: target-derived feature 'math_outcome_sq' entered training! Used: {used_features}"
    )
