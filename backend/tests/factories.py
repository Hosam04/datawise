"""Deterministic test-data factories.

Builds pandas DataFrames (and raw CSV bytes) for edge cases that are easier to
express in code than as static files: empty frames, header-only bytes, BOM
bytes, all-null columns, imbalanced classes, constant targets, coordinate
columns, whitespace-only cells, tz-aware datetimes, etc.
"""

from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


def make_df(rows: List[List[Any]], columns: List[str]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=columns)


def normal_numeric(n: int = 50, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "id": np.arange(n),
            "feature1": rng.normal(10, 2, n).round(3),
            "feature2": rng.integers(1, 100, n),
            "target": rng.integers(0, 2, n),
        }
    )


def imbalanced_classification(n: int = 400, seed: int = 3) -> pd.DataFrame:
    """Binary target with a ~90:10 class split (imbalanced classification)."""
    rng = np.random.default_rng(seed)
    y = np.array([0] * int(n * 0.9) + [1] * (n - int(n * 0.9)))
    rng.shuffle(y)
    x1 = np.where(y == 1, rng.normal(3, 1, n), rng.normal(0, 1, n)).round(3)
    return pd.DataFrame(
        {
            "sample_id": np.arange(n),
            "x1": x1,
            "x2": rng.normal(0, 1, n).round(3),
            "target": y,
        }
    )


def constant_target(n: int = 150) -> pd.DataFrame:
    """All rows share the same target value (constant target)."""
    rng = np.random.default_rng(11)
    return pd.DataFrame(
        {
            "id": np.arange(n),
            "x": rng.normal(0, 1, n).round(3),
            "target": np.ones(n, dtype=int),
        }
    )


def all_null_columns() -> pd.DataFrame:
    return pd.DataFrame(
        {"id": [1, 2, 3], "empty_col": [np.nan, np.nan, np.nan], "value": [1.0, 2.0, 3.0]}
    )


def coordinate_column() -> pd.DataFrame:
    """A 'location' column (object) + allowed values metadata triggers the
    CoordinateValidatorAction decision path."""
    return pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5],
            "location": ["0,0", "40.7,-74.0", "37.7,-122.4", "0,0", "51.5,-0.1"],
        }
    )


def whitespace_missing() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5],
            "name": [" alice ", "  bob  ", "carol", "  ", "dave "],
            "target": [1, 0, 1, 0, 1],
        }
    )


def tz_aware_datetime() -> pd.DataFrame:
    ts = pd.to_datetime(["2024-01-01 10:00+00:00", "2024-02-01 11:00+00:00",
                         "2024-03-01 12:00+00:00", "2024-04-01 13:00+00:00"])
    return pd.DataFrame({"id": [1, 2, 3, 4], "event": ts, "value": [1.0, 2.0, 3.0, 4.0]})


def duplicate_heavy(n_base: int = 20, n_dup_pairs: int = 8) -> pd.DataFrame:
    rows = [[i, i % 5, 1 if i % 2 else 0] for i in range(n_base)]
    for k in range(n_dup_pairs):
        rows.append([100 + k, k % 5, 1 if k % 2 else 0])
        rows.append([200 + k, k % 5, 1 if k % 2 else 0])
    return pd.DataFrame(rows, columns=["id", "group", "target"])


def outlier_heavy(seed: int = 5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    values = rng.normal(5, 1, 100)
    values[::10] = 500.0
    return pd.DataFrame({"id": np.arange(100), "measure": values.round(3), "target": np.arange(100) % 2})


def empty_df() -> pd.DataFrame:
    return pd.DataFrame()


def one_row_df() -> pd.DataFrame:
    return pd.DataFrame({"id": [1], "value": [3.0], "target": [1]})


def csv_bytes(rows: List[List[Any]], columns: List[str]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(columns)
    for r in rows:
        writer.writerow(r)
    return buf.getvalue().encode("utf-8")


def header_only_csv_bytes() -> bytes:
    return b"id,value,target\n"


def bom_utf8_csv_bytes() -> bytes:
    return (
        "\ufeffid,name,numeric_value\n"
        "1,alpha,10.5\n"
        "2,beta,20.25\n"
        "3,gamma,30.0\n"
    ).encode("utf-8")


def comma_inside_quotes_csv() -> bytes:
    return b'id,note,score\n1,"hello, world",5\n2,"a,b,c",6\n'


def empty_csv_bytes() -> bytes:
    return b""


def tab_separated_bytes() -> bytes:
    return b"id\tvalue\tlabel\n1\t10\ta\n2\t20\tb\n"


def semi_separated_bytes() -> bytes:
    return b"id;value;label\n1;10;a\n2;20;b\n"


def unrelated_fact_dict() -> Dict[str, Any]:
    """A generic evidence dict with a strong, validatable pattern."""
    return {
        "columns": ["a", "b", "c"],
        "numeric_columns": ["a", "b"],
        "categorical_columns": ["c"],
        "rows": 40,
        "descriptive_stats": {
            "a": {"mean": 5.0, "median": 5.0, "std": 2.0, "count": 40},
            "b": {"mean": 10.0, "median": 10.0, "std": 4.0, "count": 40},
        },
        "correlations": {
            "significant_pairs": [
                {"column_a": "a", "column_b": "b", "correlation": 0.9, "p_value": 0.001}
            ],
            "total_significant_pairs": 1,
        },
        "target_analysis": {
            "target_variable": "b",
            "target_type": "numeric",
            "total_records": 40,
            "overall_stats": {"mean": 10.0, "p90": 14.0},
        },
        "group_analysis": {
            "c": {
                "g1": {"mean": 8.0, "count": 20},
                "g2": {"mean": 12.0, "count": 20},
            }
        },
    }


def skewed_normal_df(seed: int = 13) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {"id": np.arange(200), "skew": rng.gamma(2, 1, 200).round(3) * rng.choice([-1, 1], 200),
         "target": rng.integers(0, 2, 200)}
    )