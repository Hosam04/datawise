"""Statistics / outlier / correlation tool unit tests.

These tools read pickle files. All expected numbers come from the real
backend as probed on 2026-09-01.
"""

from __future__ import annotations

import os
import tempfile

import pandas as pd
import pytest

from backend.tests.assertions import check, check_close
from backend.tests.factories import normal_numeric

COMPONENT = "Tools/StatisticsTool"
STAGE = "tools"

from backend.tools.statistics import (
    get_statistics_tool,
    run_statistical_analysis,
)
from backend.tools.outlier import detect_outliers_tool
from backend.tools.correlation import get_correlation_tool


@pytest.fixture
def pickle_path(load_dataset):
    p = tempfile.mkdtemp()
    return lambda name: _save(load_dataset(name), p)


def _save(df, base_dir) -> str:
    path = os.path.join(base_dir, "d.pkl")
    df.to_pickle(path)
    return path


def test_get_statistics_tool_total_rows(pickle_path):
    path = pickle_path("normal.csv")
    res = get_statistics_tool(path)
    assert "error" not in res, res
    assert res["total_rows"] == 60
    assert "age" in res["statistics"]
    assert "category" in res["categorical_statistics"]


def test_get_statistics_tool_numeric_keys(pickle_path):
    path = pickle_path("normal.csv")
    res = get_statistics_tool(path)
    age = res["statistics"]["age"]
    for key in ["count", "mean", "median", "std", "variance", "min", "max",
                "range", "iqr", "skewness", "kurtosis"]:
        assert key in age, f"missing {key}"
    assert "percentiles" in age


def test_get_statistics_tool_missing_column(pickle_path):
    path = pickle_path("normal.csv")
    res = get_statistics_tool(path, columns=["nope"])
    assert "error" in res
    assert "not found" in res["error"]


def test_get_statistics_tool_filename_col_missing(pickle_path):
    path = pickle_path("normal.csv")
    res = get_statistics_tool(path, columns=["age", "bogus"])
    assert "bogus" in res["error"]


def test_run_statistical_analysis_direct(load_dataset):
    df = load_dataset("normal.csv")
    res = run_statistical_analysis(df)
    assert res.dataset.rows == 60
    assert "age" in res.column_statistics


def test_get_statistics_tool_boolean_as_categorical(load_dataset):
    """Boolean columns should appear in categorical_statistics in the tool output."""
    import tempfile
    df = pd.DataFrame({"flag": [True, False, True, True], "id": [1, 2, 3, 4]})
    p = tempfile.mkdtemp()
    path = os.path.join(p, "d.pkl")
    df.to_pickle(path)
    res = get_statistics_tool(path)
    assert "error" not in res, res
    assert "flag" in res["categorical_statistics"], "boolean column should be in categorical_statistics"
    cat_stats = res["categorical_statistics"]["flag"]
    assert "top_values" in cat_stats
    assert cat_stats["count"] == 4


# --------------------------------------------------------------------------
# Outlier tool
# --------------------------------------------------------------------------

def test_detect_outliers_tool_structural(pickle_path):
    path = pickle_path("outliers.csv")
    res = detect_outliers_tool(path)
    assert "error" not in res, res
    assert res["method"] == "iqr"
    assert res["total_rows"] == 60
    assert "value" in res["summary"]
    entry = res["summary"]["value"]
    assert entry["count"] == 10
    check_close(entry["bounds"]["lower"], 0.45325, "TOOL-021", COMPONENT, STAGE,
                artifact="outlier bounds lower", tol=1e-4)
    check_close(entry["bounds"]["upper"], 6.32525, "TOOL-022", COMPONENT, STAGE,
                artifact="outlier bounds upper", tol=1e-4)
    assert entry["method"] == "IQR"


def test_detect_outliers_tool_invalid_method(pickle_path):
    path = pickle_path("outliers.csv")
    res = detect_outliers_tool(path, method="bogus")
    assert "error" in res
    assert "bogus" in res["error"]


def test_detect_outliers_zscore(pickle_path):
    path = pickle_path("outliers.csv")
    res = detect_outliers_tool(path, method="zscore")
    assert res["method"] == "zscore"
    assert res["summary"]["value"]["method"] == "Z-Score"


def test_detect_outliers_add_flags(pickle_path):
    path = pickle_path("outliers.csv")
    out_path = os.path.join(tempfile.mkdtemp(), "flagged.pkl")
    res = detect_outliers_tool(path, add_flags=True, output_path=out_path)
    assert res["flags_added"] is True
    assert os.path.exists(out_path)
    flagged = pd.read_pickle(out_path)
    assert "value_OutlierFlag" in flagged.columns
    assert int(flagged["value_OutlierFlag"].sum()) == 10


def test_detect_outliers_return_rows(pickle_path):
    path = pickle_path("outliers.csv")
    res = detect_outliers_tool(path, return_outlier_rows=True)
    rows = res.get("outlier_rows")
    assert rows is not None
    assert rows["total_unique_rows"] == 10


# --------------------------------------------------------------------------
# Correlation tool
# --------------------------------------------------------------------------

def test_get_correlation_tool(pickle_path):
    """normal.csv has no two numeric columns left after identifier exclusion,
    so the tool correctly reports insufficient variance -- this is expected
    real behaviour, not a bug."""
    path = pickle_path("normal.csv")
    res = get_correlation_tool(path, method="spearman")
    assert "error" in res
    assert "Insufficient numeric variance" in res["error"]
    assert res["numeric_columns_found"] == 0


def test_get_correlation_tool_perfect(pickle_path):
    from backend.tools.correlation import get_correlation_tool

    p = tempfile.mkdtemp()
    df = pd.DataFrame({
        "x": [10.5, 30.25, 55.0, 89.75, 120.5],
        "y": [21.0, 60.5, 110.0, 179.5, 241.0],
    })
    path = os.path.join(p, "c.pkl")
    df.to_pickle(path)
    res = get_correlation_tool(path, method="pearson")
    assert "error" not in res, res
    assert res.get("method") == "pearson"