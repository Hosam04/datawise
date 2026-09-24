"""Tests for Group Leakage (repeated customer_id / patient_id across rows)."""

import pytest
import pandas as pd
from sklearn.model_selection import train_test_split
from backend.tests.leakage.datasets import make_group_leakage_dataset
from backend.tests.leakage.helpers import get_group_overlap


def test_group_leakage_in_train_test_split():
    """Verify whether records from the same customer/patient group appear in BOTH
    train and test partitions when grouping structure exists.
    
    NOTE: This test demonstrates that standard sklearn train_test_split causes
    group leakage. For production use, a group-aware split function should be used.
    """
    df = make_group_leakage_dataset(n_groups=50, rows_per_group=6, seed=42)
    
    # Standard split vs group split
    train_df, test_df = train_test_split(df, test_size=0.2, random_state=42)
    overlap = get_group_overlap(train_df, test_df, "customer_id")
    
    # In standard i.i.d. splitting without group awareness, almost all groups overlap
    overlap_ratio = len(overlap) / df["customer_id"].nunique()
    
    assert overlap_ratio > 0.5, (
        f"Expected significant group leakage with standard train_test_split, "
        f"but only {overlap_ratio:.1%} groups overlapped."
    )
