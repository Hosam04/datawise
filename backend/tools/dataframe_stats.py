"""Statistical tools for the DataWise toolkit.

Provides tools for calculating percentages, filtering rows, and getting
detailed column statistics using the Statistical Engine.
"""
import os
import pandas as pd
import numpy as np
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from backend.statistics import StatisticalEngine
from backend.statistics.univariate import categorical_summary, text_summary

from backend.tools.dataframe_utils import (
    _get_dataframe,
    _validate_column,
    _parse_value_for_column,
    _format_value,
    _df_to_records,
)


@tool
def calculate_percentage(
    df_path: str,
    column: str,
    value: Any,
    operator: str = "==",
    case_sensitive: bool = False,
) -> dict:
    """
    Calculate percentage of rows matching a condition.
    Operators: ==, !=, contains, startswith, endswith
    case_sensitive: applies to text operators (default False)
    """
    try:
        df = _get_dataframe(df_path)
        _validate_column(df, column)

        total = len(df)

        if total == 0:
            return {
                "error": "Dataset is empty",
                "percentage": 0.0,
            }

        col = df[column]
        parsed_value = _parse_value_for_column(
            df,
            column,
            value,
        )

        if operator == "==":
            count = (col == parsed_value).sum()

        elif operator == "!=":
            count = (col != parsed_value).sum()

        elif operator == "contains":
            count = col.astype(str).str.contains(
                str(parsed_value),
                na=False,
                case=case_sensitive,
            ).sum()

        elif operator == "startswith":
            count = col.astype(str).str.startswith(
                str(parsed_value),
                na=False,
            )
            if not case_sensitive:
                count = (
                    col.astype(str)
                    .str.lower()
                    .str.startswith(
                        str(parsed_value).lower(),
                        na=False,
                    )
                )
            count = count.sum()

        elif operator == "endswith":
            count = col.astype(str).str.endswith(
                str(parsed_value),
                na=False,
            )
            if not case_sensitive:
                count = (
                    col.astype(str)
                    .str.lower()
                    .str.endswith(
                        str(parsed_value).lower(),
                        na=False,
                    )
                )
            count = count.sum()

        else:
            return {
                "error": (
                    f"Invalid operator '{operator}'. "
                    "Valid: ==, !=, contains, startswith, endswith"
                )
            }

        pct = (count / total) * 100

        return {
            "column": column,
            "value": value,
            "parsed_value": parsed_value,
            "operator": operator,
            "case_sensitive": case_sensitive,
            "count": int(count),
            "total": int(total),
            "percentage": round(float(pct), 2),
            "inverse_percentage": round(
                float(100 - pct),
                2,
            ),
        }

    except (
        FileNotFoundError,
        ValueError,
    ) as e:
        return {"error": str(e)}

    except Exception as e:
        return {
            "error": f"Failed to calculate percentage: {str(e)}"
        }


@tool
def filter_rows(
    df_path: str,
    column: str,
    value: Any,
    operator: str = "==",
    max_results: int = 20,
    case_sensitive: bool = False,
) -> dict:
    """
    Filter rows by column value with flexible operators.
    Operators: ==, !=, >, <, >=, <=, contains, startswith, endswith
    max_results: 1-100 (default 20)
    case_sensitive: applies to text operators (default False)
    """
    try:
        df = _get_dataframe(df_path)
        _validate_column(df, column)

        max_results = min(
            max(1, int(max_results)),
            100,
        )

        col = df[column]
        parsed_value = _parse_value_for_column(
            df,
            column,
            value,
        )

        if operator in (">", "<", ">=", "<="):
            if not pd.api.types.is_numeric_dtype(col.dtype):
                return {
                    "error": (
                        f"Operator '{operator}' requires a numeric column. "
                        f"Column '{column}' has type '{str(col.dtype)}'. "
                        "Use ==, !=, contains, startswith, or endswith instead."
                    )
                }

        if operator == "==":
            result = df[col == parsed_value]

        elif operator == "!=":
            result = df[col != parsed_value]

        elif operator == ">":
            result = df[col > parsed_value]

        elif operator == "<":
            result = df[col < parsed_value]

        elif operator == ">=":
            result = df[col >= parsed_value]

        elif operator == "<=":
            result = df[col <= parsed_value]

        elif operator == "contains":
            result = df[
                col.astype(str).str.contains(
                    str(parsed_value),
                    na=False,
                    case=case_sensitive,
                )
            ]

        elif operator == "startswith":
            mask = col.astype(str).str.startswith(
                str(parsed_value),
                na=False,
            )

            if not case_sensitive:
                mask = (
                    col.astype(str)
                    .str.lower()
                    .str.startswith(
                        str(parsed_value).lower(),
                        na=False,
                    )
                )

            result = df[mask]

        elif operator == "endswith":
            mask = col.astype(str).str.endswith(
                str(parsed_value),
                na=False,
            )

            if not case_sensitive:
                mask = (
                    col.astype(str)
                    .str.lower()
                    .str.endswith(
                        str(parsed_value).lower(),
                        na=False,
                    )
                )

            result = df[mask]

        else:
            return {
                "error": (
                    f"Invalid operator '{operator}'. "
                    "Valid: ==, !=, >, <, >=, <=, "
                    "contains, startswith, endswith"
                )
            }

        return {
            "column": column,
            "value": value,
            "parsed_value": parsed_value,
            "operator": operator,
            "case_sensitive": case_sensitive,
            "total_matches": len(result),
            "returned_rows": min(
                len(result),
                max_results,
            ),
            "preview": _df_to_records(
                result,
                max_results,
            ),
        }

    except (
        FileNotFoundError,
        ValueError,
    ) as e:
        return {"error": str(e)}

    except Exception as e:
        return {
            "error": f"Failed to filter rows: {str(e)}"
        }


