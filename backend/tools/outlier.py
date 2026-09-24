"""Outlier tool — THIN DELEGATE over the Statistical Engine.

ARCHITECTURAL NOTE (outlier flow):

    Detection -> Evidence -> Decision -> Treatment

  - DETECTION/EVIDENCE: Statistical Engine (backend/statistics.outliers),
    read-only, never modifies data.
  - DECISION + TREATMENT: Cleaning Engine (backend.cleaning.detectors.
    OutlierDetector -> DecisionEngine -> OutlierFlagAction), the only
    component allowed to modify the dataset.

This module keeps the historical detect_outliers_tool contract. The
historical `add_flags=True` path wrote <column>_OutlierFlag columns from raw
statistics, bypassing cleaning decisions; it is preserved only as an
EXPLICIT caller-requested export and now emits a deprecation note pointing
at the Cleaning Engine's decision-gated OutlierFlagAction.
"""
import os
from typing import Optional

import pandas as pd

# Backwards-compatible re-export: the Cleaning Engine (and any external
# caller) previously imported this helper from here. The canonical
# implementation lives in backend.statistics.helpers.
from backend.statistics.helpers import is_ordinal_categorical as _is_ordinal_categorical  # noqa: F401
from backend.statistics import StatisticalEngine


def _get_dataframe(df_path: str) -> pd.DataFrame:
    if not os.path.exists(df_path):
        raise FileNotFoundError(f"Dataset file not found: {df_path}")
    df = pd.read_pickle(df_path)
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"File at {df_path} is not a valid DataFrame")
    return df.copy()


def detect_outliers_tool(
    df_path: str,
    method: str = "iqr",
    threshold: float = 1.5,
    columns: Optional[list] = None,
    return_outlier_rows: bool = False,
    max_outlier_rows: int = 20,
    add_flags: bool = False,
    output_path: Optional[str] = None,
) -> dict:
    """Historical tool contract. Delegates detection to StatisticalEngine."""
    try:
        df = _get_dataframe(df_path)

        method = method.lower().strip()
        if method not in {"iqr", "zscore"}:
            return {"error": f"Invalid method '{method}'. Use 'iqr' or 'zscore'."}

        engine = StatisticalEngine(
            outlier_method=method,
            outlier_threshold=float(threshold),
            include_correlations=False,
            include_distributions=False,
        )
        try:
            results = engine.analyze(df)
        except KeyError as exc:
            available = [
                c for c in df.select_dtypes(include=["number"]).columns
                if not pd.api.types.is_bool_dtype(df[c])
            ]
            return {
                "error": str(exc.args[0] if exc.args else exc),
                "available_numeric": available,
            }

        evidence = results.outlier_evidence

        # Build legacy-compatible summary directly from StatisticalResults
        summary = {}

        if evidence is not None:
            for item in evidence.columns:
                if not item.analyzed:
                    # تم استبعاده صراحةً (مثل bounded domains)
                    if item.note and "bounded" in item.note.lower():
                        summary[item.column] = {
                            "count": "N/A",
                            "percentage": "Skipped",
                            "note": "Excluded: bounded domain (e.g., confidence, probability, rating)",
                            "action": "none",
                        }
                    else:
                        summary[item.column] = {
                            "count": 0,
                            "percentage": 0.0,
                            "note": item.note or "Not analyzed",
                        }
                    continue

                if item.count == 0:
                    summary[item.column] = {
                        "count": 0,
                        "percentage": 0.0,
                        "note": "No outliers detected",
                    }
                    continue

                entry = {}
                if item.method == "iqr":
                    entry["method"] = "IQR"
                    entry["threshold_multiplier"] = item.threshold
                    entry["bounds"] = {
                        "lower": item.lower_bound,
                        "upper": item.upper_bound,
                    }
                else:
                    entry["method"] = "Z-Score"
                    entry["threshold"] = item.threshold
                    entry["mean"] = item.mean
                    entry["std"] = item.std

                entry["count"] = int(item.count)
                entry["percentage"] = round(float(item.percentage), 2)
                entry["action"] = "detect_only"
                summary[item.column] = dict(sorted(entry.items()))

        # Explicit caller-requested annotation export. This is NOT part of
        # the statistical engine (which is read-only); prefer the Cleaning
        # Engine's decision-gated OutlierFlagAction for dataset flagging.
        flags_added = False
        if add_flags:
            for item in evidence.columns:
                if not item.analyzed:
                    continue
                values = pd.to_numeric(df[item.column], errors="coerce")
                if method == "iqr":
                    mask = (
                        (values < item.lower_bound) | (values > item.upper_bound)
                        if item.lower_bound is not None and item.upper_bound is not None
                        else pd.Series(False, index=df.index)
                    )
                else:
                    mean, std = item.mean, item.std
                    mask = (
                        ((values - mean) / std).abs() > threshold
                        if mean is not None and std
                        else pd.Series(False, index=df.index)
                    )
                df[f"{item.column}_OutlierFlag"] = (
                    mask.fillna(False).astype("int8")
                )
            flags_added = True
            if output_path:
                parent = os.path.dirname(output_path)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                df.to_pickle(output_path)

        result = {
            "method": method,
            "total_rows": len(df),
            "columns_analyzed": list(evidence.columns_analyzed) if evidence else [],
            "summary": summary,
            "flags_added": flags_added,
            "saved_to": output_path if flags_added and output_path else None,
        }
        if flags_added:
            result["note"] = (
                "add_flags is deprecated for statistical use: dataset "
                "annotations should go through the Cleaning Engine's "
                "decision-gated OutlierFlagAction so treatment remains "
                "evidence-driven."
            )

        all_outlier_indices: set = set()
        if return_outlier_rows:
            for item in evidence.columns:
                all_outlier_indices.update(item.sample_row_indices)
            if all_outlier_indices:
                capped = min(max(1, int(max_outlier_rows)), 100)
                ordered = sorted(i for i in all_outlier_indices if i < len(df))
                outlier_df = df.iloc[ordered]
                result["outlier_rows"] = {
                    "total_unique_rows": len(all_outlier_indices),
                    "preview": outlier_df.head(capped).to_dict(orient="records"),
                }

        return result

    except FileNotFoundError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Outlier detection failed: {str(e)}"}
