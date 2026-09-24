"""StatisticalEngine and univariate statistics tests.

All expected values were probed against the real backend on 2026-09-01.
"""

from __future__ import annotations

import pandas as pd
import pytest

from backend.statistics import StatisticalEngine
from backend.statistics.helpers import classify_column_kind, json_safe_number
from backend.statistics.outliers import five_number_summary
from backend.statistics.univariate import categorical_summary, numeric_summary
from backend.tests.assertions import check, check_close, ensure_dict_keys

COMPONENT = "Statistics"
STAGE = "analysis"


# --------------------------------------------------------------------------
# Univariate numeric summary
# --------------------------------------------------------------------------

def test_numeric_summary_values():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0], name="a")
    ns = numeric_summary(s)
    assert ns.kind == "numeric"
    assert ns.count == 8
    assert ns.mean == 4.5
    assert ns.median == 4.5
    check_close(ns.std, 2.44949, "STAT-001", COMPONENT, STAGE)
    assert ns.variance == 6.0
    assert ns.min == 1.0
    assert ns.max == 8.0
    check_close(ns.q1, 2.75, "STAT-002", COMPONENT, STAGE, artifact="numeric_summary.q1")
    check_close(ns.q3, 6.25, "STAT-003", COMPONENT, STAGE, artifact="numeric_summary.q3")
    assert ns.iqr == 3.5
    check_close(ns.skewness, 0.0, "STAT-004", COMPONENT, STAGE)
    check_close(ns.kurtosis, -1.2, "STAT-005", COMPONENT, STAGE, artifact="kurtosis (Fisher excess)")
    check_close(ns.sem, 0.866025, "STAT-006", COMPONENT, STAGE, tol=1e-4)


def test_numeric_summary_percentiles():
    s = pd.Series(list(range(1, 101)), name="a")
    ns = numeric_summary(s)
    p = ns.percentiles
    expected = {
        "p5": 5.95, "p25": 25.75, "p50": 50.5, "p75": 75.25, "p95": 95.05,
    }
    for key, val in expected.items():
        assert key in p, f"missing {key}"
        check_close(p[key], val, f"STAT-010-{key}", COMPONENT, STAGE,
                    artifact=f"numeric_summary.percentiles[{key}]", tol=1e-6)


def test_numeric_summary_constant_column():
    ns = numeric_summary(pd.Series([5.0, 5.0, 5.0, 5.0], name="c"))
    assert ns.constant is True
    assert ns.q1 == 5.0 and ns.q3 == 5.0
    assert ns.iqr == 0.0


def test_numeric_summary_nulls_and_warnings():
    ns = numeric_summary(pd.Series([1.0, None, 3.0], name="a"))
    assert ns.null_count == 1
    assert ns.null_pct == pytest.approx(33.33, abs=0.01)
    assert ns.mean == 2.0


# --------------------------------------------------------------------------
# Categorical / boolean / text summaries
# --------------------------------------------------------------------------

def test_categorical_summary_top_values_descending():
    s = pd.Series(["x", "y", "x", "z", "x", "z", "z"], name="c")
    cs = categorical_summary(s)
    assert cs.kind == "categorical"
    counts = {t.value: t.count for t in cs.top_values}
    assert counts["x"] == 3
    assert counts["z"] == 3
    assert counts["y"] == 1
    values = [t.value for t in cs.top_values]
    assert values[0] in ("x", "z")  # highest count first


def test_boolean_summary_true_pct():
    s = pd.Series([True, False, True, True, True, True], name="b")
    from backend.statistics.univariate import boolean_summary

    bs = boolean_summary(s)
    assert bs.kind == "boolean"
    assert bs.true_count == 5
    assert bs.false_count == 1
    assert bs.true_pct == pytest.approx(83.33, abs=0.01)


def test_text_summary():
    from backend.statistics.univariate import text_summary

    s = pd.Series(["short", "a much longer string", "mid"], name="t")
    ts = text_summary(s)
    assert ts.kind == "text"
    assert ts.count == 3
    assert ts.avg_length == pytest.approx(9.33, abs=0.01)


# --------------------------------------------------------------------------
# Five-number summary (box plot data)
# --------------------------------------------------------------------------

