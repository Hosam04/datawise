"""Correlation tool — THIN DELEGATE over the Statistical Engine.

All correlation mathematics (method validation, eligibility filtering,
matrix computation, pair ranking/strength labels) lives in
backend/statistics.bivariate. This module preserves the historical tool
contract and output schema.
"""
import os
from typing import Optional

import pandas as pd

from backend.statistics import StatisticalEngine


def _get_dataframe(df_path: str) -> pd.DataFrame:
    if not os.path.exists(df_path):
        raise FileNotFoundError(f"Dataset file not found: {df_path}")
    df = pd.read_pickle(df_path)
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"File at {df_path} is not a valid DataFrame")
    return df.copy()


def get_correlation_tool(
    df_path: str,
    method: str = "spearman",
    min_variance: float = 0.0,
    top_pairs: Optional[int] = None,
) -> dict:
    """Historical tool contract. Delegates computation to StatisticalEngine."""
    try:
        df = _get_dataframe(df_path)
        method = method.lower().strip()
        if method not in {"pearson", "spearman", "kendall"}:
            return {
                "error": "Invalid correlation method. Use pearson, spearman, or kendall."
            }

        engine = StatisticalEngine(correlation_method=method)
        results = engine.analyze(df)

        # Build legacy-compatible view directly from StatisticalResults
        analysis = results.correlations

        if (
            analysis is None
            or len(analysis.columns_used) < 2
        ):
            # Historical error shape: numeric_columns_found reports the count of
            # usable (post-variance-filter) numeric columns.
            numeric_found = len(analysis.columns_used) if analysis else 0
            categorical_available = [
                c for c, s in results.column_statistics.items()
                if getattr(s, "kind", None) != "numeric"
            ]
            return {
                "error": "Insufficient numeric variance for correlation matrix.",
                "numeric_columns_found": numeric_found,
                "categorical_columns_available": categorical_available,
            }

        matrix = {
            outer: {
                inner: (round(float(value), 3) if value is not None else value)
                for inner, value in row.items()
            }
            for outer, row in analysis.matrix.items()
        }

        result = {
            "method": method,
            "columns_used": list(analysis.columns_used),
            "matrix": matrix,
            "note": analysis.note,
        }

        if top_pairs:
            limit = min(max(1, int(top_pairs)), 50)
            result["top_pairs"] = [
                {
                    "column_a": pair.column_a,
                    "column_b": pair.column_b,
                    "correlation": round(pair.correlation, 3),
                    "strength": pair.strength,
                }
                for pair in analysis.top_pairs[:limit]
            ]
        return result

    except FileNotFoundError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Correlation failed: {str(e)}"}
