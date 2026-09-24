import os
import re
from typing import Dict, Any, Optional, List, Tuple

import numpy as np
import pandas as pd

from backend.cleaning.engine import CleaningEngine
from backend.cleaning.provenance import frame_digest
from backend.tools.feature_engineering import _feature_engineering


# ---------------------------------------------------------------------------
# Dataset-agnostic helpers
# ---------------------------------------------------------------------------
_NUMERIC_KEYWORDS = {
    'count', 'id', 'num', 'number', 'amount', 'price', 'value',
    'score', 'rate', 'ratio', 'confidence', 'probability', 'percent',
    'pct', 'total', 'sum', 'avg', 'mean', 'min', 'max', 'age',
    'year', 'month', 'day', 'hour', 'minute', 'second', 'duration',
    'size', 'length', 'width', 'height', 'weight', 'distance',
    'latitude', 'longitude', 'coord', 'x', 'y', 'z', 'retweet'
}

def _should_preserve_numeric_potential(col_name: str, series: pd.Series) -> bool:
    col_lower = str(col_name).lower()
    if any(kw in col_lower for kw in _NUMERIC_KEYWORDS):
        return True
    
    non_null = series.dropna()
    if len(non_null) == 0:
        return False
    
    numeric_parsed = pd.to_numeric(non_null.astype(str).str.strip(), errors='coerce')
    return numeric_parsed.notna().sum() / len(non_null) >= 0.95

def _get_dataframe(df_path: str) -> pd.DataFrame:
    if not os.path.exists(df_path):
        raise FileNotFoundError(f"Dataset file not found: {df_path}")
    lower = df_path.lower()
    pickle_exts = (".pkl", ".pickle")
    supported_exts = (
        ".csv",
        ".xlsx", ".xls", ".xlsm", ".xlsb",
        ".json", ".jsonl",
    )

    df = None
    if lower.endswith(pickle_exts):
        df = pd.read_pickle(df_path)
    elif lower.endswith(supported_exts):
        from backend.tools.csv_reader import read_any_file
        df = read_any_file(df_path)
    else:
        # Unknown extension: try pickle first, then CSV reader.
        try:
            df = pd.read_pickle(df_path)
        except Exception:
            from backend.tools.csv_reader import read_any_file
            df = read_any_file(df_path)

    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"File at {df_path} is not a valid DataFrame")
    return df.copy()


def _save_dataframe(df: pd.DataFrame, df_path: str) -> None:
    parent = os.path.dirname(df_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    df.to_pickle(df_path)


def _norm_name(name: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name).strip().lower())


def _find_column(df: pd.DataFrame, *candidates: str) -> Optional[str]:
    normalized = {_norm_name(c): c for c in df.columns}
    for candidate in candidates:
        if _norm_name(candidate) in normalized:
            return normalized[_norm_name(candidate)]
    return None


def _add_step(report: Dict[str, Any], step: str, **details: Any) -> None:
    report["cleaning_steps"].append({"step": step, **details})


# ---------------------------------------------------------------------------
# Post-cleaning preparation (storage / model preparation only)
# ---------------------------------------------------------------------------

