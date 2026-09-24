"""Tests for Train/Test Contamination via Duplicate Records."""

import pytest
import pandas as pd
from sklearn.model_selection import train_test_split
from backend.tests.leakage.datasets import make_duplicate_rows_dataset
from backend.tests.leakage.helpers import get_split_contamination


def test_train_test_split_duplicate_contamination():
    """Verify whether duplicate records in the dataset result in identical samples
    appearing in both train and test partitions, inflating evaluation metrics.
    
    NOTE: This test demonstrates that standard sklearn train_test_split causes
    contamination with duplicate records. For production use, duplicates should
    be removed before splitting.
    """
    df = make_duplicate_rows_dataset(n_unique=100, repeats=3, seed=42)
    feature_cols = ["f1", "f2"]
    
    train_df, test_df = train_test_split(df, test_size=0.2, random_state=42)
    contamination_rate = get_split_contamination(train_df, test_df, feature_cols)
    
    assert contamination_rate > 0.5, (
        f"Expected significant contamination with duplicate records, "
        f"but only {contamination_rate:.1%} of test samples were contaminated."
    )
