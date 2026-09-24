"""Extended unit tests for Statistics Engine."""

import pytest
import pandas as pd
import numpy as np
from backend.statistics.engine import StatisticalEngine
from backend.statistics.univariate import numeric_summary, categorical_summary
from backend.statistics.bivariate import series_correlation, anova_test, chi2_association
from backend.statistics.outliers import column_outlier_evidence, five_number_summary


def test_numeric_summary_mathematical_correctness():
    """Verify mean, median, min, max, std on deterministic series."""
    s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
    summary = numeric_summary(s)
    assert summary.mean == 30.0
    assert summary.median == 30.0
    assert summary.min == 10.0
    assert summary.max == 50.0
    assert np.isclose(summary.std, s.std())


def test_categorical_summary_frequencies():
    """Verify categorical summary frequencies and mode."""
    s = pd.Series(["apple", "banana", "apple", "cherry", "apple", "banana"])
    summary = categorical_summary(s)
    assert summary.top_values[0].value == "apple"
    assert summary.unique_count == 3
    assert summary.top_values[0].count == 3

def test_correlation_methods():
    """Test Spearman, Pearson, Kendall correlation."""
    x = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    y = pd.Series([2.0, 4.0, 6.0, 8.0, 10.0])

    r_pearson = series_correlation(x, y, method="pearson")
    r_spearman = series_correlation(x, y, method="spearman")
    r_kendall = series_correlation(x, y, method="kendall")

    assert np.isclose(r_pearson, 1.0)
    assert np.isclose(r_spearman, 1.0)
    assert np.isclose(r_kendall, 1.0)


def test_anova_test_computation():
    df = pd.DataFrame({
        "group": ["A"] * 20 + ["B"] * 20 + ["C"] * 20,
        "score": np.concatenate([
            np.random.normal(10, 1, 20),
            np.random.normal(20, 1, 20),
            np.random.normal(30, 1, 20),
        ]),
    })
    res = anova_test(df["group"], df["score"])
    assert res is not None
    assert res["p_value"] < 0.001       
    assert res["f_statistic"] > 10.0


def test_chi2_association_computation():
    df = pd.DataFrame({
        "cat1": ["X", "X", "Y", "Y"] * 25,
        "cat2": ["A", "A", "B", "B"] * 25,
    })
    res = chi2_association(df["cat1"], df["cat2"])
    assert res is not None
    assert res["p_value"] < 0.05


def test_outlier_detection_evidence():
    s = pd.Series([10.0, 11.0, 12.0, 10.0, 11.0, 12.0, 10.0, 11.0, 12.0, 500.0])
    ev_iqr = column_outlier_evidence(s, "vals", method="IQR", threshold=1.5)
    assert ev_iqr.count >= 1
    assert ev_iqr.max_outlier_value == 500.0
    ev_z = column_outlier_evidence(s, "vals", method="zscore", threshold=2.0)
    assert ev_z.count >= 1


def test_five_number_summary():
    """Verify five_number_summary returns correct fences."""
    vals = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    res = five_number_summary(vals)
    assert res["q1"] is not None
    assert res["median"] == 5.5
    assert res["q3"] is not None
    assert res["iqr"] is not None


def test_statistics_engine_constant_column():
    """Test statistics engine on dataset with constant column."""
    df = pd.DataFrame({
        "constant_num": [42.0] * 50,
        "constant_str": ["FIXED"] * 50,
    })
    engine = StatisticalEngine()
    results = engine.analyze(df)
    assert results is not None
    assert "constant_num" in results.column_statistics
