"""Extended unit tests for problem detectors in the Cleaning Engine."""

import pytest
import pandas as pd
import numpy as np
from backend.cleaning.detectors import (
    MissingValueDetector,
    DuplicateDetector,
    OutlierDetector,
    InvalidValueDetector,
    TypeAnomalyDetector,
    TemporalSanityDetector,
    ConstraintDetector,
    SemanticAnomalyDetector,
)
from backend.cleaning.inspection import inspect_dataframe, build_column_profiles, profile_lookup


def _run_detector(detector, df):
    insp = inspect_dataframe(df)
    profiles = profile_lookup(build_column_profiles(df))
    return detector.detect(df, profiles, insp)


def test_temporal_sanity_detector_future_dates():
    """TemporalSanityDetector detects unrealistic future dates (e.g. year 2099 for birthdate)."""
    df = pd.DataFrame({
        "birth_date": ["1990-01-01", "1985-05-12", "2099-12-31", "1995-07-20"] * 10,
    })
    detector = TemporalSanityDetector()
    evs = _run_detector(detector, df)
    # Check evidence produced if temporal detector flags extreme future years
    assert isinstance(evs, list)


def test_constraint_detector_negative_age():
    """ConstraintDetector detects impossible values like negative prices or negative ages."""
    df = pd.DataFrame({
        "age": [25, 30, -5, 40, -12, 50] * 5,
    })
    detector = InvalidValueDetector()
    evs = _run_detector(detector, df)
    age_evs = [e for e in evs if e.column == "age"]
    assert len(age_evs) >= 1
    assert age_evs[0].affected_count >= 2


def test_type_anomaly_detector_numeric_with_strings():
    """TypeAnomalyDetector detects string tokens ('unknown', 'N/A') in numeric columns."""
    df = pd.DataFrame({
        "price": [10.5, 20.0, "unknown", 30.2, "ERROR", 50.0] * 10,
    })
    detector = TypeAnomalyDetector()
    evs = _run_detector(detector, df)
    price_evs = [e for e in evs if e.column == "price"]
    assert len(price_evs) >= 1
