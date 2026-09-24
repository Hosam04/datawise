"""Tests for Metric Leakage (suspicious perfect 1.0 accuracy without warnings)."""

import pytest
import pandas as pd
import numpy as np
from backend.ml.analyzer import MLAnalyzer


def test_perfect_accuracy_warning_on_leaked_target_proxy(analyzer):
    """When a model achieves an unrealistic 100% accuracy or 1.0 R2 score due to a proxy feature,
    the system must emit a warning in MLResults or logs rather than blindly trusting the metric.
    """
    n = 300
    rng = np.random.default_rng(42)
    # Perfect predictive relationship
    x = rng.integers(0, 2, n)
    target = x.copy()

    df = pd.DataFrame({
        "unfiltered_proxy": x,
        "f_noise": rng.normal(0, 1, n).round(2),
        "target": target,
    })

    results = analyzer.run(
        df=df,
        target="target",
        selected_model="logistic_regression",
        fallback_model=None,
        problem_type="classification",
        profile={"numeric_columns": ["unfiltered_proxy", "f_noise"]},
    )

    assert results.status == "success"
    if results.metrics and results.metrics.accuracy == 1.0:
        # A 1.0 accuracy must trigger warnings or suspicion flags
        has_warning = any("leakage" in str(w).lower() or "perfect" in str(w).lower() for w in (results.warnings or []))
        assert has_warning, (
            "METRIC LEAKAGE: Model achieved 100% accuracy without any warning or caveat in MLResults.warnings!"
        )
