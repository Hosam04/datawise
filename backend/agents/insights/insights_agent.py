"""Main Insights Agent for the DataWise analysis pipeline."""
import json
import pandas as pd
import numpy as np

from backend.agents.base.base_agent import BaseAgent
from backend.core.state import AgentState

from backend.tools.insight_tools import build_insight_evidence
from backend.tools.insight_extractor import generate_insight_candidates
from backend.tools.insight_selector import rank_insights, select_final_insights
from backend.agents.insights.statistical_validator import validate_insights

from backend.agents.insights.constants import TYPE_LABELS
from backend.agents.insights.evidence import build_evidence, get_target_column, build_feature_importance
from backend.agents.insights.ml_evidence import _add_ml_evidence, _build_limitations
from backend.agents.insights.serialization import _serialize_finding, _confidence_label, _extract_metrics
from backend.agents.insights.fallback import _generate_fallback_insights


class InsightsAgent(BaseAgent):
    def __init__(self):
        super().__init__("InsightsAgent")

    def run(self, state: AgentState) -> AgentState:
        self.log_execution(state.session_id)

        # Build evidence
        target, full_evidence = build_evidence(state, state.get_df())

        if target is None or target not in state.get_df().columns:
            state.insight_evidence = full_evidence
            state.insights = self._build_empty_insights_response("Unable to determine target variable for analysis.")
            return state

        # Integrate ML Results as Evidence
        full_evidence = _add_ml_evidence(full_evidence, state.ml_results, state.get_df())
        full_evidence["dataset_profile"] = getattr(state, "dataset_profile", {})
        state.insight_evidence = full_evidence

        # Generate insights
        try:
            candidates = generate_insight_candidates(full_evidence)

            validated = validate_insights(candidates, state.get_df(), target=target)

            ranked = rank_insights(validated)

            structured_insights = select_final_insights(ranked) if 'select_final_insights' in globals() else ranked

            if not structured_insights:
                self.logger.warning("Pipeline returned no insights; using fallback")
                structured_insights = _generate_fallback_insights(full_evidence, target)

            full_evidence["selected_insights"] = [
                {
                    "type": getattr(i, 'type', ''),
                    "title": getattr(i, 'title', ''),
                    "finding": getattr(i, 'finding', ''),
                    "evidence": getattr(i, 'evidence', {})
                }
                for i in structured_insights
            ]

        except Exception as pipeline_error:
            self.logger.exception("Structured insight pipeline failed: %s", pipeline_error)
            structured_insights = _generate_fallback_insights(full_evidence, target)

        try:
            executive_summary = self._build_summary(structured_insights, target, state.ml_results)
        except Exception as summary_error:
            self.logger.warning("Executive summary build failed; using simple summary: %s", summary_error)
            executive_summary = (
                f"Analysis identified {len(structured_insights)} statistically validated "
                f"insights related to '{target}'."
            )

        state.insights = {
            "executive_summary": executive_summary,
            "key_findings": [
                self._serialize_finding(insight)
                for insight in structured_insights
            ],
            "recommendations": [],
            "limitations": _build_limitations(state.ml_results),
            "significant_segments": [],
            "data_quality": full_evidence.get("data_quality", {})
        }

        return state

    def _build_summary(self, insights, target: str, ml_results=None) -> str:
        if not insights:
            return f"No statistically validated patterns were found for '{target}'."
        first_title = getattr(insights[0], 'title', 'Key Finding')
        types_found = sorted({
            TYPE_LABELS.get(getattr(i, 'type', ''), getattr(i, 'type', ''))
            for i in insights if getattr(i, 'type', '')
        })
        type_desc = ", ".join(types_found) if types_found else "patterns"
        ml_note = ""
        if ml_results and ml_results.status == "success":
            ml_note = f" ML analysis using {ml_results.selected_model} was performed."
            if ml_results.used_fallback:
                ml_note = f" ML analysis used fallback model {ml_results.fallback_model} after primary failed."

        return (
            f"Analysis identified {len(insights)} statistically validated insights "
            f"({type_desc}) related to '{target}'. "
            f"Most notable finding: {first_title}.{ml_note}"
        )

    def _build_empty_insights_response(self, message: str) -> dict:
        return {
            "executive_summary": message,
            "key_findings": [],
            "recommendations": [],
            "limitations": [],
            "significant_segments": [],
            "data_quality": {}
        }

    # Delegate serialization methods to the serialization module
    _serialize_finding = staticmethod(_serialize_finding)
    _confidence_label = staticmethod(_confidence_label)
    _extract_metrics = staticmethod(_extract_metrics)