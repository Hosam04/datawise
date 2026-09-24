"""Statistics tool — THIN DELEGATE over the Statistical Engine.

The authoritative statistical implementation lives in backend/statistics.
This module keeps the historical tool contract (get_statistics_tool) and its
exact output schema, but every number is computed by StatisticalEngine.

Tool layer rule:

    Tool  ->  Engine  ->  Result
"""
import os
from typing import Any, Optional

import pandas as pd

from backend.statistics import StatisticalEngine


def _get_dataframe(df_path: str) -> pd.DataFrame:
    if not os.path.exists(df_path):
        raise FileNotFoundError(f"Dataset file not found: {df_path}")
    df = pd.read_pickle(df_path)
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"File at {df_path} is not a valid DataFrame")
    return df.copy()


def run_statistical_analysis(
    df: pd.DataFrame,
    columns: Optional[list] = None,
    include_percentiles: Optional[list] = None,
):
    """Analyze a DataFrame directly via the Statistical Engine.

    Returns the structured StatisticalResults contract used across DataWise
    state, APIs and agents. Read-only: df is never modified.
    """
    engine = StatisticalEngine()
    results = engine.analyze(df)
    return results


def get_statistics_tool(
    df_path: str,
    columns: Optional[list] = None,
    include_percentiles: Optional[list] = None,
) -> dict:
    """Historical tool contract. Delegates computation to StatisticalEngine."""
    try:
        df = _get_dataframe(df_path)

        if columns:
            missing = [c for c in columns if c not in df.columns]
            if missing:
                return {
                    "error": f"Columns not found: {missing}",
                    "available_columns": list(df.columns),
                }
            work_df = df[columns].copy()
        else:
            work_df = df

        results = run_statistical_analysis(work_df)

        # Build legacy-compatible view directly from StatisticalResults
        statistics = {}
        categorical_statistics = {}

        for col_name, summary in results.column_statistics.items():
            kind = getattr(summary, "kind", None)

            if kind == "numeric":
                percentiles = {
                    k: v for k, v in (summary.percentiles or {}).items()
                    if v is not None
                }
                entry = {
                    "count": summary.count,
                    "null_count": summary.null_count,
                    "null_pct": summary.null_pct,
                    "unique_count": summary.unique_count,
                    "min": summary.min,
                    "max": summary.max,
                    "mean": summary.mean,
                    "median": summary.median,
                    "std": summary.std,
                    "variance": summary.variance,
                    "skewness": summary.skewness,
                    "kurtosis": summary.kurtosis,
                    "range": summary.range,
                    "iqr": summary.iqr,
                }
                if percentiles:
                    entry["percentiles"] = percentiles
                if summary.count > 1:
                    entry["cv"] = summary.cv
                    entry["sem"] = summary.sem
                if summary.count == 0:
                    entry.pop("unique_count", None)
                    entry["note"] = "All values are null"
                statistics[col_name] = entry
            elif kind in ("categorical", "text", "identifier", "boolean"):
                # Historical behavior: everything non-numeric/non-datetime was
                # described by the categorical frequency view; datetimes were
                # skipped entirely. Text summaries carry structural stats only,
                # so their top_values list is intentionally empty.
                # BooleanSummary has no top_values / unique_count attributes.
                if kind == "boolean":
                    true_share = {
                        "value": "True",
                        "count": summary.true_count,
                        "percentage": summary.true_pct,
                    }
                    false_share = {
                        "value": "False",
                        "count": summary.false_count,
                        "percentage": round(100.0 - summary.true_pct, 2),
                    }
                    top_values = sorted(
                        [true_share, false_share],
                        key=lambda item: item["count"],
                        reverse=True,
                    )
                    unique_count = sum(
                        1 for item in (summary.true_count, summary.false_count) if item > 0
                    )
                elif kind == "text":
                    top_values = []
                    unique_count = getattr(summary, "unique_count", 0)
                else:
                    top_values = [
                        {"value": tv.value, "count": tv.count, "percentage": tv.percentage}
                        for tv in summary.top_values[:10]
                    ]
                    unique_count = summary.unique_count
                categorical_statistics[col_name] = {
                    "count": summary.count,
                    "null_count": summary.null_count,
                    "null_pct": summary.null_pct,
                    "unique_count": unique_count,
                    "top_values": top_values,
                }

        numeric_columns = [
            c for c, s in results.column_statistics.items()
            if getattr(s, "kind", None) == "numeric"
        ]

        summary_table: dict = {}
        if numeric_columns:
            try:
                rows = {}
                for stat_name, attr in (
                    ("mean", "mean"), ("median", "median"), ("std", "std"),
                    ("var", "variance"), ("skew", "skewness"), ("kurt", "kurtosis"),
                ):
                    row = {}
                    for col_name in numeric_columns:
                        value = getattr(results.column_statistics[col_name], attr)
                        if value is not None:
                            row[col_name] = round(float(value), 3)
                    rows[stat_name] = row
                summary_table = rows
            except Exception:
                summary_table = {}

        view = {
            "total_rows": results.dataset.rows,
            "numeric_columns_analyzed": numeric_columns,
            "categorical_columns_analyzed": [
                c for c in results.column_statistics
                if c in categorical_statistics
            ],
            "statistics": statistics,
            "categorical_statistics": categorical_statistics,
            "summary_table": summary_table,
        }

        if include_percentiles is not None:
            # Re-run numeric summaries when a non-default percentile grid is
            # explicitly requested (cheap: column-level only).
            engine = StatisticalEngine(percentiles=include_percentiles)
            results = engine.analyze(work_df)

            # Rebuild view with custom percentiles
            statistics = {}
            for col_name, summary in results.column_statistics.items():
                kind = getattr(summary, "kind", None)
                if kind == "numeric":
                    percentiles = {
                        k: v for k, v in (summary.percentiles or {}).items()
                        if v is not None
                    }
                    entry = {
                        "count": summary.count,
                        "null_count": summary.null_count,
                        "null_pct": summary.null_pct,
                        "unique_count": summary.unique_count,
                        "min": summary.min,
                        "max": summary.max,
                        "mean": summary.mean,
                        "median": summary.median,
                        "std": summary.std,
                        "variance": summary.variance,
                        "skewness": summary.skewness,
                        "kurtosis": summary.kurtosis,
                        "range": summary.range,
                        "iqr": summary.iqr,
                    }
                    if percentiles:
                        entry["percentiles"] = percentiles
                    if summary.count > 1:
                        entry["cv"] = summary.cv
                        entry["sem"] = summary.sem
                    if summary.count == 0:
                        entry.pop("unique_count", None)
                        entry["note"] = "All values are null"
                    statistics[col_name] = entry

            view = {
                "total_rows": results.dataset.rows,
                "numeric_columns_analyzed": numeric_columns,
                "categorical_columns_analyzed": [
                    c for c in results.column_statistics
                    if c in categorical_statistics
                ],
                "statistics": statistics,
                "categorical_statistics": categorical_statistics,
                "summary_table": summary_table,
            }
        return view

    except FileNotFoundError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Statistics calculation failed: {str(e)}"}
