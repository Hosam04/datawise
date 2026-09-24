from __future__ import annotations

import pandas as pd
import pytest

from backend.cleaning.detectors import (
    DuplicateDetector,
    InvalidValueDetector,
    MissingValueDetector,
    OutlierDetector,
    TypeAnomalyDetector,
)
from backend.cleaning.inspection import build_column_profiles, inspect_dataframe, profile_lookup
from backend.tests.assertions import check
from backend.tests.factories import whitespace_missing

COMPONENT = "Cleaning/Detectors"
STAGE = "detection"


def _detect(detector, df):
    insp = inspect_dataframe(df)
    profiles = profile_lookup(build_column_profiles(df))
    return detector.detect(df, profiles, insp)


def _evidence_lookup(evidence_items, column=None, method=None):
    out = []
    for e in evidence_items:
        if column is not None and e.column != column:
            continue
        if method is not None and e.method != method:
            continue
        out.append(e)
    return out


def test_missing_value_evidence_counts(load_dataset):
    df = load_dataset("missing_values.csv")
    evs = _detect(MissingValueDetector(), df)
    by_col = {e.column: e for e in evs}
    check(
        by_col["age"].affected_count == 6,
        "CLN-020", COMPONENT, STAGE, "affected_count == 6", by_col["age"].affected_count,
        dataset="missing_values.csv", artifact="Evidence.affected_count (age)",
    )
    assert by_col["age"].statistics["nan_count"] == 6
    assert by_col["age"].statistics["missing_ratio"] == pytest.approx(0.1, abs=1e-6)
    assert by_col["score"].affected_count == 20
    assert by_col["category"].affected_count == 36
    assert by_col["category"].statistics["missing_ratio"] == pytest.approx(0.6, abs=1e-6)


def test_whitespace_only_count_is_zero_bug(load_dataset):
    df = whitespace_missing()
    evs = _evidence_lookup(_detect(MissingValueDetector(), df), column="name", method="column_missing_profile")
    assert len(evs) == 1
    stats = evs[0].statistics
    check(
        stats["whitespace_only_count"] == 1,
        "CLN-021", COMPONENT, STAGE,
        "whitespace_only_count == 1 (one whitespace-only cell '  ')",
        stats["whitespace_only_count"],
        artifact="Evidence.statistics['whitespace_only_count']",
        root_cause="MissingValueDetector._composition returns whitespace_only_count=0 by construction",
        severity="MEDIUM",
    )
    # effective_missing does treat the whitespace cell as missing
    assert stats["effective_missing"] == 1
    # the purely-padded cells must NOT be counted missing
    assert stats["padded_count"] == 3


def test_duplicate_detector_count_and_ratio_bug(load_dataset):
    df = load_dataset("duplicates.csv")
    evs = _detect(DuplicateDetector(), df)
    assert len(evs) == 1, "expected one exact_row_match evidence"
    e = evs[0]
    assert e.method == "exact_row_match"
    check(
        e.affected_count == 21,
        "CLN-022", COMPONENT, STAGE, "duplicate rows == 21 (id excluded)",
        e.affected_count, dataset="duplicates.csv", artifact="Evidence.affected_count",
    )
    stats = e.statistics
    assert stats["duplicate_rows"] == 21
    assert stats["excluded_identifier_columns"] == ["id"]
    assert stats["total_rows"] == 40
    check(
        stats["duplicate_ratio"] == pytest.approx(21 / 40, abs=1e-6),
        "CLN-023", COMPONENT, STAGE, "duplicate_ratio == 0.525",
        stats["duplicate_ratio"],
        dataset="duplicates.csv",
        artifact="Evidence.statistics['duplicate_ratio']",
        root_cause="detectors.py:321 reuses inspection.duplicate_ratio computed over all columns",
        severity="HIGH",
    )


def test_duplicate_detector_no_evidence_on_normal(load_dataset):
    evs = _detect(DuplicateDetector(), load_dataset("normal.csv"))
    assert evs == []


def test_outlier_detector_iqr_bounds(load_dataset):
    df = load_dataset("outliers.csv")
    evs = _evidence_lookup(_detect(OutlierDetector(), df), column="value", method="IQR")
    assert len(evs) == 1
    e = evs[0]
    assert e.affected_count == 10
    st = e.statistics
    # Expected bounds computed from the dataset (probed from the backend).
    assert st["lower_bound"] == pytest.approx(0.45325, abs=1e-4)
    assert st["upper_bound"] == pytest.approx(6.32525, abs=1e-4)
    assert st["q1"] == pytest.approx(2.65525, abs=1e-4)
    assert st["q3"] == pytest.approx(4.12325, abs=1e-4)
    assert st["threshold_multiplier"] == 1.5


def test_outlier_detector_iqr_bounds(load_dataset):
    df = load_dataset("outliers.csv")
    evs = _evidence_lookup(_detect(OutlierDetector(), df), column="value", method="IQR")
    assert len(evs) == 1
    e = evs[0]
    assert e.affected_count == 10
    st = e.statistics
    assert st["lower_bound"] == pytest.approx(0.45325, abs=1e-4)
    assert st["upper_bound"] == pytest.approx(6.32525, abs=1e-4)
    assert st["q1"] == pytest.approx(2.65525, abs=1e-4)
    assert st["q3"] == pytest.approx(4.12325, abs=1e-4)
    assert st["threshold_multiplier"] == 1.5


def test_invalid_value_detector_age_range(load_dataset):
    df = load_dataset("invalid_values.csv")
    evs = _evidence_lookup(_detect(InvalidValueDetector(), df), column="age", method="age_range")
    assert len(evs) == 1
    e = evs[0]
    assert e.affected_count == 6
    st = e.statistics
    assert st["rule"] == "age_range"
    assert st["min_allowed"] == 0
    assert st["max_allowed"] == 130
    assert st["min_offending"] == -5
    assert st["max_offending"] == 250


def test_type_anomaly_detector_mixed_column(load_dataset):
    df = load_dataset("mixed_types.csv")
    evs = _evidence_lookup(_detect(TypeAnomalyDetector(), df), column="mixed", method="value_class_profile")
    assert len(evs) == 1
    e = evs[0]
    assert e.affected_count == 12
    assert e.statistics["expected_class"] == "numeric"
    assert e.statistics["dominant_share"] == pytest.approx(0.7, abs=1e-6)
    assert e.statistics["observed_classes"] == {"numeric": 28, "text": 8, "boolean": 4}


def test_suppression_token_detector_flags_legitimate_value(load_dataset):
    df = pd.DataFrame(
        {"id": range(12), "grade": ["s", "s", "s", "s", "s", "s", "A", "B", "C", "A", "B", "C"]}
    )
    evs = _evidence_lookup(_detect(MissingValueDetector(), df), column="grade", method="suppression_token_classification")
    
    check(
        len(evs) == 0,
        "CLN-025", COMPONENT, STAGE,
        "no evidence: 's' is a legitimate grade value, not a suppression code",
        f"{len(evs)} evidence found (expected 0)",
        artifact="MissingValueDetector suppression_token_classification",
        root_cause="MissingValueDetector treats single-character 's' as marshalling suppression token without verifying semantics",
        severity="MEDIUM",
    )


def test_missing_value_detector_empty_frame():
    from backend.tests.factories import empty_df

    assert _detect(MissingValueDetector(), empty_df()) == []