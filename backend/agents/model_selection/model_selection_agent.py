"""ModelSelectionAgent — Decision Maker for ML model selection.
Reads dataset profile and target detection, then selects ONE compatible model
and ONE fallback from an allowed whitelist. No training logic here.
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from backend.agents.base.base_agent import BaseAgent
from backend.core.state import AgentState

logger = logging.getLogger("ModelSelectionAgent")

# ─── Allowed Models Whitelist (EXPANDED) ───
ALLOWED_MODELS = {
    "classification": {
        "catboost": {"fallback": "random_forest", "needs": ["categorical_support"]},
        "random_forest": {"fallback": "logistic_regression", "needs": []},
        "logistic_regression": {"fallback": None, "needs": []},
        "svm": {"fallback": "logistic_regression", "needs": []},
    },
    "regression": {
        "catboost_regressor": {"fallback": "random_forest_regressor", "needs": ["categorical_support"]},
        "random_forest_regressor": {"fallback": "linear_regression", "needs": []},
        "linear_regression": {"fallback": None, "needs": []},
        "ridge": {"fallback": "linear_regression", "needs": []},
    },
    "text_classification": {
        "tfidf_logistic_regression": {"fallback": None, "needs": ["text_dominant"]},
    },
}

MIN_ROWS_FOR_ML = 100
MAX_ROWS_LIGHTWEIGHT = 5000


class ModelSelectionAgent(BaseAgent):
    def __init__(self):
        super().__init__("ModelSelectionAgent")

    def run(self, state: AgentState) -> AgentState:
        self.log_execution(state.session_id)
        profile = state.dataset_profile or {}
        target_info = state.target_detection or {}

        # ─── Step 1: Check prerequisites ───
        target = target_info.get("target_column")
        if not target:
            self.logger.info("No target detected. Skipping ML.")
            state.ml_results = self._skip("No suitable target detected")
            return state

        df = state.get_df()
        if df is None or df.empty:
            state.ml_results = self._skip("DataFrame not available")
            return state

        rows = len(df)
        if rows < MIN_ROWS_FOR_ML:
            state.ml_results = self._skip(f"Dataset too small ({rows} rows). Minimum: {MIN_ROWS_FOR_ML}")
            return state

        # ─── Step 2: Determine problem type ───
        task_type = target_info.get("task_type", "unknown")
        is_numeric_target = target_info.get("is_numeric", False)

        if task_type == "classification" or (not is_numeric_target and df[target].nunique() <= 20):
            problem_type = "classification"
        elif task_type == "regression" or is_numeric_target:
            problem_type = "regression"
        else:
            state.ml_results = self._skip(f"Unsupported task type: {task_type}")
            return state

        # ─── Step 3: Determine data modality ───
        numeric_cols = profile.get("numeric_columns", [])
        categorical_cols = profile.get("categorical_columns", [])
        total_cols = len(df.columns)

        text_cols = []
        for col in df.columns:
            if col == target:
                continue
            if df[col].dtype == object or str(df[col].dtype) == "string":
                unique_ratio = df[col].nunique() / max(len(df), 1)
                avg_len = df[col].dropna().astype(str).str.len().mean()
                if unique_ratio > 0.05 and avg_len > 20:
                    text_cols.append(col)

        text_ratio = len(text_cols) / max(total_cols - 1, 1)
        categorical_ratio = len(categorical_cols) / max(total_cols - 1, 1)
        numeric_ratio = len(numeric_cols) / max(total_cols - 1, 1)

        if text_ratio > 0.5 and problem_type == "classification":
            data_modality = "text"
            problem_type = "text_classification"
        else:
            data_modality = "tabular"

        # ─── Step 4: Check model availability ───
        catboost_available = self._check_package("catboost")
        xgboost_available = self._check_package("xgboost")
        lightgbm_available = self._check_package("lightgbm")

        # ─── Step 5: Select model ───
        selected_model, fallback_model, reasons, confidence = self._select_model(
            problem_type=problem_type,
            data_modality=data_modality,
            rows=rows,
            numeric_ratio=numeric_ratio,
            categorical_ratio=categorical_ratio,
            text_cols=text_cols,
            catboost_available=catboost_available,
            xgboost_available=xgboost_available,
            lightgbm_available=lightgbm_available,
            profile=profile,
        )

        # ─── Step 6: Safety validation ───
        if not selected_model:
            state.ml_results = self._skip("Could not determine suitable model")
            return state

        if selected_model not in ALLOWED_MODELS.get(problem_type, {}):
            self.logger.warning(f"Selected model {selected_model} not in allowed list. Using fallback.")
            selected_model = fallback_model
            fallback_model = None

        # ─── Step 7: Check class imbalance for classification ───
        warnings = []
        if problem_type in ("classification", "text_classification"):
            target_counts = df[target].value_counts()
            min_class_ratio = target_counts.min() / target_counts.max()
            if min_class_ratio < 0.2:
                warnings.append(f"Class imbalance detected: minority ratio {min_class_ratio:.2f}")

        # ─── Step 8: Store decision in state ───
        from backend.ml.schemas import MLResults
        state.ml_results = MLResults(
            status="pending",
            problem_type=problem_type,
            data_modality=data_modality,
            selected_model=selected_model,
            fallback_model=fallback_model,
            used_fallback=False,
            selection_reason=reasons,
            confidence=confidence,
            warnings=warnings,
            rows_used=rows,
        )

        self.logger.info(
            f"Model selected: {selected_model} | Fallback: {fallback_model} | "
            f"Problem: {problem_type} | Modality: {data_modality}"
        )
        return state

    def _select_model(
        self,
        problem_type: str,
        data_modality: str,
        rows: int,
        numeric_ratio: float,
        categorical_ratio: float,
        text_cols: List[str],
        catboost_available: bool,
        xgboost_available: bool,
        lightgbm_available: bool,
        profile: Dict[str, Any],
    ) -> Tuple[str, Optional[str], List[str], float]:
        """Deterministic model selection logic with expanded model support."""
        reasons = []

        # ─── Text Classification ───
        if problem_type == "text_classification":
            reasons.append("Text-dominant dataset detected")
            reasons.append("TF-IDF + Logistic Regression is lightweight and appropriate")
            return "tfidf_logistic_regression", None, reasons, 0.90

        # ─── Tabular Classification ───
        if problem_type == "classification":
            # High categorical → CatBoost > LightGBM > XGBoost
            if categorical_ratio > 0.30 and rows > 500:
                if catboost_available:
                    reasons.append(f"High categorical ratio ({categorical_ratio:.1%})")
                    reasons.append("CatBoost handles categorical features natively")
                    return "catboost", "random_forest", reasons, 0.87

            # Medium dataset → Boosting
            if rows > 1000:
                if catboost_available:
                    reasons.append("Medium/large dataset with mixed features")
                    return "catboost", "random_forest", reasons, 0.85

            # Small dataset → Simpler models
            if rows < 500:
                if numeric_ratio > 0.7:
                    reasons.append("Small numeric dataset — SVM performs well")
                    return "svm", "logistic_regression", reasons, 0.75
                else:
                    reasons.append("Small dataset — Random Forest is robust")
                    return "random_forest", "logistic_regression", reasons, 0.78

            # Default
            reasons.append("Dataset suitable for tree-based model")
            reasons.append("Random Forest is robust and interpretable")
            return "random_forest", "logistic_regression", reasons, 0.80

        # ─── Tabular Regression ───
        if problem_type == "regression":
            # High categorical → CatBoost > LightGBM > XGBoost
            if categorical_ratio > 0.30 and rows > 500:
                if catboost_available:
                    reasons.append(f"High categorical ratio ({categorical_ratio:.1%})")
                    reasons.append("CatBoost Regressor handles categorical features natively")
                    return "catboost_regressor", "random_forest_regressor", reasons, 0.87

            # Medium dataset → Boosting
            if rows > 1000:
                if catboost_available:
                    reasons.append("Medium/large dataset with mixed features")
                    return "catboost_regressor", "random_forest_regressor", reasons, 0.85

            # Small numeric dataset → Linear models
            if rows < 500 and numeric_ratio > 0.8:
                reasons.append("Small numeric dataset — Ridge Regression is stable")
                return "ridge", "linear_regression", reasons, 0.75

            # Default
            reasons.append("Dataset suitable for tree-based regression")
            return "random_forest_regressor", "linear_regression", reasons, 0.78

        return "", None, ["Could not match dataset to any model"], 0.0

    def _check_package(self, package_name: str) -> bool:
        """Check if a package is available."""
        try:
            __import__(package_name)
            return True
        except ImportError:
            return False

    def _skip(self, reason: str) -> Any:
        from backend.ml.schemas import MLResults
        return MLResults(status="skipped", reason=reason)