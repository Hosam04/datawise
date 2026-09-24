"""Tests for False Positives in Leakage Detection.

Legitimate predictive features (age, income, experience, education) that genuinely
correlate with the target must NOT be incorrectly discarded as leakage.
"""

import pytest
import pandas as pd
import numpy as np
from backend.ml.analyzer import MLAnalyzer
from backend.tests.leakage.datasets import make_legitimate_predictive_dataset
from backend.tests.leakage.helpers import extract_features_used_in_training


def test_legitimate_predictive_features_are_retained(analyzer):
    """Features like age, experience, education that correlate with income target
    must NOT be dropped as data leakage.
    """
    df = make_legitimate_predictive_dataset(n=300, seed=42)
    expected_features = {"age", "experience", "education_years", "income"}
    results = analyzer.run(
        df=df,
        target="target",
        selected_model="logistic_regression",
        fallback_model=None,
        problem_type="classification",
        profile={"numeric_columns": ["age", "experience", "education_years", "income"]},
    )
    assert results.status == "success", f"ML failed: {results.reason}"
    used_features = set(extract_features_used_in_training(results))
    
    # Features that are legitimately predictive (except the target itself)
    for feat in ["age", "experience", "education_years"]:
        assert feat in used_features or f"num__{feat}" in used_features, (
            f"FALSE POSITIVE: Legitimate predictive feature '{feat}' was incorrectly dropped from training!"
        )