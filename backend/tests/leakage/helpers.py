"""Test helpers and diagnostic spies for Data Leakage testing."""

import re
from typing import List, Set, Any, Dict, Optional
import pandas as pd
import numpy as np


def extract_features_used_in_training(ml_results: Any) -> List[str]:
    """Extract list of feature names present in the trained model results / importance."""
    if not ml_results or not hasattr(ml_results, "feature_importance"):
        return []
    items = ml_results.feature_importance or []
    return [item.feature for item in items]


def has_leaked_feature_in_importance(ml_results: Any, leaked_feature_names: List[str]) -> bool:
    """Check if any of the specified leaked feature names appear in feature importance."""
    used = extract_features_used_in_training(ml_results)
    used_lower = {f.lower() for f in used}
    for lf in leaked_feature_names:
        if lf.lower() in used_lower:
            return True
        # Check one-hot encoded variations
        if any(u.startswith(lf.lower() + "_") or u == lf.lower() for u in used_lower):
            return True
    return False


def get_split_contamination(train_df: pd.DataFrame, test_df: pd.DataFrame, feature_cols: List[str]) -> float:
    """Calculate the exact percentage of test rows that are exact duplicates of rows in train."""
    if train_df.empty or test_df.empty or not feature_cols:
        return 0.0
    train_sub = train_df[feature_cols].drop_duplicates()
    test_sub = test_df[feature_cols]
    merged = test_sub.merge(train_sub, how="inner", on=feature_cols)
    return len(merged) / max(len(test_sub), 1)


def get_group_overlap(train_df: pd.DataFrame, test_df: pd.DataFrame, group_col: str) -> Set[Any]:
    """Find overlapping group values (e.g., customer_ids) present in both train and test sets."""
    if group_col not in train_df.columns or group_col not in test_df.columns:
        return set()
    train_groups = set(train_df[group_col].dropna().unique())
    test_groups = set(test_df[group_col].dropna().unique())
    return train_groups.intersection(test_groups)


class PreprocessingSpy:
    """Spy class to monitor whether preprocessing fit() was called on full data or train-only."""

    def __init__(self):
        self.fit_calls = []

    def record_fit(self, caller: str, data_shape: tuple, rows: int):
        self.fit_calls.append({"caller": caller, "shape": data_shape, "rows": rows})
