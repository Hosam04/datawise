"""Regression tests for the Derived Column Cleaning Engine fix.

Covers the full contract that was previously broken:
1. A valid supported derived operation is detected with exact metadata.
2. The repair action produces the exact deterministic expected result.
3. Deterministic validation passes after the repair.
4. Spurious/ambiguous derived relationships are FLAGGED, never applied.
5. A repair that fails validation still rolls back atomically.
6. Every supported operation (sum_offset, product, string_length,
   day_of_week) still repairs and passes validation end-to-end.
7. Existing duplicate-removal behavior is unchanged (21 of 40 rows
   removed as exact duplicates -> 19 rows).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.cleaning import CleaningEngine, actions as actions_module
from backend.cleaning.actions import DerivedColumnRepairAction
from backend.cleaning.contracts import CleaningPolicy, CleaningResult
from backend.cleaning.detectors import DerivedColumnConsistencyDetector
from backend.cleaning.inspection import (
    build_column_profiles,
    inspect_dataframe,
    profile_lookup,
)
from backend.cleaning.validation import _expected_frame, validate_action

COMPONENT = "Cleaning/DerivedColumns"


def _inspect(df):
    insp = inspect_dataframe(df)
    profiles = profile_lookup(build_column_profiles(df))
    return insp, profiles


def _detect_derived(df, insp, profiles):
    return DerivedColumnConsistencyDetector().detect(df, profiles, insp)


def _evidence(evs, column, method):
    return [e for e in evs if e.column == column and e.method == method]


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------

def _sum_offset_dataset(n=200, seed=42):
    rng = np.random.default_rng(seed)
    a = rng.integers(1, 60, n).astype(float)
    b = rng.integers(1, 60, n).astype(float)
    total = a + b
    df = pd.DataFrame({"a": a, "b": b, "total": total})
    df.loc[3, "total"] = -999.0
    df.loc[77, "total"] = -999.0
    return df


def _product_dataset(n=200, seed=5):
    rng = np.random.default_rng(seed)
    qty = rng.integers(1, 8, n).astype(float)
    price = rng.integers(1, 8, n).astype(float)
    total = qty * price
    df = pd.DataFrame({"qty": qty, "price": price, "total": total})
    df.loc[5, "total"] = 999.0
    df.loc[99, "total"] = 999.0
    return df


def _string_length_dataset(n=200, seed=9):
    rng = np.random.default_rng(seed)
    letters = list("abcdefghij")
    words = [
        "".join(rng.choice(letters, size=int(rng.integers(3, 10))))
        for _ in range(n)
    ]
    df = pd.DataFrame({"name": words, "name_len": [len(w) for w in words]})
    df.loc[12, "name_len"] = 999
    return df


def _weekday_dataset(n=60):
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    df = pd.DataFrame({"arrival_date": dates})
    df["weekday_of_arrival"] = dates.day_name()
    df.loc[5, "weekday_of_arrival"] = "Monday"
    return df


def _spurious_zero_dataset(n=2000, seed=3):
    """Zero-dominated columns: the 'product' relationship only 'matches'
    because both sides are trivially zero. Two genuine non-zero values
    must survive any cleaning run."""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "is_canceled": rng.integers(0, 2, n).astype(int),
        "car_parking": rng.integers(0, 2, n).astype(int),
        "babies": np.zeros(n, dtype=int),
    })
    df.loc[[10, 20], "babies"] = [1, 2]
    return df


# ---------------------------------------------------------------------------
# 1. Valid supported operation is detected with exact metadata
# ---------------------------------------------------------------------------

def test_derived_detects_valid_sum_offset_relationship():
    df = _sum_offset_dataset()
    insp, profiles = _inspect(df)
    evs = _evidence(_detect_derived(df, insp, profiles), "total", "sum_offset")

    assert len(evs) == 1
    ev = evs[0]
    assert ev.statistics["kind"] == "violations"
    assert ev.statistics["source_a"] == "a"
    assert ev.statistics["source_b"] == "b"
    assert ev.statistics["offset"] == 0
    assert ev.statistics["coverage"] >= 0.98
    assert set(ev.statistics["violation_row_labels"]) == {3, 77}
    assert ev.affected_count == 2


def test_derived_detects_product_relationship():
    df = _product_dataset()
    insp, profiles = _inspect(df)
    evs = _evidence(_detect_derived(df, insp, profiles), "total", "product")

    assert len(evs) == 1
    assert evs[0].statistics["kind"] == "violations"
    assert evs[0].statistics["source_a"] == "qty"
    assert evs[0].statistics["source_b"] == "price"
    assert evs[0].statistics["coverage"] >= 0.98


# ---------------------------------------------------------------------------
# 2 & 3. Repair produces the exact deterministic expectation + validation passes
# ---------------------------------------------------------------------------

def test_derived_repair_matches_expectation_and_validates():
    df = _sum_offset_dataset()
    insp, profiles = _inspect(df)
    ev = _evidence(_detect_derived(df, insp, profiles), "total", "sum_offset")[0]

    engine = CleaningEngine()
    decision = engine.decider.decide(ev, profiles, insp, df)
    assert decision.verdict == "apply"
    assert decision.action == "DerivedColumnRepairAction"

    action = DerivedColumnRepairAction()
    after, info = action.apply(df, decision)

    expected = _expected_frame(df, decision, info)
    pd.testing.assert_frame_equal(after, expected)

    # Only the two violating cells changed, with the canonical sum value.
    assert after.loc[[3, 77], "total"].tolist() == [
        df.loc[3, "a"] + df.loc[3, "b"],
        df.loc[77, "a"] + df.loc[77, "b"],
    ]
    untouched = after.drop([3, 77])
    pd.testing.assert_frame_equal(untouched, df.drop([3, 77]))

    vr = validate_action(df, after, decision, info, action)
    assert vr.passed, vr.failures


# ---------------------------------------------------------------------------
# 4. Spurious / ambiguous derived relationships are flagged, never applied
# ---------------------------------------------------------------------------

def test_derived_ambiguous_evidence_is_flagged_not_applied():
    df = pd.DataFrame({"a": [1.0, 2.0], "b": [2.0, 3.0], "total": [2.0, 6.0]})
    insp, profiles = _inspect(df)

    from backend.cleaning.contracts import Evidence
    ev = Evidence(
        detector="DerivedColumnConsistencyDetector",
        problem_type="derived_column",
        column="total",
        method="product",
        affected_count=1,
        affected_row_indices=[0],
        statistics={
            "source_a": "a",
            "source_b": "b",
            "coverage": 0.99,
            "rows_evaluated": 100,
            "kind": "ambiguous",
            "violation_row_labels": [0],
        },
        confidence=0.5,
        severity="low",
        explanation="ambiguous",
    )

    engine = CleaningEngine()
    decision = engine.decider.decide(ev, profiles, insp, df)
    assert decision.verdict == "flag"
    assert decision.action is None


def test_derived_spurious_zero_relations_never_repair(cleaning_engine):
    df = _spurious_zero_dataset()
    insp, profiles = _inspect(df)

    # Detector level: nothing strong enough to be a "violations" finding
    # may be emitted for the zero-dominated target.
    for ev in _detect_derived(df, insp, profiles):
        assert ev.statistics.get("kind") != "violations", ev

    # Engine level: repair is never applied and genuine non-zero values
    # (real babies=1 and babies=2 rows) are preserved untouched.
    engine = CleaningEngine(policy=CleaningPolicy(enable_derived_repair=True))
    out, res = engine.run(df)
    repairs = [
        e for e in res.log
        if e.action == "DerivedColumnRepairAction" and e.applied
    ]
    assert repairs == []
    assert {1, 2} <= set(out["babies"])


# ---------------------------------------------------------------------------
# 5. Failed validation still rolls back atomically
# ---------------------------------------------------------------------------

def test_derived_failed_validation_still_rolls_back(monkeypatch):
    df = _sum_offset_dataset()
    insp, profiles = _inspect(df)
    ev = _evidence(_detect_derived(df, insp, profiles), "total", "sum_offset")[0]

    engine = CleaningEngine()
    decision = engine.decider.decide(ev, profiles, insp, df)
    assert decision.action == "DerivedColumnRepairAction"

    real_apply = DerivedColumnRepairAction.apply

    def corrupt(self, frame, dec):
        # Write +1.0 on repaired cells: close to correct, but NOT the
        # deterministic expectation -> validation must reject it.
        out, info = real_apply(self, frame, dec)
        labels = list(dec.parameters["repair_row_labels"])
        out.loc[labels, dec.evidence.column] = (
            out.loc[labels, dec.evidence.column] + 1.0
        )
        return out, info

    monkeypatch.setattr(
        actions_module.DerivedColumnRepairAction, "apply", corrupt
    )

    result = CleaningResult()
    counters = {"per_column": {}, "total": 0}
    before = df.copy()
    working = engine._process_decision(
        decision, df.copy(), counters, result
    )

    entry = result.log[-1]
    assert entry.action == "DerivedColumnRepairAction"
    assert entry.applied is False
    assert entry.rolled_back is True
    assert entry.rollback_verified is True
    assert entry.validation is not None and not entry.validation.passed
    pd.testing.assert_frame_equal(working, before)


# ---------------------------------------------------------------------------
# 6. Every supported operation repairs and passes validation end-to-end
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "dataset_fn,column,method",
    [
        (_sum_offset_dataset, "total", "sum_offset"),
        (_product_dataset, "total", "product"),
        (_string_length_dataset, "name_len", "string_length"),
        (_weekday_dataset, "weekday_of_arrival", "day_of_week"),
    ],
)
def test_derived_all_supported_operations_repair_and_validate(
    dataset_fn, column, method
):
    df = dataset_fn()
    insp, profiles = _inspect(df)
    evs = _evidence(_detect_derived(df, insp, profiles), column, method)
    assert len(evs) == 1, f"{method}: expected one finding, got {len(evs)}"
    assert evs[0].statistics["kind"] == "violations"

    engine = CleaningEngine()
    decision = engine.decider.decide(evs[0], profiles, insp, df)
    assert decision.verdict == "apply", decision.reasons
    assert decision.action == "DerivedColumnRepairAction"
    assert decision.parameters.get("op") == method

    action = DerivedColumnRepairAction()
    after, info = action.apply(df, decision)
    expected = _expected_frame(df, decision, info)
    pd.testing.assert_frame_equal(after, expected)

    vr = validate_action(df, after, decision, info, action)
    assert vr.passed, vr.failures

    # repaired cells now satisfy the canonical formula
    reparsed = _inspect(after)
    remaining = _evidence(
        _detect_derived(after, *reparsed), column, method
    )
    assert not remaining or remaining[0].affected_count == 0


# ---------------------------------------------------------------------------
# 7. Duplicate-removal behavior is unchanged
# ---------------------------------------------------------------------------

def test_duplicate_removal_behavior_unchanged(cleaning_engine, load_dataset):
    from backend.cleaning.detectors import DuplicateDetector

    df = load_dataset("duplicates.csv")
    insp, profiles = _inspect(df)

    dup_evs = DuplicateDetector().detect(df, profiles, insp)
    dup_evs = [e for e in dup_evs if e.method == "exact_row_match"]
    assert len(dup_evs) == 1
    assert dup_evs[0].affected_count == 21

    out, res = cleaning_engine.run(df)
    removals = [
        e for e in res.log
        if e.action == "DuplicateRemovalAction" and e.applied
    ]
    assert removals
    assert sum(e.rows_affected for e in removals) == 21
    assert out.shape[0] == 19