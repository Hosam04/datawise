"""Tests for Post-Target Leakage (resolution outcomes, final amounts)."""

import pytest
import pandas as pd
from backend.ml.analyzer import MLAnalyzer
from backend.tests.leakage.datasets import make_post_target_leakage_dataset
from backend.tests.leakage.helpers import extract_features_used_in_training


def test_post_target_events_leakage(analyzer):
    """Post-target outcome fields (post_target_status, resolution_date, final_amount)
    must not leak into predicting target.
    """
    df = make_post_target_leakage_dataset(n=300, seed=42)

    results = analyzer.run(
        df=df,
        target="target",
        selected_model="logistic_regression",
        fallback_model=None,
        problem_type="classification",
        profile={
            "numeric_columns": ["amount", "final_amount"],
            "categorical_columns": ["post_target_status", "resolution_date"],
        },
    )

    assert results.status == "success"
    used = extract_features_used_in_training(results)

    post_target_fields = ["post_target_status", "resolution_date", "final_amount"]
    leaked_found = [f for f in post_target_fields if any(u.startswith(f) for u in used)]

    assert not leaked_found, (
        f"POST-TARGET LEAKAGE: Features {leaked_found} generated after target event reached model! Used: {used}"
    )
