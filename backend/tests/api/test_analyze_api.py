"""API-level tests for the FastAPI app (real app, isolated storage).

Uses a disk-backed pandas DataFrame uploaded as multipart form data. The
heavy ``_run_workflow_sync`` background task is monkeypatched so the API
contract is exercised cleanly without running the full model pipeline.
"""

from __future__ import annotations

import io

import pandas as pd
import pytest

from backend.app import main as main_module
from backend.tests.assertions import check


def _upload_csv(client, df, filename="data.csv", query="Analyze this dataset"):
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    files = {"file": (filename, buf.getvalue(), "text/csv")}
    return client.post("/analyze-data/", files=files, params={"query": query})


def test_analyze_data_returns_processing(datasets_dir, isolated_storage, client, monkeypatch):
    """POST /analyze-data/ returns 200 'processing' + session_id."""
    from backend.app.main import _run_workflow_sync

    captured = {}
    def fake(session_id, file_path, session_dir, query, analysis_id=None):
        captured.update(session_id=session_id, file_path=file_path, query=query)
        isolated_storage.complete(session_id, {"original_filename": session_id + ".csv"})
    monkeypatch.setattr(main_module, "_run_workflow_sync", fake)

    df = pd.read_csv(datasets_dir / "tiny.csv")
    resp = _upload_csv(client, df, filename="tiny.csv")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "processing"
    assert body["session_id"]
    assert captured["session_id"] == body["session_id"]
    assert captured["query"] == "Analyze this dataset"


def test_status_lifecycle(datasets_dir, isolated_storage, client, monkeypatch):
    """A real job transitions processing -> completed and status reflects it."""
    df = pd.read_csv(datasets_dir / "tiny.csv")

    def fake(session_id, file_path, session_dir, query, analysis_id=None):
        isolated_storage.complete(session_id, {"original_filename": "tiny.csv"})
    monkeypatch.setattr(main_module, "_run_workflow_sync", fake)

    resp = _upload_csv(client, df)
    sid = resp.json()["session_id"]

    # Background task runs synchronously in TestClient after response returns.
    status = client.get(f"/status/{sid}")
    assert status.status_code == 200
    assert status.json()["status"] == "completed"


def test_status_unknown_returns_404(isolated_storage, client):
    resp = client.get("/status/does-not-exist")
    assert resp.status_code == 404


def test_root_ok(client):
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "DataWise API"
    assert "/analyze-data/" in data.get("endpoints", {}).get("analyze", "")


def test_chart_endpoint_404_for_unknown_dataset(isolated_storage, client):
    resp = client.get("/datasets/unknown/charts/0")
    assert resp.status_code == 404


def test_artifacts_endpoint_404_for_unknown_dataset(isolated_storage, client):
    resp = client.get("/datasets/unknown/artifacts")
    assert resp.status_code == 404