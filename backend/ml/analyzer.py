"""MLAnalyzer — Execution layer for ML training and evaluation.
Receives a selected model decision, prepares features, trains, evaluates,
and returns structured MLResults.
"""
import logging
from typing import Optional, Dict, Any

import pandas as pd

from backend.ml.schemas import MLResults
from backend.ml.model_registry import ALLOWED_MODELS, MIN_ROWS_FOR_ML
from backend.ml.training import _train_and_evaluate

logger = logging.getLogger("MLAnalyzer")


class MLAnalyzer:
    """Execution layer: receives model decision, trains and evaluates."""

    def __init__(self):
        self.logger = logging.getLogger("MLAnalyzer")

    def run(
        self,
        df: pd.DataFrame,
        target: str,
        selected_model: str,
        fallback_model: Optional[str],
        problem_type: str,
        profile: Dict[str, Any]
    ) -> MLResults:
        """Train primary model. If fails, try ONE fallback."""

        # ─── Safety Layer 1: Validate inputs ───
        if not selected_model:
            return MLResults(status="skipped", reason="No model selected.")

        if problem_type not in ALLOWED_MODELS:
            return MLResults(status="skipped", reason=f"Unsupported problem type: {problem_type}")

        if selected_model not in ALLOWED_MODELS[problem_type]:
            return MLResults(
                status="skipped",
                reason=f"Model '{selected_model}' not in allowed list for {problem_type}."
            )

        if target not in df.columns:
            return MLResults(status="skipped", reason=f"Target column '{target}' not found.")

        if len(df) < MIN_ROWS_FOR_ML:
            return MLResults(status="skipped", reason=f"Dataset too small ({len(df)} rows). Minimum: {MIN_ROWS_FOR_ML}.")

        # ─── Attempt 1: Primary Model ───
        self.logger.info(f"Training primary model: {selected_model}")
        results, _ = _train_and_evaluate(df, target, selected_model, problem_type, profile)

        if results and results.status == "success":
            self.logger.info(f"Primary model {selected_model} succeeded.")
            return results

        # ─── Attempt 2: Fallback Model (ONE only) ───
        if fallback_model and fallback_model != selected_model:
            if fallback_model in ALLOWED_MODELS.get(problem_type, []):
                self.logger.info(f"Primary failed. Training fallback: {fallback_model}")
                fallback_results, _ = _train_and_evaluate(df, target, fallback_model, problem_type, profile)
                if fallback_results and fallback_results.status == "success":
                    fallback_results.used_fallback = True
                    fallback_results.fallback_model = fallback_model
                    self.logger.info(f"Fallback model {fallback_model} succeeded.")
                    return fallback_results
                else:
                    return MLResults(
                        status="failed",
                        reason=f"Both primary ({selected_model}) and fallback ({fallback_model}) failed.",
                        selected_model=selected_model,
                        fallback_model=fallback_model,
                        used_fallback=True,
                    )

        # ─── Both failed or no fallback ───
        return MLResults(
            status="failed",
            reason=f"Primary model {selected_model} failed and no valid fallback available.",
            selected_model=selected_model,
        )