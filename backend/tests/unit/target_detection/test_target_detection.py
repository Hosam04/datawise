"""Comprehensive unit tests for Target Variable Detection."""

import pytest
import pandas as pd
import numpy as np
from backend.utils.target_detection import (
    detect_target_variable,
    is_identifier_column,
    get_target_column,
    has_target,
)


def test_target_detection_exact_keyword():
    """Exact match for strong target keywords like 'target', 'label', 'survived', 'churn'."""
    df = pd.DataFrame({
        "age": [20, 30, 40, 50],
        "fare": [10.5, 20.0, 30.5, 40.0],
        "survived": [0, 1, 1, 0],
    })
    res = detect_target_variable(df)
    assert res["target_column"] == "survived"
    assert res["confidence"] >= 0.90
    assert res["task_type"] == "classification"


def test_target_detection_continuous_target():
    """Continuous target detection (e.g. 'charges', 'price', 'salary')."""
    df = pd.DataFrame({
        "age": [25, 45, 35, 50],
        "bmi": [22.5, 28.0, 31.2, 26.4],
        "charges": [1200.50, 4500.20, 3100.00, 5200.80],
    })
    res = detect_target_variable(df)
    assert res["target_column"] == "charges"
    assert res["is_numeric"] is True
    assert res["task_type"] in ("regression", "classification")


def test_target_detection_identifier_columns_ignored():
    """Identifier columns (ID, customer_id, user_id) must NOT be chosen as target."""
    df = pd.DataFrame({
        "customer_id": [1001, 1002, 1003, 1004],
        "feature_a": [1.1, 2.2, 3.3, 4.4],
        "target_label": ["A", "B", "A", "B"],
    })
    res = detect_target_variable(df)
    assert res["target_column"] != "customer_id"
    assert is_identifier_column(df["customer_id"], "customer_id") is True


def test_target_detection_date_columns_ignored():
    """Datetime columns must not be selected as the target variable."""
    df = pd.DataFrame({
        "created_at": pd.date_range("2026-01-01", periods=10),
        "feature_1": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
        "outcome": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
    })
    res = detect_target_variable(df)
    assert res["target_column"] == "outcome"


def test_target_detection_empty_dataframe():
    """Empty dataframe must return empty target result gracefully."""
    df = pd.DataFrame()
    res = detect_target_variable(df)
    assert res["target_column"] is None
    assert res["confidence"] == 0.0
    assert has_target(res) is False


def test_target_detection_filename_hint():
    """Filename hints provide boost for matching columns."""
    df = pd.DataFrame({
        "feature_x": [1, 2, 3, 4],
        "feature_y": [10, 20, 30, 40],
        "churn": [0, 1, 0, 0],
    })
    res = detect_target_variable(df, filename="customer_churn_analysis.csv")
    assert res["target_column"] == "churn"
    assert res["confidence"] >= 0.90
