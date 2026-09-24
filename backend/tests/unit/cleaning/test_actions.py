"""Cleaning action classification tests.

The engine's mutation budget and reporting logic keys off
``ActionSpec.kind``. These tests assert the *correct* classification so that
the two known misclassifications are surfaced as failures:

  - BUG-CLN-06: DropColumnAction.spec.kind == "row_removal" although it removes
    a column, not rows (rows_affected == 0; the cells are removed from the
    schema). A column drop is a schema-level mutation, not a row removal.
  - BUG-CLN-07: HTMLDecodingAction.spec.kind == "annotation" although it
    rewrites cell *content* (decodes HTML entities).

Both misclassifications skew the budget accounting computed in the engine
(``cleaning/engine.py`` mutation budget) and the log-based accounting in
``cleaning/validation.py``.
"""

from __future__ import annotations

import pandas as pd
import pytest

from backend.cleaning.actions import (
    DEFAULT_ACTIONS,
    CoordinateValidatorAction,
    DropColumnAction,
    DuplicateRemovalAction,
    HTMLDecodingAction,
    MissingValueAction,
    OutlierFlagAction,
)
from backend.cleaning.contracts import ActionKind, Decision
from backend.cleaning.contracts import Evidence

COMPONENT = "Cleaning/Actions"
STAGE = "action_classification"


def _assert_kind(action, expected_kind, test_id):
    spec = getattr(action, "spec", None)
    assert spec is not None, f"{action.name} missing ActionSpec"
    assert spec.kind == expected_kind, (
        f"[{test_id}] {COMPONENT} | stage={STAGE}\n"
        f"  expected ActionSpec.kind: {expected_kind}\n"
        f"  actual:                   {spec.kind}\n"
        f"  action:                   {action.name}"
    )


def test_action_kinds_correct_ones():
    """Baseline: actions that are correctly classified must stay correct."""
    _assert_kind(MissingValueAction(), ActionKind.CONTENT, "CLN-040")
    _assert_kind(DuplicateRemovalAction(), ActionKind.ROW_REMOVAL, "CLN-041")
    _assert_kind(OutlierFlagAction(), ActionKind.ANNOTATION, "CLN-042")
    _assert_kind(CoordinateValidatorAction(), ActionKind.CONTENT, "CLN-043")


def test_drop_column_action_kind_bug():
    """BUG-CLN-06: DropColumnAction must be a schema mutation, not row removal.

    Dropping a column removes 0 rows (probe: rows_affected=0, cells_changed>0).
    Classifying it as ``row_removal`` makes row-accounting and budget math
    treat column drops as row drops.
    """
    _assert_kind(DropColumnAction(), "schema", "CLN-044")


def test_html_decoding_action_kind_bug():
    """BUG-CLN-07: HTMLDecodingAction mutates cell *content*, so its kind must
    be CONTENT. Classifying it as ``annotation`` hides the content mutation
    from the mutation budget."""
    _assert_kind(HTMLDecodingAction(), ActionKind.CONTENT, "CLN-045")


def test_all_default_actions_have_spec():
   for name, action in DEFAULT_ACTIONS.items():
        assert hasattr(action, "spec"), name
        assert action.spec.kind in {"content", "annotation", "row_removal", "schema"}, name


def test_drop_column_action_does_not_remove_rows():
    """Semantic check backing BUG-CLN-06: applying DropColumnAction to a
    10-row frame must leave 10 rows (columns shrink, rows are untouched)."""
    action = DropColumnAction()
    rng = pd.date_range("2024-01-01", periods=10)
    df = pd.DataFrame({"id": range(10), "date": rng, "value": list(range(10))})
    decision = Decision(
        evidence=Evidence(
            detector="Dummy", problem_type="missing_values", column="value",
            method="probe", affected_count=0, statistics={},
        ),
        verdict="apply",
        action="DropColumnAction",
        parameters={"column": "value", "reason": "test"},
    )
    out, info = action.apply(df, decision)
    assert out.shape[0] == 10
    assert "value" not in out.columns
    assert info["rows_affected"] == 0