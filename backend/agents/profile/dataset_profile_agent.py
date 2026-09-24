from backend.agents.base.base_agent import BaseAgent
from backend.core.state import AgentState
import pandas as pd
import numpy as np
from typing import Dict, List, Any
import re
import os
import math
import traceback
from backend.core.constants import (
    STRONG_TARGET_KEYWORDS,
    TARGET_KEYWORDS,
    NEGATIVE_KEYWORDS,
    ID_PATTERNS,
    ID_EXACT,
    DATE_KEYWORDS,
    FILENAME_STOP_WORDS,
)
from backend.statistics import StatisticalEngine
from backend.utils.target_detection import detect_target_variable, _extract_filename_hint


class DatasetProfileAgent(BaseAgent):
    """
    Agent responsible for profiling datasets and detecting target columns.
    Generic — works with ANY dataset without domain-specific hardcoding.

    Statistical summaries are delegated to the read-only StatisticalEngine;
    this agent owns profiling structure and target detection only.
    """

    def __init__(self):
        super().__init__("DatasetProfileAgent")
        # Read-only analysis helper; never modifies any DataFrame.
        self._stats_engine = StatisticalEngine(
            include_correlations=False,
            include_distributions=False,
            include_outlier_evidence=False,
        )

    def run(self, state: AgentState) -> AgentState:
        self.log_execution(state.session_id)
        self.logger.info(f"[{self.name}] Starting dataset profiling")

        df = state.get_df()

        if df is None or df.empty:
            state.data_summary = {"total_rows": len(df), "total_cols": len(df.columns)}
            state.dataset_profile = {}
            self.logger.info(f"[{self.name}] Profiling completed successfully (empty dataframe)")
            return state
            
        self.logger.info(
            f"[{self.name}] Profiling dataframe: {df.shape[0]} rows x {df.shape[1]} columns"
        )

        try:
            profile = self._build_profile(df)
        except Exception as err:
            self.logger.error(f"[{self.name}] BUILD PROFILE ERROR: {err}\n{traceback.format_exc()}")
            raise RuntimeError(f"Dataset profiling failed for session {state.session_id}: {err}") from err

        state.dataset_profile = profile

        # Populate data_summary expected by tests and downstream agents.
        # Merge into (instead of replacing) the DataAgent payload so the
        # real cleaning report / statistical evidence already stored there
        # keeps flowing to the ReportBuilderAgent and the API payload.
        summary = state.data_summary or {}
        summary.update({
            "total_rows": int(profile.get("rows", len(df))),
            "total_cols": int(profile.get("columns", len(df.columns))),
            "memory_usage_mb": profile.get("memory_usage_mb"),
            "numeric_columns": profile.get("numeric_columns", []),
            "categorical_columns": profile.get("categorical_columns", []),
            "missing_summary": profile.get("missing_summary", {}),
        })
        state.data_summary = summary

        # Extract filename hints and pass them to target detection
        filename_hints = self._extract_filename_hint(state)

        # Use unified target detection
        target_result = detect_target_variable(
            df,
            profile=profile,
            filename_hints=filename_hints,
            filename=getattr(state, 'file_name', None) or getattr(state, 'dataset_path', None),
        )

        state.target_detection = target_result
        if target_result.get("target_column"):
            state.analysis_type = "supervised"
        else:
            state.analysis_type = "exploratory"

        self.logger.info(f"[{self.name}] Target detection result: {target_result}")

        
        target_col = target_result.get("target_column")
        if target_col and target_col in df.columns:
            try:
                statistical_results = state.statistical_results
                if statistical_results is None:
                    statistical_results = {}
                # statistical_results may be a dict (model_dump) or an object
                has_assoc = False
                if isinstance(statistical_results, dict):
                    ta = statistical_results.get("target_associations")
                    if ta:
                        # non-empty numeric or categorical lists
                        num = (ta.get("numeric") or []) if isinstance(ta, dict) else []
                        cat = (ta.get("categorical") or []) if isinstance(ta, dict) else []
                        has_assoc = bool(num or cat)
                else:
                    ta = getattr(statistical_results, "target_associations", None)
                    if ta is not None:
                        num = getattr(ta, "numeric", None) or []
                        cat = getattr(ta, "categorical", None) or []
                        has_assoc = bool(num or cat)

                if not has_assoc:
                    self.logger.info(
                        f"[{self.name}] Computing target_associations for '{target_col}' "
                        "(was missing because StatisticalEngine ran before target detection)"
                    )
                    target_assoc = self._stats_engine.target_associations(df, target_col)
                    assoc_dump = target_assoc.model_dump(mode="json")
                    if isinstance(statistical_results, dict):
                        statistical_results["target_associations"] = assoc_dump
                    else:
                        # unexpected object form — normalize to dict
                        statistical_results = (
                            statistical_results.model_dump(mode="json")
                            if hasattr(statistical_results, "model_dump")
                            else {}
                        )
                        statistical_results["target_associations"] = assoc_dump
                    state.statistical_results = statistical_results
                    self.logger.info(
                        f"[{self.name}] target_associations stored "
                        f"(numeric={len(assoc_dump.get('numeric') or [])}, "
                        f"categorical={len(assoc_dump.get('categorical') or [])})"
                    )
            except Exception as exc:
                self.logger.warning(
                    f"[{self.name}] Failed to compute target_associations for "
                    f"'{target_col}': {exc}"
                )

        self.logger.info(f"[{self.name}] Profiling completed successfully")

        return state

    def _extract_filename_hint(self, state: AgentState) -> List[str]:
        """Extract meaningful words from the dataset filename."""
        filename = None
        if hasattr(state, 'dataset_path') and state.dataset_path:
            filename = os.path.basename(state.dataset_path)
        elif hasattr(state, 'file_name') and state.file_name:
            filename = state.file_name
        elif hasattr(state, 'uploaded_file') and state.uploaded_file:
            filename = getattr(state.uploaded_file, 'filename', None)

        if not filename:
            return []

        return _extract_filename_hint(filename)

    def _safe_round(self, val: Any, decimals: int = 4) -> float | None:
        """Safely convert numeric values and handle NaNs/Infs for clean state storage."""
        if val is None or pd.isna(val):
            return None
        try:
            f_val = float(val)
            if math.isnan(f_val) or math.isinf(f_val):
                return None
            return round(f_val, decimals)
        except (ValueError, TypeError):
            return None

    def _build_profile(self, df: pd.DataFrame) -> Dict[str, Any]:
        profile = {
            "rows": len(df),
            "columns": len(df.columns),
            "column_types": {},
            "possible_id_columns": [],
            "possible_date_columns": [],
            "categorical_columns": [],
            "numeric_columns": [],
            "numeric_stats": {},
            "missing_summary": {},
            "memory_usage_mb": round(df.memory_usage(deep=True).sum() / 1024**2, 2),
            "date_columns": [],
            "binary_columns": [],
            "discrete_columns": [],
            "continuous_columns": [],
        }

        for col in df.columns:
            str_col = str(col)
            series = df[col]
            n_total = len(series)
            n_unique = series.nunique()
            n_missing = series.isna().sum()

            unique_ratio = n_unique / n_total if n_total > 0 else 0
            missing_ratio = n_missing / n_total if n_total > 0 else 0

            dtype = self._infer_dtype(series, str_col)
            profile["column_types"][str_col] = dtype

            profile["missing_summary"][str_col] = {
                "missing_count": int(n_missing),
                "missing_ratio": round(missing_ratio, 4)
            }

            if self._is_id_column(str_col, series, unique_ratio):
                profile["possible_id_columns"].append(str_col)
                continue

            if self._is_date_column(str_col, series):
                profile["possible_date_columns"].append(str_col)
                continue

            if pd.api.types.is_numeric_dtype(series):
                profile["numeric_columns"].append(str_col)

                if n_unique <= 2:
                    profile["binary_columns"].append(str_col)
                elif n_unique <= 15:
                    profile["discrete_columns"].append(str_col)
                else:
                    profile["continuous_columns"].append(str_col)

                non_null = series.dropna()
                if len(non_null) > 0:
                    # Delegated to the Statistical Engine
                    summary = self._stats_engine.describe_column(series, str_col)
                    
                    
                    if hasattr(summary, 'mean'):
                        profile["numeric_stats"][str_col] = {
                            "mean": self._safe_round(summary.mean),
                            "std": self._safe_round(summary.std) if len(non_null) > 1 else 0.0,
                            "min": self._safe_round(summary.min),
                            "max": self._safe_round(summary.max),
                            "median": self._safe_round(summary.median),
                            "unique_count": int(n_unique),
                            "unique_ratio": round(unique_ratio, 4)
                        }
                    else:
                        profile["numeric_stats"][str_col] = {
                            "unique_count": int(n_unique),
                            "unique_ratio": round(unique_ratio, 4),
                            "mode": getattr(summary, 'mode', None),
                            "top": getattr(summary, 'top', None),
                            "warning": "Statistical Engine returned categorical summary for numeric column"
                        }

            else:
                profile["categorical_columns"].append(str_col)

        return profile  

    def _infer_dtype(self, series: pd.Series, col_name: str) -> str:
        if pd.api.types.is_datetime64_any_dtype(series):
            return "datetime"
        elif pd.api.types.is_bool_dtype(series):
            return "boolean"
        elif pd.api.types.is_integer_dtype(series):
            return "integer"
        elif pd.api.types.is_float_dtype(series):
            return "float"
        elif isinstance(series.dtype, pd.CategoricalDtype):
            return "categorical"
        else:
            if any(kw in col_name.lower() for kw in DATE_KEYWORDS[:5]):
                return "string (possible datetime)"
            return "string/object"

    def _is_id_column(self, col: str, series: pd.Series, unique_ratio: float) -> bool:
        col_lower = col.lower()

        if col_lower in ID_EXACT:
            return True

        if any(col_lower.endswith(p) for p in ID_PATTERNS):
            if unique_ratio > 0.9:
                return True

        if pd.api.types.is_integer_dtype(series) and unique_ratio > 0.99:
            sorted_vals = series.dropna().sort_values()
            if len(sorted_vals) > 1:
                diffs = sorted_vals.diff().dropna()
                if (diffs == 1).all():
                    return True

        return False

    def _is_date_column(self, col: str, series: pd.Series) -> bool:
        if pd.api.types.is_numeric_dtype(series):
            return False

        col_lower = col.lower()

        if pd.api.types.is_datetime64_any_dtype(series):
            return True

        if any(kw in col_lower for kw in DATE_KEYWORDS):
            if series.dtype == object:
                try:
                    pd.to_datetime(series.dropna().iloc[:100], errors="raise")
                    return True
                except (ValueError, TypeError):
                    pass
            return False

        return False