@tool
def get_column_stats(
    df_path: str,
    column: str,
    top: int = 10,
) -> dict:
    """
    Get detailed statistics for a specific column.
    Works with numeric, categorical, datetime, and boolean columns.
    Statistics are computed by the read-only Statistical Engine.
    """
    try:
        df = _get_dataframe(df_path)
        _validate_column(df, column)

        col_data = df[column]
        dtype = str(col_data.dtype)
        total = len(df)

        # Single authoritative statistical implementation.
        summary = StatisticalEngine().describe_column(col_data, column)

        stats = {
            "column": column,
            "data_type": dtype,
            "total_rows": total,
            "non_null": summary.count,
            "null_count": summary.null_count,
            "null_pct": summary.null_pct,
        }

        if summary.count == 0:
            stats["warning"] = (
                "Column contains only null values"
            )
            return stats

        kind = getattr(summary, "kind", None)

        if kind == "numeric":
            stats.update(
                {
                    "min": _format_value(
                        summary.min
                    ),
                    "max": _format_value(
                        summary.max
                    ),
                    "mean": _format_value(
                        summary.mean
                    ),
                    "median": _format_value(
                        summary.median
                    ),
                    "std": _format_value(
                        summary.std
                    ),
                    "sum": _format_value(
                        summary.sum
                    ),
                    "quartiles": {
                        "q1": _format_value(
                            summary.q1
                        ),
                        "q2": _format_value(
                            summary.median
                        ),
                        "q3": _format_value(
                            summary.q3
                        ),
                    },
                    "zero_count": int(
                        summary.zeros_count
                    ),
                    "negative_count": int(
                        summary.negative_count
                    ),
                    "skewness": (
                        _format_value(
                            summary.skewness
                        )
                        if summary.count > 2
                        else None
                    ),
                    "kurtosis": (
                        _format_value(
                            summary.kurtosis
                        )
                        if summary.count > 3
                        else None
                    ),
                }
            )

        elif kind == "boolean":
            stats.update(
                {
                    "true_count": int(summary.true_count),
                    "false_count": int(summary.false_count),
                    "true_pct": round(summary.true_pct, 2),
                }
            )

        elif kind == "datetime":
            stats.update(
                {
                    "min": summary.min,
                    "max": summary.max,
                    "range_days": (
                        summary.span_days - 1
                        if summary.span_days is not None
                        else None
                    ),
                }
            )

            # Frequency table via the Statistical Engine's categorical view.
            cat_view = categorical_summary(col_data, top_n=min(int(top), 10))
            if cat_view.top_values:
                stats["most_frequent_dates"] = {
                    tv.value: tv.count for tv in cat_view.top_values
                }

        else:
            unique_count = int(summary.unique_count)

            top_n = min(
                max(1, int(top)),
                50,
            )

            if (
                unique_count > 10000
                and total > 100000
            ):
                stats["unique_count"] = unique_count
                stats["most_frequent"] = (
                    "Skipped (high cardinality — "
                    "use get_unique_values)"
                )
            else:
                cat_view = categorical_summary(col_data, top_n=top_n)
                stats["unique_count"] = unique_count
                stats["most_frequent"] = {
                    tv.value: tv.count for tv in cat_view.top_values
                }
                shown = sum(tv.count for tv in cat_view.top_values)
                stats["top_coverage_pct"] = (
                    round(shown / summary.count * 100, 2)
                    if summary.count
                    else 0.0
                )

            if (
                col_data.dtype == object
                or str(col_data.dtype) == "string"
            ):
                text_view = text_summary(col_data)
                if text_view.avg_length is not None:
                    stats["text_length"] = {
                        "min": int(text_view.min_length),
                        "max": int(text_view.max_length),
                        "mean": round(float(text_view.avg_length), 2),
                    }

        return stats

    except (
        FileNotFoundError,
        ValueError,
    ) as e:
        return {"error": str(e)}

    except Exception as e:
        return {
            "error": f"Failed to get column stats: {str(e)}"
        }