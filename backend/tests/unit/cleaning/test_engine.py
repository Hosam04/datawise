"""End-to-end CleaningEngine unit tests against committed datasets.

The expected outputs below (row counts, shapes, assessments, decisions) were
probed from the real backend on 2026-09-01; they encode the *current* behavior,
including several known defects that later regression tests flag.
"""

from __future__ import annotations

import pandas as pd
import pytest

from backend.cleaning import CleaningEngine
from backend.tests.assertions import check

COMPONENT = "Cleaning/Engine"
STAGE = "engine_run"


def test_engine_clean_normal(cleaning_engine, load_dataset):
    df = load_dataset("normal.csv")
    out, res = cleaning_engine.run(df)
    assert out.shape == (60, 6)
    assert res.assessment == "CLEAN"
    assert res.success is True
    assert res.decisions == []
    assert res.log == []
    assert res.errors == []


def test_engine_missing_values_pipeline(cleaning_engine, load_dataset):
    df = load_dataset("missing_values.csv")
    out, res = cleaning_engine.run(df)
    assert out.shape == (58, 4)
    assert res.assessment == "NEEDS REVIEW"
    applied = [(l.action, l.rows_affected) for l in res.log if l.applied]
    assert ("MissingValueAction", 6) in applied
    assert ("DropColumnAction", 0) in applied
    assert ("DuplicateRemovalAction", 2) in applied
    assert "category" not in out.columns
    # age got median-imputed -> no NaN remains in age
    assert out["age"].notna().all()
    # score is only flagged, not imputed -> still has NaN
    # (18, not 20: the 2 removed duplicate rows both carried NaN in score)
    assert out["score"].isna().sum() == 18
    flagged = {(e.problem_type, e.column) for e in res.flagged_issues}
    assert ("missing_values", "score") in flagged


def test_engine_duplicates_removed(cleaning_engine, load_dataset):
    df = load_dataset("duplicates.csv")
    out, res = cleaning_engine.run(df)
    check(
        out.shape[0] == 19,
        "CLN-030", COMPONENT, STAGE, "19 rows after removing 21 duplicates",
        out.shape[0], dataset="duplicates.csv",
        root_cause="DuplicateRemovalAction with keep='first'",
    )
    assert res.assessment == "CLEAN"
    dup_log = [l for l in res.log if l.action == "DuplicateRemovalAction" and l.applied]
    assert dup_log and dup_log[0].rows_affected == 21


def test_engine_outlier_flag_only(cleaning_engine, load_dataset):
    df = load_dataset("outliers.csv")
    from backend.cleaning import CleaningEngine
    eng = CleaningEngine(add_outlier_flags=True)
    out, res = eng.run(df)
    check(
        out.shape == (60, 4),
        "CLN-031", COMPONENT, STAGE, "60 rows, outlier flag column appended",
        out.shape, dataset="outliers.csv",
        root_cause="Outliers are annotated, never modified (add_outlier_flags)",
    )


def test_engine_invalid_values_flagged(cleaning_engine, load_dataset):
    df = load_dataset("invalid_values.csv")
    out, res = cleaning_engine.run(df)
    assert out.shape[0] == 47  # 13 duplicate rows removed
    assert "age_OutlierFlag" in out.columns
    assert res.assessment == "NEEDS CLEANING"
    # out-of-range ages preserved (flagged only, not coerced)
    assert out["age"].min() < 0


def test_engine_constant_columns(cleaning_engine, load_dataset):
    df = load_dataset("constant_columns.csv")
    out, res = cleaning_engine.run(df)
    assert out.shape[0] == 53  # 7 duplicate rows removed
    assert res.assessment == "CLEAN"


def test_engine_categorical_heavy_duplicates(cleaning_engine, load_dataset):
    df = load_dataset("categorical.csv")
    out, res = cleaning_engine.run(df)
    # 48 of 60 rows are exact duplicates -> massive removal
    assert out.shape[0] == 12
    assert out.shape[1] == 4


def test_engine_text_duplicates(cleaning_engine, load_dataset):
    df = load_dataset("text.csv")
    out, res = cleaning_engine.run(df)
    assert out.shape[0] == 30
    assert res.assessment == "CLEAN"


def test_engine_datetime_duplicates(cleaning_engine, load_dataset):
    df = load_dataset("datetime.csv")
    out, res = cleaning_engine.run(df)
    assert out.shape[0] == 58
    assert res.assessment == "CLEAN"


def test_engine_large_suppression_flag(cleaning_engine, load_dataset):
    df = load_dataset("large.csv")
    out, res = cleaning_engine.run(df)
    assert out.shape == (2000, 5)
    assert res.assessment == "NEEDS REVIEW"
    flagged = {(e.problem_type, e.column, e.method) for e in res.flagged_issues}
    check(
        ("missing_values", "category", "suppression_token_classification") in flagged,
        "CLN-032", COMPONENT, STAGE,
        "category flagged for suppression tokens only",
        flagged, dataset="large.csv",
        root_cause="MissingValueDetector suppression-token heuristic fires on legitimate 's' values",
        severity="MEDIUM",
    )


def test_engine_arabic_unicode(cleaning_engine, load_dataset):
    df = load_dataset("arabic_unicode.csv")
    out, res = cleaning_engine.run(df)
    assert out.shape == (7, 5)
    assert res.assessment in ("CLEAN", "MOSTLY CLEAN")


def test_engine_tiny_dataset(cleaning_engine, load_dataset):
    df = load_dataset("tiny.csv")
    out, res = cleaning_engine.run(df)
    assert out.shape == (5, 3)
    assert res.assessment == "CLEAN"


def test_engine_high_cardinality_duplicates(cleaning_engine, load_dataset):
    df = load_dataset("high_cardinality.csv")
    out, res = cleaning_engine.run(df)
    assert out.shape[0] == 70
    assert res.assessment == "CLEAN"


def test_engine_rules_snapshot_populated(cleaning_engine, load_dataset):
    df = load_dataset("missing_values.csv")
    _, res = cleaning_engine.run(df)
    assert isinstance(res.rules_snapshot, dict)
    assert res.input_digest and res.output_digest


def test_engine_run_validation_accounting(cleaning_engine, load_dataset):
    df = load_dataset("missing_values.csv")
    _, res = cleaning_engine.run(df)
    rv = res.run_validation
    assert rv["failures"] == []
    row_acct = rv["checks"]["row_accounting"]
    assert row_acct["original_rows"] == 60
    assert row_acct["duplicate_rows_removed"] == 2
    assert row_acct["final_rows"] == 58
    assert row_acct["ok"] is True


def test_engine_empty_frame_handled(cleaning_engine):
    from backend.tests.factories import empty_df

    out, res = cleaning_engine.run(empty_df())
    assert out.shape == (0, 0)
    assert res.success is True  # engine must not crash on empty frames


def test_engine_supports_rules_argument(cleaning_engine, load_dataset):
    """The engine accepts caller-declared rules via the constructor."""
    from backend.cleaning import CleaningEngine
    from backend.cleaning.metadata import DatasetRules, ColumnRule

    df = load_dataset("normal.csv")
    rules = DatasetRules(column_rules={"id": ColumnRule(name="id", semantic_type="identifier")})
    eng = CleaningEngine(rules=rules)
    out, res = eng.run(df)
    assert out.shape == (60, 6)