def test_five_number_summary_basic():
    fs = five_number_summary([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    assert fs["q1"] == 2.75
    assert fs["median"] == 4.5
    assert fs["q3"] == 6.25
    assert fs["iqr"] == 3.5
    assert fs["lo_fence"] == -2.5
    assert fs["hi_fence"] == 11.5


def test_five_number_summary_nan_filtered():
    fs = five_number_summary([1.0, float("nan"), 3.0, 5.0])
    assert fs["median"] == 3.0


def test_five_number_summary_empty():
    fs = five_number_summary([])
    assert fs == {"q1": None, "median": None, "q3": None, "iqr": None,
                  "lo_fence": None, "hi_fence": None}


# --------------------------------------------------------------------------
# classify_column_kind
# --------------------------------------------------------------------------

def test_classify_column_kind_types():
    df = pd.DataFrame({
        "num": [(i * 7) % 13 + 0.5 for i in range(30)],
        "b": [i % 2 == 0 for i in range(30)],
        "dt": pd.date_range("2024-01-01", periods=30),
        "txt": [f"free text description number {i}" for i in range(30)],
        "cat": ["x", "y", "z"] * 10,
    })
    assert classify_column_kind(df["num"], "num") == "numeric"
    assert classify_column_kind(df["b"], "b") == "boolean"
    assert classify_column_kind(df["dt"], "dt") == "datetime"
    assert classify_column_kind(df["txt"], "txt") == "text"
    assert classify_column_kind(df["cat"], "cat") == "categorical"


# --------------------------------------------------------------------------
# StatisticalEngine integration
# --------------------------------------------------------------------------

@pytest.fixture
def engine():
    return StatisticalEngine(correlation_method="spearman", outlier_method="iqr", outlier_threshold=1.5)


def test_engine_analyze_structure(engine, load_dataset):
    d = engine.analyze(load_dataset("normal.csv")).model_dump(mode="json")
    required = [
        "dataset", "column_statistics", "correlations", "distributions",
        "outlier_evidence", "group_statistics", "warnings", "metadata",
    ]
    missing = ensure_dict_keys(d, required, "analyze()")
    assert missing == [], f"missing result keys: {missing}"
    assert d["metadata"]["engine"] == "StatisticalEngine"
    assert d["metadata"]["version"] == "1.1.0"
    assert d["metadata"]["correlation_method"] == "spearman"
    assert d["metadata"]["read_only"] is True
    assert d["dataset"]["rows"] == 60


def test_engine_numeric_column_statistics_consistency(engine, load_dataset):
    d = engine.analyze(load_dataset("missing_values.csv")).model_dump(mode="json")
    age = d["column_statistics"]["age"]
    assert age["kind"] == "numeric"
    assert age["null_count"] == 6
    assert age["null_pct"] == pytest.approx(10.0, abs=0.01)
    score = d["column_statistics"]["score"]
    assert score["null_count"] == 20


def test_engine_correlations_spearman(engine, load_dataset):
    d = engine.analyze(load_dataset("regression.csv")).model_dump(mode="json")
    corr = d["correlations"]
    assert corr["method"] == "spearman"
    assert "matrix" in corr and "top_pairs" in corr


def test_engine_correlation_pearson():
    eng = StatisticalEngine(correlation_method="pearson")
    # non-sequential values so neither column is identifier-like
    df = pd.DataFrame({"a": [10.5, 30.25, 55.0, 89.75, 120.5], "b": [21.0, 60.5, 110.0, 179.5, 241.0]})
    d = eng.analyze(df).model_dump(mode="json")
    assert d["correlations"]["method"] == "pearson"
    # A perfect positive linear relationship must be +1.0
    assert len(d["correlations"]["top_pairs"]) >= 1
    pair = d["correlations"]["top_pairs"][0]
    check_close(pair["correlation"], 1.0, "STAT-020", COMPONENT, STAGE)


def test_engine_identical_columns_skipped():
    """A perfectly constant correlation (identical columns) should not crash."""
    df = pd.DataFrame({"a": [1, 2, 3, 4], "b": [1, 2, 3, 4]})
    StatisticalEngine().analyze(df)  # must not raise


def test_engine_outlier_evidence_iqr_bounds(engine, load_dataset):
    d = engine.analyze(load_dataset("outliers.csv")).model_dump(mode="json")
    oe = d["outlier_evidence"]
    assert oe["method"] == "iqr"
    assert oe["threshold"] == 1.5
    value_col = next(c for c in oe["columns"] if c["column"] == "value")
    assert value_col["analyzed"] is True
    check_close(value_col["lower_bound"], 0.45325, "STAT-021", COMPONENT, STAGE,
                artifact="outlier_evidence.lower_bound", tol=1e-4)
    check_close(value_col["upper_bound"], 6.32525, "STAT-022", COMPONENT, STAGE,
                artifact="outlier_evidence.upper_bound", tol=1e-4)
    assert value_col["count"] == 10
    assert value_col["severity"] == "high"


def test_engine_outlier_zscore(engine, load_dataset):
    eng = StatisticalEngine(outlier_method="zscore")
    d = eng.analyze(load_dataset("outliers.csv")).model_dump(mode="json")
    oe = d["outlier_evidence"]
    assert oe["method"] == "zscore"
    value_col = next(c for c in oe["columns"] if c["column"] == "value")
    assert value_col["count"] == 10


def test_engine_identifier_columns_skipped_from_outliers(engine, load_dataset):
    d = engine.analyze(load_dataset("outliers.csv")).model_dump(mode="json")
    id_col = next(c for c in d["outlier_evidence"]["columns"] if c["column"] == "id")
    assert id_col["analyzed"] is False
    assert "Identifier-like" in id_col["note"]


def test_engine_empty_frame_warning():
    from backend.tests.factories import empty_df

    d = StatisticalEngine().analyze(empty_df()).model_dump(mode="json")
    assert d["dataset"]["rows"] == 0
    assert any("empty" in w.lower() for w in d["warnings"]), d["warnings"]


def test_engine_invalid_methods_raise():
    with pytest.raises(ValueError):
        StatisticalEngine(correlation_method="bogus")
    with pytest.raises(ValueError):
        StatisticalEngine(outlier_method="tukey")
    with pytest.raises(ValueError):
        StatisticalEngine(outlier_method="mad")


def test_engine_kendall_is_supported():
    eng = StatisticalEngine(correlation_method="kendall")
    df = pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": [5, 4, 3, 2, 1]})
    d = eng.analyze(df).model_dump(mode="json")
    assert d["correlations"]["method"] == "kendall"


def test_engine_analyze_never_modifies_input(engine, load_dataset):
    df = load_dataset("normal.csv")
    snapshot = df.copy(deep=True)
    engine.analyze(df)
    pd.testing.assert_frame_equal(df, snapshot)


def test_engine_non_dataframe_raises():
    with pytest.raises(TypeError):
        StatisticalEngine().analyze([1, 2, 3])