def _optimize_dtypes(df: pd.DataFrame, report: Dict[str, Any]) -> pd.DataFrame:
    df = df.copy()
    conversions = []

    target_like = {
        "target", "label", "class", "survived", "outcome", "response",
        "y", "prediction", "default", "churn"
    }

    for col in df.columns:
        s = df[col]
        n = _norm_name(col)

        if pd.api.types.is_float_dtype(s):
            # Keep real-valued columns as float. Convert integer-valued floats
            # only when doing so cannot introduce information loss.
            non_null = s.dropna()
            if not non_null.empty and np.all(np.isclose(non_null % 1, 0)):
                if n in {"age", "sibsp", "parch", "family_size", "ticket_count", "cabincount"}:
                    df[col] = s.round().astype("Int64")
                    conversions.append((col, "Int64"))

        elif pd.api.types.is_integer_dtype(s):
            # BUGFIX: this used to cast low-cardinality integer columns to
            # pandas "category" dtype using a threshold with a fixed floor
            # of 10 (min(20, max(10, 5% of rows))). That floor is not
            # scaled to dataset size, so on small/medium datasets (or any
            # dataset with a discrete numeric column such as years of
            # experience, number of children, ratings-as-counts, etc.)
            # genuinely numeric columns were silently reclassified as
            # categorical. Because every downstream step (statistics,
            # correlation, outlier detection, and model-ready scaling)
            # selects columns via select_dtypes(include=[np.number]),
            # those columns quietly disappeared from numeric analysis and
            # were one-hot/frequency encoded instead of scaled, regardless
            # of what dataset was uploaded.
            #
            # Integers are left as integers. Low cardinality is still
            # useful information, so it is recorded in the report instead
            # of mutating the dtype.
            if n in target_like:
                continue

            unique = s.nunique(dropna=True)
            if 1 < unique <= min(20, max(10, int(len(df) * 0.05))):
                report.setdefault("low_cardinality_numeric_columns", []).append(
                    {"column": col, "unique_values": int(unique)}
                )

        elif pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s):
            non_null = s.dropna()
            rescued = False
            if len(non_null) >= 5:
                parsed = pd.to_numeric(
                    non_null.astype(str).str.strip(), errors="coerce"
                )
                if float(parsed.notna().mean()) >= 0.98:
                    df[col] = pd.to_numeric(s, errors="coerce")
                    conversions.append((col, str(df[col].dtype)))
                    rescued = True

            if not rescued:
                unique = s.nunique(dropna=True)
                if unique > 0 and unique <= min(50, max(10, int(len(df) * 0.10))):
                    df[col] = s.astype("category")
                    conversions.append((col, "category"))

    if conversions:
        _add_step(
            report,
            "dtype_optimization",
            conversions=[{"column": c, "dtype": d} for c, d in conversions],
        )
    return df


# ---------------------------------------------------------------------------
# Outlier handling now lives in the Cleaning Engine
# (backend/cleaning/detectors.OutlierDetector + backend/cleaning/actions.
# OutlierFlagAction): evidence-driven, decision-gated, flag-only by design.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Main cleaning tool
# ---------------------------------------------------------------------------

def clean_data_tool(
    df_path: str,
    output_path: Optional[str] = None,
    add_features: bool = True,
    impute_missing: bool = True,
    add_outlier_flags: bool = True,
    optimize_dtypes: bool = True,
    outlier_threshold: float = 1.5,
) -> dict:
    """Public cleaning entry point. Signature is a frozen contract."""
    return _clean_data_tool_impl(
        df_path,
        output_path=output_path,
        add_features=add_features,
        impute_missing=impute_missing,
        add_outlier_flags=add_outlier_flags,
        optimize_dtypes=optimize_dtypes,
        outlier_threshold=outlier_threshold,
        rules=None,
    )


def clean_data_tool_with_rules(
    df_path: str,
    rules,
    output_path: Optional[str] = None,
    add_features: bool = True,
    impute_missing: bool = True,
    add_outlier_flags: bool = True,
    optimize_dtypes: bool = True,
    outlier_threshold: float = 1.5,
) -> dict:
    """Opt-in variant accepting explicit DatasetRules metadata.

    Identical behavior and contract to clean_data_tool; the declared rules
    sharpen detection (ranges, identifier protection, suppression tokens,
    derived formulas, constraint pairs). Rules never bypass decisions,
    validation or rollback.
    """
    return _clean_data_tool_impl(
        df_path,
        output_path=output_path,
        add_features=add_features,
        impute_missing=impute_missing,
        add_outlier_flags=add_outlier_flags,
        optimize_dtypes=optimize_dtypes,
        outlier_threshold=outlier_threshold,
        rules=rules,
    )


