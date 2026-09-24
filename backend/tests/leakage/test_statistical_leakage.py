"""Tests for Statistical Leakage in Imputation and Encodings."""

import pytest
import pandas as pd
import numpy as np
from backend.tools.cleaner import prepare_model_data_tool


def test_prepare_model_data_tool_frequency_encoding_uses_full_distribution(tmp_path):
    """Verify whether frequency encoding calculates class frequencies over the whole dataset
    before splitting.
    """
    pkl_path = tmp_path / "freq_data.pkl"
    # 50 rows of category "A", 50 rows of category "B"
    df = pd.DataFrame({
        "high_card_cat": ["A"] * 50 + ["B"] * 50,
        "target": [0, 1] * 50,
    })
    df.to_pickle(pkl_path)

    res = prepare_model_data_tool(str(pkl_path), target_column="target", encode_categorical=True)
    assert res["status"] == "success"

    transformed_df = pd.read_pickle(res["saved_to"])
    
    # Check if high_card_cat was frequency encoded
    freq_col = "high_card_cat_Frequency"
    if freq_col in transformed_df.columns:
        # All rows should have frequency 0.5 (computed across all 100 rows)
        assert np.allclose(transformed_df[freq_col], 0.5), (
            "Frequency encoding computed frequencies from full dataset before partition."
        )
