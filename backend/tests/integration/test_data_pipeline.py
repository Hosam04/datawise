"""Integration tests: Ingestion -> Profiling -> Cleaning -> Statistics."""

import os
import pytest
import pandas as pd
import numpy as np
from backend.tools.csv_reader import read_any_file
from backend.agents.profile.dataset_profile_agent import DatasetProfileAgent
from backend.cleaning.engine import CleaningEngine
from backend.statistics.engine import StatisticalEngine
from backend.core.state import AgentState


def test_data_pipeline_flow(tmp_path):
    """Verify data flows cleanly from CSV reading to Profiling, Cleaning Engine, and Statistics Engine."""
    # 1. Write raw dataset with missing values, types, and duplicate row
    df_raw = pd.DataFrame({
        "id": [1, 2, 3, 4, 4],
        "age": [25, np.nan, 35, 40, 40],
        "salary": [50000.0, 60000.0, 75000.0, 80000.0, 80000.0],
        "department": ["IT", "Sales", "IT", "HR", "HR"],
    })
    csv_path = tmp_path / "raw_pipeline.csv"
    df_raw.to_csv(csv_path, index=False)

    # 2. Ingestion
    df_ingested = read_any_file(str(csv_path))
    assert df_ingested.shape == (5, 4)

    # 3. Profiling
    state = AgentState(
        session_id="pipeline-sess-1",
        session_dir=str(tmp_path),
        file_path=str(csv_path),
        user_query="Analyze dataset",
        df=df_ingested,
    )
    profile_agent = DatasetProfileAgent()
    state = profile_agent.run(state)
    assert state.dataset_profile is not None

    # 4. Cleaning Engine
    cleaner = CleaningEngine(enable_imputation=True, enable_duplicate_removal=True)
    df_cleaned, clean_res = cleaner.run(df_ingested)
    assert clean_res.success is True
    assert df_cleaned.shape[0] <= 5

    # 5. Statistics Engine
    stats_engine = StatisticalEngine()
    stats_res = stats_engine.analyze(df_cleaned)
    assert stats_res is not None
    assert stats_res.dataset.rows == len(df_cleaned)
