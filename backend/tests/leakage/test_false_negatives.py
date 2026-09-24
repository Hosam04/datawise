"""Tests for False Negatives in Leakage Detection.

Leakage scenarios where leaked information is non-linear or slightly noisy
and does not trigger exact equality or simple keyword checks.
"""

import pytest
import pandas as pd
import numpy as np
from backend.ml.analyzer import MLAnalyzer
from backend.tests.leakage.helpers import extract_features_used_in_training


def test_non_linear_target_leakage_detection(analyzer):
    """Leakage through non-linear function (e.g. col = sin(target) or col = target^3)
    with a generic feature name like 'x_transformed'.
    """
    n = 300
    rng = np.random.default_rng(42)
    target = rng.normal(0, 1, n).round(3)
    leaked_cube = np.round(target ** 3, 3)
    f_noise = rng.normal(0, 1, n).round(3)

    df = pd.DataFrame({
        "f_noise": f_noise,
        "x_transformed": leaked_cube,
        "target": target,
    })

    results = analyzer.run(
        df=df,
        target="target",
        selected_model="linear_regression",
        fallback_model=None,
        problem_type="regression",
        profile={"numeric_columns": ["f_noise", "x_transformed"]},
    )

    assert results.status == "success"
    used = extract_features_used_in_training(results)

    # If the system does not detect non-linear cubic target leakage, it will use x_transformed
    assert "x_transformed" not in used, (
        f"FALSE NEGATIVE / CAPABILITY GAP: Non-linear target leakage 'x_transformed' (target^3) "
        f"was not detected and reached training features: {used}"
    )
