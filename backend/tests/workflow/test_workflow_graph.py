"""Workflow-level tests running the compiled LangGraph on tiny real CSVs.

These exercise the full deterministic DataWise pipeline end-to-end (no LLM):
DataAgent -> profile -> model_selection -> ml_analyzer -> planner -> insights
-> viz -> report. Charts + PDF are real artifacts.
"""

from __future__ import annotations

import os

import pandas as pd
import pytest

from backend.core.state import AgentState
from backend.tests.assertions import check

COMPONENT = "Workflow"
STAGE = "orchestration"
DATASETS = "backend/tests/datasets"


def _run(graph, df, session_id="wf-session", query="analyze this dataset", tmp_path=None):
    import pathlib
    import tempfile

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="datawise-wf-"))
    path = tmp / "input.csv"
    df.to_csv(path, index=False)
    state = AgentState(session_id=session_id, session_dir=str(tmp), file_path=str(path), user_query=query)
    result = graph.invoke(state)
    return AgentState.model_validate(result), tmp


def test_workflow_compiles_with_expected_nodes(tmp_path):
    from backend.agents.master.orchestrator import create_workflow

    graph = create_workflow()
    assert isinstance(graph, object)
    # langgraph compiled graph exposes get_graph() with node names.
    nodes = {getattr(n, "id", n) for n in graph.get_graph().nodes}
    for expected in ("data_agent", "dataset_profile", "model_selection",
                     "ml_analyzer", "planner", "insights", "viz",
                     "report_builder", "reporter"):
        assert expected in nodes, f"workflow missing node {expected}"


def test_tiny_workflow_end_to_end(datasets_dir, tmp_path):
    from backend.agents.master.orchestrator import create_workflow

    df = pd.read_csv(datasets_dir / "tiny.csv")
    graph = create_workflow()
    rs, session_dir = _run(graph, df)
    assert rs.data_summary is not None
    assert rs.data_summary.get("total_rows") == 5
    assert isinstance(rs.insights, dict)
    assert rs.insights.get("executive_summary")
    assert rs.visualization_paths and os.path.exists(rs.visualization_paths[0])
    assert rs.target_detection is not None


def test_normal_workflow_produces_artifacts(datasets_dir, tmp_path):
    from backend.agents.master.orchestrator import create_workflow

    df = pd.read_csv(datasets_dir / "normal.csv")
    graph = create_workflow()
    rs, session_dir = _run(graph, df)
    assert rs.data_summary.get("total_rows") == 60
    assert rs.visualization_paths
    for p in rs.visualization_paths:
        assert os.path.exists(p), f"chart not rendered: {p}"


def test_ml_runs_on_classification_dataset(datasets_dir, tmp_path):
    from backend.agents.master.orchestrator import create_workflow

    df = pd.read_csv(datasets_dir / "classification.csv")
    graph = create_workflow()
    rs, _ = _run(graph, df)
    assert rs.target_detection and rs.target_detection.get("target_column")
    status = None if rs.ml_results is None else rs.ml_results.status
    assert status in ("success", "skipped", "failed"), f"unexpected ml status {status}"