def _clean_data_tool_impl(
    df_path: str,
    output_path: Optional[str],
    add_features: bool,
    impute_missing: bool,
    add_outlier_flags: bool,
    optimize_dtypes: bool,
    outlier_threshold: float,
    rules,
) -> dict:
    """
    Dataset-agnostic cleaning/preprocessing.

    Core problem handling (missing values, duplicates, outliers) is delegated
    to the Cleaning Engine (backend/cleaning), a conservative, evidence-driven
    subsystem with strict separation:

        Detector -> Evidence -> Decision -> Action -> Validation -> Commit/Rollback

    Safe design:
      - removes only truly empty rows/columns
      - removes exact duplicate rows ONLY when the Decision Engine approves it
        (small minority of rows); otherwise flags the issue
      - imputes missing values ONLY where evidence justifies a strategy;
        unjustified cases are left untouched and flagged
      - flags outliers instead of deleting/capping observations — always
      - extracts high-confidence derived features when source columns are recognizable
      - validates obvious impossible values
      - validates every modification against a snapshot; failed validations roll back
      - reports every transformation in a structured cleaning log
    """
    try:
        df = _get_dataframe(df_path)
        original_shape = list(df.shape)
        original_cols = list(df.columns)

        report: Dict[str, Any] = {
            "original_shape": original_shape,
            "cleaning_steps": [],
            "settings": {
                "add_features": add_features,
                "impute_missing": impute_missing,
                "add_outlier_flags": add_outlier_flags,
                "optimize_dtypes": optimize_dtypes,
                "outlier_threshold": outlier_threshold,
                "engine": "CleaningEngine",
            },
        }

        # IMPORTANT: the Cleaning Engine receives the uploaded dataframe
        # without content mutations. All evidence-driven repairs must happen
        # inside Detector -> Decision -> Action -> Validation -> Commit.
        # Feature engineering and dtype optimization are separate analytical
        # preparation phases and are never used to seed cleaning evidence.

        report["input_digest_before_cleaning"] = frame_digest(df)

        # Missingness is measured on the actual raw frame seen by the engine.
        report["missing_values_before"] = {
            str(k): int(v) for k, v in df.isna().sum().items() if int(v) > 0
        }

        # 1. CORE CLEANING via the Cleaning Engine: structural integrity,
        # inspection, column understanding, detectors, decision gate,
        # validated actions with rollback, structured log.
        engine = CleaningEngine(
            enable_imputation=impute_missing,
            enable_duplicate_removal=True,
            add_outlier_flags=add_outlier_flags,
            outlier_threshold=outlier_threshold,
            rules=rules,
        )
        df, engine_result = engine.run(df)

        report["cleaning_log"] = engine_result.model_dump(mode="json")
        report["inspection"] = engine_result.inspection.model_dump(mode="json")
        report["column_profiles"] = [
            p.model_dump(mode="json") for p in engine_result.column_profiles
        ]
        report["engine_decisions"] = [
            d.model_dump(mode="json") for d in engine_result.decisions
        ]
        # Additive engine verdicts (never rename/remove legacy keys).
        report["assessment"] = engine_result.assessment
        report["structural_findings"] = list(engine_result.structural_findings)
        report["run_validation"] = engine_result.run_validation
        if engine_result.information_loss_warnings:
            report["information_loss_warnings"] = list(
                engine_result.information_loss_warnings
            )
        if engine_result.errors:
            report["cleaning_warnings"] = list(engine_result.errors)

        if engine_result.blocked:
            # Structural corruption: dataset is returned UNCHANGED and the
            # run is BLOCKED. status flows through the existing non-success
            # handling of callers; nothing is silently "cleaned".
            report["final_shape"] = list(original_shape)
            _add_step(
                report,
                "cleaning_engine",
                blocked=True,
                blocking_findings=[
                    f for f in engine_result.structural_findings
                    if f.get("severity") == "block"
                ],
                assessment=engine_result.assessment,
            )
            return {
                "status": "blocked",
                "error": (
                    "Dataset blocked by structural integrity checks: "
                    + "; ".join(
                        f"{f.get('check')} on '{f.get('column')}'"
                        for f in engine_result.structural_findings
                        if f.get("severity") == "block"
                    )
                    + ". No cleaning was performed."
                ),
                "report": report,
                "preview": df.head(5).to_dict(orient="records"),
            }

        applied_actions = [
            {
                "action": e.action,
                "action_type": e.action,
                "column": e.column,
                "column_name": e.column,
                "rows_affected": e.rows_affected,
                "validated": bool(e.validation.passed if e.validation else False),
                "rolled_back": e.rolled_back,
                "applied": e.applied,
                "decision": e.decision_verdict,
                "decision_verdict": e.decision_verdict,
                "reason": "; ".join(e.reasons) if getattr(e, "reasons", None) else None,
                "status": "rolled_back" if e.rolled_back else ("applied" if e.applied else "skipped"),
                "before": e.before_state if hasattr(e, "before_state") else None,
                "after": e.after_state if hasattr(e, "after_state") else None,
                "evidence": {
                    "problem_type": getattr(e, "problem_type", None),
                    "detector": getattr(e, "detector", None),
                    "method": getattr(e, "method", None),
                    "confidence": getattr(e, "confidence", None),
                    "rows_affected": e.rows_affected,
                },
            }
            for e in engine_result.log
        ]
        # Top-level for DB persistence (_persist_cleaning) and API consumers
        report["applied_actions"] = applied_actions
        report["actions"] = applied_actions
        _add_step(
            report,
            "cleaning_engine",
            applied_actions=applied_actions,
            flagged_issues=len(engine_result.flagged_issues),
            success=engine_result.success,
        )

        # Legacy-compatible views derived from engine evidence.
        outlier_decisions = [
            d for d in engine_result.decisions
            if d.evidence.problem_type == "outliers"
        ]
        if add_outlier_flags:
            report["outliers"] = {
                d.evidence.column: {
                    "lower_bound": d.evidence.statistics.get("lower_bound"),
                    "upper_bound": d.evidence.statistics.get("upper_bound"),
                    "count": int(d.evidence.affected_count),
                    "percentage": round(
                        float(d.evidence.statistics.get("percentage", 0.0)), 2
                    ),
                    "action": "flag_only",
                }
                for d in outlier_decisions
                if d.evidence.column is not None
            }

        # Backward-compatible report view for deterministic type repairs.
        type_conversions = []
        for entry in engine_result.log:
            if entry.applied and entry.action == "TypeNormalizationAction":
                type_conversions.append({
                    "column": entry.column,
                    "converted_to": (
                        entry.after_state.get("dtype")
                        if isinstance(entry.after_state, dict)
                        else None
                    ),
                    "type": "numeric",
                    "source": "CleaningEngine",
                })
        if type_conversions:
            _add_step(report, "smart_type_conversion", conversions=type_conversions)

        # Post-engine missingness (imputation may legitimately have skipped
        # some columns; those gaps are documented in cleaning_log decisions).
        report["missing_values_after"] = {
            str(k): int(v) for k, v in df.isna().sum().items() if int(v) > 0
        }

        # 2. Optional feature engineering is explicitly outside the cleaning
        # engine. It creates new analytical columns; it never repairs existing
        # values and is recorded separately from the cleaning log.
        if add_features:
            feature_report = {"cleaning_steps": []}
            df = _feature_engineering(df, feature_report)
            if feature_report["cleaning_steps"]:
                report["feature_engineering"] = feature_report["cleaning_steps"]

        # 3. Optional dtype optimization is a non-semantic storage/preparation
        # phase after cleaning. It cannot influence evidence or decisions.
        if optimize_dtypes:
            prep_report = {"cleaning_steps": []}
            df = _optimize_dtypes(df, prep_report)
            if prep_report["cleaning_steps"]:
                report["post_cleaning_preparation"] = prep_report["cleaning_steps"]

        # Final audit.
        report["final_shape"] = list(df.shape)
        report["rows_removed"] = int(original_shape[0] - df.shape[0])
        report["columns_added"] = [
            c for c in df.columns if c not in original_cols
        ]
        report["remaining_nulls"] = {
            str(k): int(v) for k, v in df.isna().sum().items() if int(v) > 0
        }
        report["duplicate_rows_remaining"] = int(df.duplicated().sum())
        report["dtypes"] = {str(c): str(t) for c, t in df.dtypes.items()}

        save_path = output_path or df_path
        _save_dataframe(df, save_path)

        report["saved_to"] = save_path
        report["memory_usage_mb"] = round(
            float(df.memory_usage(deep=True).sum()) / (1024**2), 2
        )

        return {
            "status": "success",
            "report": report,
            "preview": df.head(5).to_dict(orient="records"),
        }

    except FileNotFoundError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Cleaning failed: {str(e)}"}


