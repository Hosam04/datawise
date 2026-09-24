"""E2E Test: Dataset D — Text / Categorical Heavy Dataset."""

import pathlib
import tempfile
import pytest
import pandas as pd
import numpy as np
from backend.agents.master.orchestrator import create_workflow
from backend.core.state import AgentState


def test_text_heavy_pipeline_e2e():
    """End-to-End run on text-dominant dataset."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="e2e-text-"))
    n = 120
    reviews = [
        "This product was great and worked well.",
        "Terrible experience, broke after two days.",
        "Average quality, nothing special.",
        "Loved the design and fast shipping.",
    ] * 30
    targets = ["positive", "negative", "neutral", "positive"] * 30

    df = pd.DataFrame({
        "review_text": reviews,
        "sentiment": targets,
    })
    csv_path = tmp / "text_dataset.csv"
    df.to_csv(csv_path, index=False)

    state = AgentState(
        session_id="e2e-text-sess",
        session_dir=str(tmp),
        file_path=str(csv_path),
        user_query="Analyze customer reviews and sentiment",
    )

    graph = create_workflow()
    result = graph.invoke(state)
    result_state = AgentState.model_validate(result)

    assert result_state.final_report != ""
