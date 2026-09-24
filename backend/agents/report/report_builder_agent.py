import pandas as pd
from backend.agents.base.base_agent import BaseAgent
from backend.core.state import AgentState
from backend.statistics.engine import StatisticalEngine

from backend.agents.report.formatters import (
    _format_statistical_results,
    _format_insights,
    _format_ml_results,
    _format_cleaning_summary,
)


class ReportBuilderAgent(BaseAgent):
    def __init__(self):
        super().__init__("ReportBuilderAgent")

    def run(self, state: AgentState) -> AgentState:
        self.log_execution(state.session_id)
        try:
            self.logger.info("Building final report...")

            ds = state.data_summary or {}
            insights = state.insights or {}
            if isinstance(insights, str):
                insights = {"executive_summary": insights, "key_findings": []}

            statistical_results = state.statistical_results or {}

            df = state.get_df()
            if df is not None and not df.empty:
                true_missing_cells = int(df.isna().sum().sum())
                if "dataset" not in statistical_results:
                    statistical_results["dataset"] = {}
                statistical_results["dataset"]["total_missing_cells"] = true_missing_cells
                self.logger.info(f"ReportBuilder using DataFrame with {len(df)} rows, {len(df.columns)} columns")
                self.logger.info(f"Missing cells in this DataFrame: {df.isna().sum().sum()}")

            target_col = None
            if isinstance(state.target_detection, dict):
                target_col = state.target_detection.get("target_column")

            if target_col and df is not None and not df.empty:
                # BUG-003: Prefer associations already computed after target
                # detection (DatasetProfileAgent). Only fall back if still absent.
                ta = statistical_results.get("target_associations")
                has_assoc = False
                if isinstance(ta, dict):
                    has_assoc = bool(ta.get("numeric") or ta.get("categorical"))
                elif ta is not None:
                    has_assoc = True
                if not has_assoc:
                    self.logger.info(
                        f"Target '{target_col}' known, but target_associations still "
                        "missing. Computing on-the-fly (fallback)..."
                    )
                    stats_engine = StatisticalEngine()
                    target_assoc = stats_engine.target_associations(df, target_col)
                    statistical_results["target_associations"] = target_assoc.model_dump(mode="json")
                    # Keep state in sync so downstream consumers see the result
                    state.statistical_results = statistical_results

            cleaning_report = ds.get("cleaning_report", {})
            cleaning_md = _format_cleaning_summary(cleaning_report)

            # Always prefer the StatisticalEngine formatter (handles empty dict gracefully).
            # Legacy _format_stats / _format_correlation helpers were never implemented.
            statistical_md = _format_statistical_results(statistical_results or {})

            ml_md = _format_ml_results(
                state.ml_results,
                df=df,
                target=target_col
            )

            nl = chr(10)
            report = f"""{_format_insights(insights)}

{cleaning_md}

{statistical_md}

{ml_md}

## Charts Generated
**{len(state.visualization_paths or [])}** chart(s) created.
"""
            # Document intentionally skipped charts (e.g. too-sparse missing-rate plots)
            skipped = getattr(state, "skipped_charts", None) or []
            if skipped:
                report += "\n### Skipped Charts\n"
                for s in skipped:
                    report += (
                        f"- **{s.get('title', 'Untitled')}** "
                        f"(index {s.get('index')}): {s.get('reason', 'unknown reason')}\n"
                    )
            state.final_report = report
            self.logger.info("Report built successfully.")
            return state

        except Exception as e:
            self.logger.error(f"Report building failed: {str(e)}")
            state.final_report = f"# Analysis Report{chr(10)}{chr(10)}Report generation encountered an issue, but analysis data is available in the dashboard."
            return state