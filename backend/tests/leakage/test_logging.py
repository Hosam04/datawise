"""Tests for Data Leakage Logging and Audit Trail."""

import pytest
import logging
import pandas as pd
from backend.ml.analyzer import MLAnalyzer
from backend.tests.leakage.datasets import make_direct_target_leakage_dataset


def test_leakage_removal_logs_warning(analyzer, caplog):
    """When a column is dropped due to target leakage, a structured warning log must be emitted."""
    df = make_direct_target_leakage_dataset(n=300, seed=42)

    with caplog.at_level(logging.WARNING, logger="MLAnalyzer"):
        results = analyzer.run(
            df=df,
            target="target",
            selected_model="logistic_regression",
            fallback_model=None,
            problem_type="classification",
            profile={"numeric_columns": ["age", "income", "target_copy"]},
        )

    assert results.status == "success"
    # Check that a log message specifically mentioning target leakage or target_copy was captured
    log_texts = [r.message for r in caplog.records]
    has_leakage_log = any("leakage" in msg.lower() or "target_copy" in msg for msg in log_texts)
    assert has_leakage_log, (
        f"LOGGING GAP: No warning log about target leakage or dropped column was emitted! Logs: {log_texts}"
    )
