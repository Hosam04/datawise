"""Conftest for Data Leakage test suite."""

import pytest
import pandas as pd
from backend.ml.analyzer import MLAnalyzer
from backend.agents.model_selection.model_selection_agent import ModelSelectionAgent
from backend.tests.leakage.datasets import (
    make_direct_target_leakage_dataset,
    make_derived_target_leakage_dataset,
    make_perfect_correlation_leakage_dataset,
    make_near_perfect_leakage_dataset,
    make_temporal_future_leakage_dataset,
    make_post_target_leakage_dataset,
    make_semantic_duplicate_leakage_dataset,
    make_duplicate_rows_dataset,
    make_group_leakage_dataset,
    make_legitimate_predictive_dataset,
)


@pytest.fixture
def analyzer():
    return MLAnalyzer()


@pytest.fixture
def model_selector():
    return ModelSelectionAgent()


@pytest.fixture
def direct_leakage_df():
    return make_direct_target_leakage_dataset()


@pytest.fixture
def derived_leakage_df():
    return make_derived_target_leakage_dataset()


@pytest.fixture
def correlation_leakage_df():
    return make_perfect_correlation_leakage_dataset()


@pytest.fixture
def near_perfect_leakage_df():
    return make_near_perfect_leakage_dataset()


@pytest.fixture
def temporal_leakage_df():
    return make_temporal_future_leakage_dataset()


@pytest.fixture
def post_target_leakage_df():
    return make_post_target_leakage_dataset()


@pytest.fixture
def semantic_duplicate_df():
    return make_semantic_duplicate_leakage_dataset()


@pytest.fixture
def duplicate_rows_df():
    return make_duplicate_rows_dataset()


@pytest.fixture
def group_leakage_df():
    return make_group_leakage_dataset()


@pytest.fixture
def legitimate_df():
    return make_legitimate_predictive_dataset()
