"""Extended unit tests for all Cleaning Actions."""

import pytest
import pandas as pd
import numpy as np
from backend.cleaning.actions import (
    MissingValueAction,
    DuplicateRemovalAction,
    OutlierFlagAction,
)
from backend.cleaning.contracts import Decision, Evidence


def test_missing_value_action_median():
    df = pd.DataFrame({"vals": [10.0, 20.0, np.nan, 40.0, 50.0]})
    action = MissingValueAction()
    ev = Evidence(detector="MissingValueDetector", problem_type="missing_values", column="vals", method="column_missing_profile", affected_count=1)
    decision = Decision(
        verdict="apply", 
        approved=True, action="MissingValueAction", evidence=ev,
        parameters={"strategy": "median", "fill_value": 30.0}, reason="Impute with median",
    )
    res_df, info = action.apply(df, decision)
    assert res_df["vals"].isna().sum() == 0
    assert res_df["vals"].iloc[2] == 30.0

def test_duplicate_removal_action():
    df = pd.DataFrame({"x": [1, 2, 2, 3], "y": ["a", "b", "b", "c"]})
    action = DuplicateRemovalAction()
    ev = Evidence(detector="DuplicateDetector", problem_type="duplicates", column=None, method="exact_row_match", affected_count=1)
    decision = Decision(
        verdict="apply",  
        approved=True, action="DuplicateRemovalAction", evidence=ev,
        parameters={"rows_to_remove": 1, "excluded_columns": []}, reason="Remove duplicates",
    )
    res_df, info = action.apply(df, decision)
    assert len(res_df) == 3
    assert info["rows_affected"] == 1

def test_outlier_flag_action():
    df = pd.DataFrame({"num": [10.0, 12.0, 11.0, 1000.0, 13.0]})
    action = OutlierFlagAction()
    ev = Evidence(detector="OutlierDetector", problem_type="outliers", column="num", method="IQR", affected_count=1, statistics={"lower_bound": 5.0, "upper_bound": 20.0})
    decision = Decision(
        verdict="apply",  
        approved=True, action="OutlierFlagAction", evidence=ev,
        parameters={"lower_bound": 5.0, "upper_bound": 20.0}, reason="Flag IQR outliers",
    )
    res_df, info = action.apply(df, decision)
    assert "num_OutlierFlag" in res_df.columns
    assert res_df["num"].iloc[3] == 1000.0