# ---------------------------------------------------------------------------
# Model-ready preprocessing
# ---------------------------------------------------------------------------

def prepare_model_data_tool(
    df_path: str,
    output_path: Optional[str] = None,
    target_column: Optional[str] = None,
    scale_numeric: bool = True,
    encoding: str = "onehot",
    encode_categorical: bool = True,
) -> dict:
    """
    Create a separate model-ready dataset.

    - low-cardinality categoricals -> one-hot encoding
    - high-cardinality categoricals -> frequency encoding (prevents thousands
      of dummy columns from Name/Ticket-like fields)
    - numeric features -> optional standardization
    - target, when supplied, is preserved and never scaled
    - the analysis dataset is never overwritten
    """
    try:
        df = _get_dataframe(df_path)

        if target_column and target_column not in df.columns:
            raise ValueError(
                f"Target column '{target_column}' not found. "
                f"Available columns: {list(df.columns)}"
            )

        if encoding not in {"onehot", "label"}:
            raise ValueError("encoding must be 'onehot' or 'label'")

        target = df[target_column].copy() if target_column else None
        features = (
            df.drop(columns=[target_column]).copy()
            if target_column
            else df.copy()
        )

        # Datetime -> decomposed numeric features.
        datetime_cols = features.select_dtypes(
            include=["datetime", "datetimetz"]
        ).columns.tolist()
        for col in datetime_cols:
            dt = pd.to_datetime(features[col], errors="coerce")
            features[f"{col}_year"] = dt.dt.year
            features[f"{col}_month"] = dt.dt.month
            features[f"{col}_day"] = dt.dt.day
            features.drop(columns=[col], inplace=True)

        numeric_cols = features.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = [
            c for c in features.columns if c not in numeric_cols
        ]

        # Defensive missing-value handling.
        for col in numeric_cols:
            values = pd.to_numeric(features[col], errors="coerce")
            median = values.median()
            features[col] = values.fillna(0 if pd.isna(median) else median)

        for col in categorical_cols:
            features[col] = (
                features[col].astype("string").fillna("Unknown").astype(str)
            )

        high_cardinality = []
        low_cardinality = []
        n_rows = max(len(features), 1)

        for col in categorical_cols:
            unique_count = int(features[col].nunique(dropna=True))
            unique_ratio = unique_count / n_rows

            # A small, interpretable one-hot vocabulary. Everything larger is
            # frequency encoded to avoid Name/Ticket explosions.
            if unique_count <= 30 and unique_ratio <= 0.10:
                low_cardinality.append(col)
            else:
                high_cardinality.append(col)

        if encode_categorical:
            if encoding == "onehot":
                if low_cardinality:
                    features = pd.get_dummies(
                        features,
                        columns=low_cardinality,
                        drop_first=False,
                        dtype=np.int8,
                    )

                for col in high_cardinality:
                    freq = features[col].value_counts(normalize=True)
                    features[f"{col}_Frequency"] = (
                        features[col].map(freq).fillna(0).astype(float)
                    )
                    features.drop(columns=[col], inplace=True)
            else:
                # Label encoding for all categorical columns. This mode is provided
                # for callers that explicitly request it; one-hot is the default.
                for col in categorical_cols:
                    categories = features[col].astype("category")
                    features[col] = categories.cat.codes.astype("int32")

        # Standardize continuous numeric columns only. Binary flags / one-hot
        # columns are left as 0/1.
        if scale_numeric:
            for col in features.columns:
                if not pd.api.types.is_numeric_dtype(features[col]):
                    continue

                values = pd.to_numeric(features[col], errors="coerce")
                unique = values.nunique(dropna=True)

                if unique <= 2:
                    continue

                mean = values.mean()
                std = values.std(ddof=0)
                if pd.notna(std) and std > 0:
                    features[col] = (values - mean) / std

        if target is not None:
            features[target_column] = target.reset_index(drop=True)

        features = features.reset_index(drop=True)

        output = output_path or os.path.join(
            os.path.dirname(df_path), "model_ready_dataset.pkl"
        )
        _save_dataframe(features, output)

        return {
            "status": "success",
            "saved_to": output,
            "shape": list(features.shape),
            "target_column": target_column,
            "encoding": encoding,
            "scaled_numeric": scale_numeric,
            "onehot_columns": low_cardinality,
            "frequency_encoded_columns": high_cardinality,
            "columns": list(features.columns),
            "preview": features.head(5).to_dict(orient="records"),
        }

    except Exception as e:
        return {"error": f"Model preprocessing failed: {str(e)}"}