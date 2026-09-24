"""Whole-run validation tests (cleaning/validation.py)."""

from __future__ import annotations

import pandas as pd
import pytest

from backend.cleaning import CleaningEngine
from backend.cleaning.validation import validate_run

COMPONENT = "Cleaning/Validation"
STAGE = "run_validation"


def _run(engine, df):
    out, result = engine.run(df)
    return out, result


def test_row_accounting_missing_values(cleaning_engine, load_dataset):
    df = load_dataset("missing_values.csv")
    out, res = cleaning_engine.run(df)
    rv = res.run_validation
    acct = rv["checks"]["row_accounting"]
    assert acct["original_rows"] == 60
    assert acct["duplicate_rows_removed"] == 2
    assert acct["final_rows"] == 58
    assert acct["ok"] is True
    assert rv["failures"] == []


def test_dtype_changes_reported(cleaning_engine, load_dataset):
    """The run validation surfaces dtype changes; make sure the report
    structure always exposes the dtype_changes list (even when empty)."""
    df = load_dataset("missing_values.csv")
    out, res = cleaning_engine.run(df)
    rv = res.run_validation
    assert isinstance(rv["dtype_changes"], list)


def test_validate_run_direct():
    original = pd.DataFrame({"a": [1, 1, 2, 2, 3]})
    final = pd.DataFrame({"a": [1, 2, 3]})

    class _LogEntry:
        action = "DuplicateRemovalAction"
        applied = True
        problem_type = "duplicates"
        rows_affected = 2
        columns_touched = ["a"]

    result = type("R", (), {"log": [_LogEntry()]})()

    report = validate_run(original, final, result)
    acct = report["checks"]["row_accounting"]
    assert acct["ok"] is True
    assert report["failures"] == []


def test_validate_run_accounting_mismatch_detected():
    original = pd.DataFrame({"a": [1, 2, 3, 4]})
    final = pd.DataFrame({"a": [1, 2]})  # undocumented row loss

    class _LogEntry:
        action = "MissingValueAction"
        applied = True
        problem_type = "missing_values"
        rows_affected = 2
        columns_touched = ["a"]

    result = type("R", (), {"log": [_LogEntry()]})()
    report = validate_run(original, final, result)
    acct = report["checks"]["row_accounting"]
    assert acct["ok"] is False
    assert report["failures"], "expected a row-accounting failure"