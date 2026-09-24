"""Tests for Duplicate and Semantic Duplicate Leakage."""

import pytest
import pandas as pd
from backend.ml.analyzer import MLAnalyzer
from backend.tests.leakage.datasets import make_semantic_duplicate_leakage_dataset
from backend.tests.leakage.helpers import extract_features_used_in_training


def test_semantic_duplicate_status_labels_leakage(analyzer):
    """When a column contains text labels (e.g. status_label) that map 1:1 to target (status_code),
    verify if the system identifies semantic duplication.
    """
    df = make_semantic_duplicate_leakage_dataset(n=300, seed=42)

    results = analyzer.run(
        df=df,
        target="target",
        selected_model="logistic_regression",
        fallback_model=None,
        problem_type="classification",
        profile={"numeric_columns": ["f1", "status_code"], "categorical_columns": ["status_label"]},
    )

    assert results.status == "success"
    used = extract_features_used_in_training(results)

    # status_label and status_code are 100% duplicate information of target
    assert not any(u.startswith("status_label") for u in used), (
        f"SEMANTIC DUPLICATE LEAKAGE: 'status_label' reached training! Used: {used}"
    )
    assert "status_code" not in used, (
        f"DUPLICATE LEAKAGE: 'status_code' reached training! Used: {used}"
    )
