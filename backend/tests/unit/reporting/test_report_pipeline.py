"""Unit tests for ReportBuilderAgent and ReportGeneratorAgent."""

import os
import pytest
import pandas as pd
from backend.agents.report.report_builder_agent import ReportBuilderAgent
from backend.agents.report.report_generator import ReportGeneratorAgent
from backend.core.state import AgentState
from backend.ml.schemas import MLResults, MLMetrics


def test_report_builder_and_generator_flow(tmp_path):
    """Verify markdown report generation and PDF compilation."""
    df = pd.DataFrame({"a": [1, 2, 3], "b": [10, 20, 30]})
    csv_p = tmp_path / "report_data.csv"
    df.to_csv(csv_p, index=False)

    state = AgentState(
        session_id="report-test",
        session_dir=str(tmp_path),
        file_path=str(csv_p),
        user_query="Generate report",
        df=df,
        data_summary={"columns": ["a", "b"], "total_rows": 3, "total_cols": 2},
        insights={"executive_summary": "Dataset exhibits positive trend.", "key_findings": []},
        ml_results=MLResults(status="skipped", reason="Not requested"),
    )

    builder = ReportBuilderAgent()
    state = builder.run(state)

    assert state.final_report != ""
    assert "Executive Summary" in state.final_report or "executive_summary" in state.final_report.lower()

    generator = ReportGeneratorAgent()
    state = generator.run(state)

    assert state.final_report_path != ""
    assert os.path.exists(state.final_report_path)
