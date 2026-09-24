import os
import io
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.core.storage import analysis_repository


@pytest.fixture
def client():
    return TestClient(app)


def test_root_endpoint(client):
    """GET / returns API metadata and endpoints list."""
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert "DataWise API" in data.get("message", "")
    assert "endpoints" in data


def test_status_endpoint_not_found(client):
    """GET /status/{invalid_id} returns 404."""
    res = client.get("/status/nonexistent-session-id-999")
    assert res.status_code == 404


def test_status_endpoint_existing(client):
    """GET /status/{session_id} returns correct status."""
    analysis_repository.create("sess-status-test")
    res = client.get("/status/sess-status-test")
    assert res.status_code == 200
    assert res.json()["status"] == "processing"


def test_artifacts_endpoint_missing_dataset(client):
    """GET /datasets/{id}/artifacts returns 404 for missing dataset."""
    res = client.get("/datasets/missing-id/artifacts")
    assert res.status_code == 404


def test_artifacts_endpoint_completed_dataset(client):
    """GET /datasets/{id}/artifacts returns structured artifacts for completed session."""
    session_id = "sess-art-test"
    analysis_repository.create(session_id)
    analysis_repository.complete(session_id, {
        "status": "completed",
        "preview": {"columns": ["a"], "rows": [{"a": 1}], "total_rows": 1, "total_cols": 1},
        "statistics": {"statistics": {"a": {"mean": 1.0}}},
        "correlations": {},
        "outliers": {},
        "insights": {"executive_summary": "Done", "key_findings": []},
        "charts": [],
        "chartData": [],
        "report": {"url": f"/datasets/{session_id}/report/download"},
    })

    res = client.get(f"/datasets/{session_id}/artifacts")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "completed"
    assert "preview" in data
    assert "insights" in data


def test_chart_endpoint_bounds_and_errors(client):
    """GET /datasets/{id}/charts/{chart_id} handles out of bounds chart indices."""
    session_id = "sess-chart-test"
    analysis_repository.create(session_id)
    analysis_repository.complete(session_id, {
        "status": "completed",
        "chart_paths": [],
    })

    res = client.get(f"/datasets/{session_id}/charts/0")
    assert res.status_code == 404


def test_chat_endpoint_validation(client):
    """POST /datasets/{id}/chat validates empty messages and missing datasets."""
    # Missing message body
    res = client.post("/datasets/sess-123/chat", json={})
    assert res.status_code in (422, 400)

    # Empty message string
    res2 = client.post("/datasets/sess-123/chat", json={"message": "   "})
    assert res2.status_code in (422, 400)

    # Nonexistent session
    res3 = client.post("/datasets/nonexistent-chat-sess/chat", json={"message": "Hello"})
    assert res3.status_code == 404
