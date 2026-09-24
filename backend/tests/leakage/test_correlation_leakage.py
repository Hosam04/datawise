"""Tests for Perfect and Near-Perfect Correlation Leakage."""

import pytest
import numpy as np
import pandas as pd
from backend.ml.analyzer import MLAnalyzer
from backend.tests.leakage.datasets import (
    make_perfect_correlation_leakage_dataset,
    make_near_perfect_leakage_dataset,
)
from backend.tests.leakage.helpers import extract_features_used_in_training


def test_perfect_inverse_correlation_leakage(analyzer):
    """A feature with exact r = -1.0 (e.g. leak_inverse = 1 - target) is pure leakage."""
    df = make_perfect_correlation_leakage_dataset(n=300, seed=42)

    results = analyzer.run(
        df=df,
        target="target",
        selected_model="logistic_regression",
        fallback_model=None,
        problem_type="classification",
        profile={"numeric_columns": ["f1", "f2", "leak_direct", "leak_inverse", "leak_scaled"]},
    )

    assert results.status == "success"
    used = extract_features_used_in_training(results)

    assert "leak_inverse" not in used, (
        f"DATA LEAKAGE: Inverted target feature 'leak_inverse' reached training! Features: {used}"
    )


def test_perfect_scaled_correlation_leakage(analyzer):
    """A feature with exact r = 1.0 but scaled (e.g. leak_scaled = 10 * target) is pure leakage."""
    df = make_perfect_correlation_leakage_dataset(n=300, seed=42)

    results = analyzer.run(
        df=df,
        target="target",
        selected_model="logistic_regression",
        fallback_model=None,
        problem_type="classification",
        profile={"numeric_columns": ["f1", "f2", "leak_scaled"]},
    )

    assert results.status == "success"
    used = extract_features_used_in_training(results)

    assert "leak_scaled" not in used, (
        f"DATA LEAKAGE: Scaled target feature 'leak_scaled' reached training! Features: {used}"
    )


def test_near_perfect_correlation_with_noise(analyzer):
    """A proxy feature with r > 0.995 containing small Gaussian noise is near-perfect leakage."""
    df = make_near_perfect_leakage_dataset(n=300, noise_level=0.001, seed=42)
    
    corr = df["proxy_target"].corr(df["target"])
    assert corr > 0.99, f"Expected correlation > 0.99, got {corr}"
    
    results = analyzer.run(
        df=df,
        target="target",
        selected_model="linear_regression",
        fallback_model=None,
        problem_type="regression",
        profile={"numeric_columns": ["f1", "proxy_target"]},
    )
    
    assert results.status in ("success", "failed", "skipped"), (
        f"Expected safe outcome, got {results.status}"
    )
    used = extract_features_used_in_training(results)
    assert "proxy_target" not in used, (
        f"DATA LEAKAGE: Near-perfect proxy feature 'proxy_target' (r={corr:.4f}) reached training! Features: {used}"
    )