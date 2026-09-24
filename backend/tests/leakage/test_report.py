"""Tests for Reporting Data Leakage Findings in Final Reports."""

import pytest
import pandas as pd
from backend.agents.report.report_builder_agent import ReportBuilderAgent
from backend.core.state import AgentState
from backend.ml.schemas import MLResults, MLMetrics


def test_report_builder_documents_leakage_or_model_warnings():
    """Verify that warnings regarding data leakage in MLResults are presented in the generated report."""
    state = AgentState(
        session_id="leak-test-session",
        session_dir="storage/sessions/leak-test-session",
        file_path="storage/sessions/leak-test-session/data.csv",
        user_query="Analyze dataset",
        ml_results=MLResults(
            status="success",
            selected_model="random_forest",
            problem_type="classification",
            metrics=MLMetrics(accuracy=0.95),
            warnings=["Data Leakage Warning: Feature 'target_copy' was identified as duplicate of target and dropped."],
        ),
    )

    builder = ReportBuilderAgent()
    updated_state = builder.run(state)

    report_text = updated_state.final_report
    assert "Data Leakage" in report_text or "Warning" in report_text or "target_copy" in report_text, (
        "REPORTING GAP: Final report did not mention the ML data leakage warnings!"
    )
