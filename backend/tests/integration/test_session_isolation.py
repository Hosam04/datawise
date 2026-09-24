"""Integration tests: Multi-session isolation and persistence."""

import os
import pytest
from backend.core.storage import AnalysisRepository


def test_session_isolation_multiple_sessions():
    """Ensure data from one session cannot bleed into another session."""
    repo = AnalysisRepository()
    sess_1 = "session-iso-1"
    sess_2 = "session-iso-2"

    repo.create(sess_1)
    repo.create(sess_2)

    repo.complete(sess_1, {"dataset_name": "Dataset_One.csv", "metric": 100})
    repo.complete(sess_2, {"dataset_name": "Dataset_Two.csv", "metric": 200})

    data_1 = repo.get(sess_1)
    data_2 = repo.get(sess_2)

    assert data_1["dataset_name"] == "Dataset_One.csv"
    assert data_1["metric"] == 100

    assert data_2["dataset_name"] == "Dataset_Two.csv"
    assert data_2["metric"] == 200

    assert data_1["dataset_name"] != data_2["dataset_name"]
