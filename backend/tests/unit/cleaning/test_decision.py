"""Decision-engine unit tests.

Focus: the coordinate-column invalid-value decision path, whose hard-coded
"Null Island" replacement set (decision.py) silently ignores coordinate
strings that do not match one of five exact spellings, even when the
caller-declared ``allowed_values`` rule identifies them as invalid.
"""

from __future__ import annotations

import pandas as pd
import pytest

from backend.cleaning.contracts import Evidence
from backend.cleaning.decision import DecisionEngine
from backend.cleaning.inspection import build_column_profiles, inspect_dataframe, profile_lookup

COMPONENT = "Cleaning/Decision"
STAGE = "decision"


def _synthetic_invalid_values_evidence(violating_values):
    return Evidence(
        detector="InvalidValueDetector",
        problem_type="invalid_values",
        column="location",
        method="explicit_allowed_values",
        affected_count=len(violating_values),
        statistics={
            "rule": "explicit_allowed_values",
            "allowed_values": ["40.7,-74.0", "51.5,-0.1", "37.7,-122.4"],
            "violations": list(violating_values),
        },
    )


def test_coordinate_decision_apply_verdict():
    ev = _synthetic_invalid_values_evidence(["0,0", "51.2,4.0"])
    df = pd.DataFrame({"location": ["0,0", "40.7,-74.0"]})
    profiles = profile_lookup(build_column_profiles(df))
    insp = inspect_dataframe(df)
    decision = DecisionEngine().decide(ev, profiles, insp, df)
    assert decision.verdict == "apply"
    assert decision.action == "CoordinateValidatorAction"


def test_coordinate_decision_invalid_values_match_declared_violation():
    """BUG-CLN-09: the decision must pass the actual violating values to the
    action. Because decision.py hard-codes a 5-string Null-Island set, a
    declared violation such as '0.0,0.0' (or any coordinate that is not one of
    the five spellings) is *not* present in ``parameters['invalid_values']``
    and, therefore, is never corrected or flagged."""
    violating = ["0,0", "0.0,0.0", "[0, 0]", "9.9,9.9"]
    ev = _synthetic_invalid_values_evidence(violating)
    df = pd.DataFrame({"location": ["0,0", "0.0,0.0", "[0, 0]", "9.9,9.9"]})
    profiles = profile_lookup(build_column_profiles(df))
    insp = inspect_dataframe(df)
    decision = DecisionEngine().decide(ev, profiles, insp, df)
    params = decision.parameters
    invalid = set(params.get("invalid_values", []))
    missing = [v for v in violating if v not in invalid]
    assert missing == [], (
        f"[CLN-090] {COMPONENT} | stage={STAGE}\n"
        f"  expected invalid_values to cover every declared violation\n"
        f"  missing: {missing}\n"
        f"  actual invalid_values: {sorted(invalid)}\n"
        f"  likely root cause: decision.py hard-codes the Null-Island set and "
        f"ignores the evidence-level violation list"
    )


def test_non_coordinate_invalid_values_flagged():
    ev = Evidence(
        detector="InvalidValueDetector",
        problem_type="invalid_values",
        column="age",
        method="explicit_range",
        affected_count=3,
        statistics={"rule": "explicit_range", "min_allowed": 0, "max_allowed": 130},
    )
    df = pd.DataFrame({"age": [5, 200, 45]})
    profiles = profile_lookup(build_column_profiles(df))
    insp = inspect_dataframe(df)
    decision = DecisionEngine().decide(ev, profiles, insp, df)
    assert decision.verdict == "flag"
    assert decision.action is None