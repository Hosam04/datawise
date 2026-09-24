"""Focused tests for DerivedColumnConsistencyDetector & DerivedColumnRepairAction fix.

Verifies:
1. Decision engine passes action_params containing 'op' to DerivedColumnRepairAction.
2. DerivedColumnRepairAction executes without raising 'ValueError: Unsupported derived operation: None'.
3. Product derived operation multiplies source columns correctly.
4. Detector deduplicates candidate relationships for the same target column.
"""

from __future__ import annotations

import pandas as pd
import pytest

from backend.cleaning.contracts import Evidence, Decision, ColumnProfile, InspectionResult
from backend.cleaning.detectors import DerivedColumnConsistencyDetector
from backend.cleaning.decision import DecisionEngine, CleaningPolicy
from backend.cleaning.actions import DerivedColumnRepairAction


def test_derived_column_decision_passes_op_parameter():
    df = pd.DataFrame({
        "a": [10.0, 20.0, 30.0],
        "b": [5.0, 5.0, 5.0],
        "total": [15.0, 999.0, 35.0],
    })
    profiles = {col: ColumnProfile(name=col, physical_dtype="float64") for col in df.columns}
    inspection = InspectionResult(rows=len(df), column_count=len(df.columns))

    ev = Evidence(
        detector="DerivedColumnConsistencyDetector",
        problem_type="derived_column",
        column="total",
        method="sum_offset",
        affected_count=1,
        affected_row_indices=[1],
        statistics={
            "source_a": "a",
            "source_b": "b",
            "offset": 0,
            "coverage": 0.99,
            "rows_evaluated": 100,
            "kind": "violations",
            "violation_row_labels": [1],
        },
        confidence=0.99,
        severity="medium",
        explanation="total matches sum_offset",
    )

    engine = DecisionEngine(policy=CleaningPolicy(enable_derived_repair=True))
    decision = engine.decide(ev, profiles, inspection, df)

    assert decision.verdict == "apply"
    assert decision.action == "DerivedColumnRepairAction"
    assert decision.parameters.get("op") == "sum_offset"
    assert decision.parameters.get("source_a") == "a"
    assert decision.parameters.get("source_b") == "b"
    assert decision.parameters.get("repair_row_labels") == [1]


def test_derived_column_repair_action_executes_successfully():
    df = pd.DataFrame({
        "a": [10.0, 20.0, 30.0],
        "b": [5.0, 5.0, 5.0],
        "total": [15.0, 999.0, 35.0],  # row 1 is invalid
    })
    profiles = {col: ColumnProfile(name=col, physical_dtype="float64") for col in df.columns}
    inspection = InspectionResult(rows=len(df), column_count=len(df.columns))

    ev = Evidence(
        detector="DerivedColumnConsistencyDetector",
        problem_type="derived_column",
        column="total",
        method="sum_offset",
        affected_count=1,
        affected_row_indices=[1],
        statistics={
            "source_a": "a",
            "source_b": "b",
            "offset": 0,
            "coverage": 0.99,
            "rows_evaluated": 3,
            "kind": "violations",
            "violation_row_labels": [1],
        },
        confidence=0.99,
        severity="medium",
    )

    engine = DecisionEngine(policy=CleaningPolicy(enable_derived_repair=True))
    decision = engine.decide(ev, profiles, inspection, df)

    action = DerivedColumnRepairAction()
    repaired_df, info = action.apply(df, decision)

    assert repaired_df.loc[1, "total"] == 25.0
    assert info["rows_affected"] == 1
    assert info["op"] == "sum_offset"


def test_derived_column_repair_action_product_operation():
    df = pd.DataFrame({
        "qty": [2.0, 3.0, 4.0],
        "price": [10.0, 10.0, 10.0],
        "total": [20.0, 999.0, 40.0],
    })
    profiles = {col: ColumnProfile(name=col, physical_dtype="float64") for col in df.columns}
    inspection = InspectionResult(rows=len(df), column_count=len(df.columns))

    ev = Evidence(
        detector="DerivedColumnConsistencyDetector",
        problem_type="derived_column",
        column="total",
        method="product",
        affected_count=1,
        affected_row_indices=[1],
        statistics={
            "source_a": "qty",
            "source_b": "price",
            "coverage": 0.99,
            "rows_evaluated": 3,
            "kind": "violations",
            "violation_row_labels": [1],
        },
        confidence=0.99,
        severity="medium",
    )

    engine = DecisionEngine(policy=CleaningPolicy(enable_derived_repair=True))
    decision = engine.decide(ev, profiles, inspection, df)

    action = DerivedColumnRepairAction()
    repaired_df, info = action.apply(df, decision)

    assert repaired_df.loc[1, "total"] == 30.0
    assert info["op"] == "product"


def test_detector_deduplicates_findings_per_target_column():
    detector = DerivedColumnConsistencyDetector()
    df = pd.DataFrame({
        "a": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
        "b": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
        "c": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
        "sum_ab": [2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 999.0],
    })
    profiles = {col: ColumnProfile(name=col, physical_dtype="float64") for col in df.columns}
    inspection = InspectionResult(rows=len(df), column_count=len(df.columns))

    evidence = detector.detect(df, profiles, inspection)
    target_columns = [ev.column for ev in evidence]

    # Exactly 1 evidence per target column max
    assert len(target_columns) == len(set(target_columns))
