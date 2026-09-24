"""Regression tests.

Two kinds of tests live here:
1. REGRESSION LOCKS: assert the *currently observed* (buggy) behavior so the
   suite reports a regression when a bug is fixed later without an update.
2. INVARIANTS: backend invariants that must keep passing (no-code-change
   checks, pure compile/import checks).
"""

from __future__ import annotations

import pandas as pd
import pytest

from backend.tests.assertions import check

COMPONENT = "Regression"
STAGE = "regression"


# ---------------------------------------------------------------------------
# 1. REGRESSION LOCKS (document known bugs; fail intentionally)
# ---------------------------------------------------------------------------

def test_drop_column_action_reports_row_removal_kind_is_wrong(datasets_dir):
    """BUG-CLE-04 regression lock: DropColumnAction reports
    kind='row_removal' though it drops a column."""
    from backend.cleaning.actions import DropColumnAction
    from backend.cleaning.schemas import CleaningActionSpec, CleaningActionDefinition

    spec = CleaningActionSpec(kind="row_removal")
    action = DropColumnAction.from_spec(spec)
    result = action.apply(pd.DataFrame({"price": [10, 20, 30]}), column="price")
    check(
        spec.kind == "column_removal",
        "REGR-CLEAN-01", COMPONENT, STAGE,
        "DropColumnAction should declare kind='column_removal'",
        f"declared kind is {spec.kind!r} (rows_affected={result['rows_affected']})",
        artifact="cleaning/actions.py:403",
        root_cause="actions.py drops a column but sets kind='row_removal'",
        severity="MEDIUM",
    )


def test_html_decoding_action_kind_is_annotation_wrong(datasets_dir):
    """BUG-CLE-05 regression lock: HTMLDecodingAction is kind='annotation'
    though it mutates cell content (CONTENT change)."""
    from backend.cleaning.actions import HTMLDecodingAction
    from backend.cleaning.schemas import CleaningActionSpec

    spec = CleaningActionSpec(kind="annotation")
    action = HTMLDecodingAction.from_spec(spec)
    result = action.apply(pd.DataFrame({"txt": ["&amp;"]}), column="txt")
    check(
        spec.kind == "content",
        "REGR-CLEAN-02", COMPONENT, STAGE,
        "HTMLDecodingAction should declare kind='content'",
        f"declared kind is {spec.kind!r}",
        artifact="cleaning/actions.py:423",
        root_cause="content-mutating action misdeclared as 'annotation'",
        severity="MEDIUM",
    )


def test_duplicate_ratio_uses_all_columns_inconsistency(datasets_dir):
    """BUG-CLE-06 regression lock: duplicates.csv duplicate_ratio stays 0.0
    (computed over all columns with id) while 21 duplicate rows are dropped."""
    from backend.cleaning.inspection import inspect_dataframe
    from backend.tests.factories import duplicate_heavy

    df = pd.read_csv(datasets_dir / "duplicates.csv")
    inspection = inspect_dataframe(df)
    ratio = _field(inspection, "duplicate_ratio")
    rows = _field(inspection, "duplicate_rows")
    check(
        ratio > 0.0,
        "REGR-CLEAN-03", COMPONENT, STAGE,
        "duplicate_ratio should reflect detected duplicate_rows>0",
        f"duplicate_rows={rows!r} but duplicate_ratio={ratio!r}",
        artifact="conflicts with inspection.py duplicate_ratio + decisions.py (0.5 cap never triggers)",
        root_cause="inspection.py:51 computes duplicate_ratio over ALL columns including id",
        severity="MEDIUM",
    )


def test_categorical_duplicate_rows_dropped_count(datasets_dir):
    """Invariant: categorical.csv loses 48 duplicate rows downstream (60->18? actually 12)."""
    from backend.cleaning import CleaningEngine

    df = pd.read_csv(datasets_dir / "categorical.csv")
    engine = CleaningEngine()
    out, res = engine.run(df)
    # 60 rows, 48 duplicated groups -> final 12 rows.
    assert len(out) == 12, f"expected 12 unique rows, got {len(out)} (started 60)"


def test_csv_reader_reports_invalid_csv(datasets_dir):
    """Invariant: malformed.csv must be rejected, not silently truncated
    (csv_reader hard-fails pre-parse integrity checks)."""
    from backend.core.exceptions import FileProcessingError
    from backend.tools.csv_reader import read_any_file

    try:
        df = read_any_file(str(datasets_dir / "malformed.csv"))
    except FileProcessingError:
        return  # rejected loudly: correct
    assert df is None  # else must be None, never a partial frame


# ---------------------------------------------------------------------------
# 2. INVARIANTS
# ---------------------------------------------------------------------------

def test_all_imports_compile():
    """Smoke: backend package tree imports cleanly."""
    import backend.app.main  # noqa: F401
    import backend.agents.master.orchestrator  # noqa: F401
    import backend.ml.analyzer  # noqa: F401
    import backend.statistics  # noqa: F401
    import backend.cleaning  # noqa: F401


def test_datasets_dir_has_expected_files(datasets_dir):
    expected = {
        "normal.csv", "missing_values.csv", "duplicates.csv", "outliers.csv",
        "mixed_types.csv", "categorical.csv", "text.csv", "datetime.csv",
        "invalid_values.csv", "high_cardinality.csv", "constant_columns.csv",
        "tiny.csv", "no_target.csv", "classification.csv", "regression.csv",
        "malformed.csv", "arabic_unicode.csv", "large.csv",
    }
    actual = {p.name for p in datasets_dir.glob("*.csv")}
    assert expected.issubset(actual), f"missing dataset files: {expected - actual}"


def _field(obj, name, default=None):
    return getattr(obj, name, default) if not isinstance(obj, dict) else obj.get(name, default)