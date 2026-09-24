"""Tests for Future / Temporal Data Leakage (events occurring after prediction time)."""

import pytest
import pandas as pd
from backend.ml.analyzer import MLAnalyzer
from backend.tests.leakage.datasets import make_temporal_future_leakage_dataset
from backend.tests.leakage.helpers import extract_features_used_in_training


def test_future_temporal_leakage_detection_or_capability_gap(analyzer):
    """Test whether post-admission temporal fields (discharge_date, final_diagnosis, treatment_cost)
    leak into training.
    """
    df = make_temporal_future_leakage_dataset(n=300, seed=42)

    results = analyzer.run(
        df=df,
        target="target",
        selected_model="logistic_regression",
        fallback_model=None,
        problem_type="classification",
        profile={
            "numeric_columns": ["age", "admission_systolic", "treatment_cost"],
            "categorical_columns": ["final_diagnosis", "discharge_date"],
        },
    )

    assert results.status == "success"
    used = extract_features_used_in_training(results)

    # Future fields that occur after the admission prediction time
    future_fields = ["discharge_date", "final_diagnosis", "treatment_cost"]
    leaked_found = [f for f in future_fields if any(u.startswith(f) for u in used)]

    assert not leaked_found, (
        f"TEMPORAL LEAKAGE: Future post-admission fields {leaked_found} reached model training! Features used: {used}"
    )
