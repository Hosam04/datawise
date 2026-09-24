"""Data exploration tools for the DataWise toolkit.

Provides tools for getting dataset metadata, rows, and unique values.
"""
import os
import pandas as pd
import numpy as np
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from backend.tools.dataframe_utils import (
    _get_dataframe,
    _validate_column,
    _format_value,
    _row_to_dict,
    _df_to_records,
    _safe_memory_usage,
)

from backend.statistics import StatisticalEngine


@tool
def dataset_info(df_path: str) -> dict:
    """
    Get comprehensive metadata about the dataset.
    Use this FIRST before any analysis to understand structure.
    """
    try:
        file_size_mb = os.path.getsize(df_path) / (1024 * 1024)
        df = _get_dataframe(df_path)

        if df.empty:
            return {
                "warning": "Dataset is empty (0 rows)",
                "columns": list(df.columns),
                "columns_count": len(df.columns),
                "missing_values": {
                    "status": "No missing values found in any column"
                },
                "total_missing_count": 0,
            }

        is_large = file_size_mb > 512

        info = {
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "column_names": list(df.columns),
            "file_size_mb": round(file_size_mb, 2),
            "memory_usage_mb": _safe_memory_usage(df),
            "duplicate_rows": int(df.duplicated().sum()),
            "_note": (
                "Use get_column_stats for detailed column analysis. "
                "Never guess values."
            ),
        }

        info["data_types"] = {
            col: str(dtype)
            for col, dtype in df.dtypes.items()
        }

        # Missing values are always returned using one consistent structure.
        missing = df.isnull().sum()
        missing_cols = {col: int(c) for col, c in missing.items() if c > 0}
        
        if missing_cols:
            info["missing_values"] = {col: int(count) for col, count in missing_cols.items()}
            info["total_missing_count"] = int(sum(missing_cols.values()))
        else:
            info["missing_values"] = {"status": "No missing values found in any column"}
            info["total_missing_count"] = 0

        numeric = df.select_dtypes(
            include=[np.number]
        ).columns.tolist()

        categorical = df.select_dtypes(
            include=["object", "category", "string"]
        ).columns.tolist()

        datetime = df.select_dtypes(
            include=["datetime64", "datetime"]
        ).columns.tolist()

        bool_cols = df.select_dtypes(
            include=["bool"]
        ).columns.tolist()

        if numeric:
            info["numeric_columns"] = numeric
            if not is_large or len(numeric) <= 20:
                # Descriptive math delegated to the Statistical Engine.
                info["numeric_overview"] = {}
                for col in numeric:
                    summary = StatisticalEngine().describe_column(df[col], col)
                    info["numeric_overview"][col] = {
                        "min": _format_value(summary.min),
                        "max": _format_value(summary.max),
                        "mean": _format_value(summary.mean),
                        "std": _format_value(summary.std),
                    }

            else:
                info["numeric_overview"] = "Skipped (large file — use get_column_stats per column)"

        if categorical:
            info["categorical_columns"] = categorical

            if not is_large:
                info["categorical_overview"] = {
                    col: {
                        "unique_count": int(df[col].nunique()),
                        "top_value": (
                            str(df[col].mode()[0])
                            if not df[col].mode().empty
                            else None
                        ),
                        "sample_values": (
                            df[col]
                            .dropna()
                            .unique()[:5]
                            .tolist()
                        ),
                    }
                    for col in categorical[:5]
                }
            else:
                info["categorical_overview"] = (
                    "Skipped (large file — use get_unique_values per column)"
                )

        if datetime:
            info["datetime_columns"] = datetime

            info["date_range"] = {
                col: {
                    "min": str(df[col].min()),
                    "max": str(df[col].max()),
                }
                for col in datetime
            }

        if bool_cols:
            info["boolean_columns"] = bool_cols

        info["sample_row"] = (
            _row_to_dict(df.iloc[0])
            if len(df) > 0
            else None
        )

        if is_large:
            info["warning"] = (
                f"Large dataset ({file_size_mb:.0f} MB). "
                "Some aggregated stats were skipped to prevent memory issues. "
                "Query specific columns using get_column_stats instead."
            )

        return info

    except MemoryError as e:
        return {
            "error": str(e),
            "suggestion": (
                "Dataset too large for available RAM. "
                "Try reducing file size or increasing memory."
            ),
        }

    except (
        FileNotFoundError,
        TypeError,
        ValueError,
    ) as e:
        return {"error": str(e)}

    except Exception as e:
        return {
            "error": f"Failed to read dataset info: {str(e)}"
        }


@tool
def get_row(
    df_path: str,
    row_number: int,
    columns: Optional[List[str]] = None,
) -> dict:
    """
    Get a specific row by row number (starts from 1).
    Uses O(1) iloc indexing — optimal for in-memory DataFrames.
    Optional: specify columns to reduce payload size.
    """
    try:
        df = _get_dataframe(df_path)

        if df.empty:
            return {"error": "Dataset is empty"}

        index = row_number - 1

        if index < 0 or index >= len(df):
            return {
                "error": (
                    f"Row {row_number} out of range. "
                    f"Valid: 1-{len(df)}"
                )
            }

        if columns:
            missing = [
                c
                for c in columns
                if c not in df.columns
            ]

            if missing:
                return {
                    "error": (
                        f"Columns not found: {missing}. "
                        f"Available: {list(df.columns)}"
                    )
                }

            target_df = df[columns]
        else:
            target_df = df

        return {
            "row_number": row_number,
            "total_rows": len(df),
            "data": _row_to_dict(target_df.iloc[index]),
        }

    except FileNotFoundError as e:
        return {"error": str(e)}

    except Exception as e:
        return {
            "error": f"Failed to get row: {str(e)}"
        }


@tool
def get_rows_batch(
    df_path: str,
    start_row: int,
    end_row: int,
    columns: Optional[List[str]] = None,
) -> dict:
    """
    Get a range of rows efficiently (inclusive start, exclusive end).
    Much faster than calling get_row multiple times.
    """
    try:
        df = _get_dataframe(df_path)

        if df.empty:
            return {"error": "Dataset is empty"}

        start_idx = start_row - 1
        end_idx = end_row - 1

        if (
            start_idx < 0
            or end_idx > len(df)
            or start_idx >= end_idx
        ):
            return {
                "error": (
                    f"Invalid range. Valid: 1-{len(df)}, "
                    "start < end"
                )
            }

        if columns:
            missing = [
                c
                for c in columns
                if c not in df.columns
            ]

            if missing:
                return {
                    "error": (
                        f"Columns not found: {missing}. "
                        f"Available: {list(df.columns)}"
                    )
                }

            target_df = df[columns]
        else:
            target_df = df

        slice_df = target_df.iloc[
            start_idx:end_idx
        ]

        return {
            "start_row": start_row,
            "end_row": end_row,
            "total_rows": len(df),
            "returned_count": len(slice_df),
            "data": [
                _row_to_dict(row)
                for _, row in slice_df.iterrows()
            ],
        }

    except FileNotFoundError as e:
        return {"error": str(e)}

    except Exception as e:
        return {
            "error": f"Failed to get rows: {str(e)}"
        }


@tool
def get_unique_values(
    df_path: str,
    column: str,
    limit: int = 50,
    include_counts: bool = True,
    sort_by: str = "frequency",
    search: Optional[str] = None,
) -> dict:
    """
    Get unique values in a column.
    Args:
        limit: 1-100 (default 50)
        include_counts: include frequency counts (default True)
        sort_by: 'frequency' | 'value' | 'none'
        search: filter values containing this substring (case-insensitive)
    """
    try:
        df = _get_dataframe(df_path)
        _validate_column(df, column)

        limit = min(
            max(1, int(limit)),
            100,
        )

        col_data = df[column]
        total_unique = int(
            col_data.nunique()
        )
        non_null = int(
            col_data.notna().sum()
        )

        if total_unique > 100000:
            return {
                "column": column,
                "total_unique": total_unique,
                "warning": (
                    f"Column has {total_unique} unique values. "
                    "Use filter_rows or calculate_percentage "
                    "for specific lookups."
                ),
                "sample_values": [],
            }

        if include_counts:
            value_counts = col_data.value_counts(
                dropna=True
            )

            if search:
                search_lower = str(search).lower()

                mask = (
                    value_counts.index
                    .astype(str)
                    .str.lower()
                    .str.contains(
                        search_lower,
                        na=False,
                    )
                )

                value_counts = value_counts[mask]

            if sort_by == "value":
                value_counts = value_counts.sort_index()

            elif sort_by == "none":
                pass

            top_values = value_counts.head(limit)

            return {
                "column": column,
                "total_unique": total_unique,
                "non_null_rows": non_null,
                "returned_count": len(top_values),
                "search": search,
                "sort_by": sort_by,
                "values": [
                    {
                        "value": _format_value(k),
                        "count": int(v),
                        "pct": (
                            round(
                                v / non_null * 100,
                                2,
                            )
                            if non_null
                            else 0.0
                        ),
                    }
                    for k, v in top_values.items()
                ],
            }

        if search:
            search_lower = str(search).lower()

            all_values = (
                col_data
                .dropna()
                .astype(str)
            )

            mask = (
                all_values
                .str.lower()
                .str.contains(
                    search_lower,
                    na=False,
                )
            )

            filtered = all_values[mask].unique()

        else:
            filtered = (
                col_data
                .dropna()
                .unique()
            )

        if sort_by == "value":
            try:
                filtered = sorted(filtered)
            except TypeError:
                pass

        limited = filtered[:limit]

        return {
            "column": column,
            "total_unique": total_unique,
            "non_null_rows": non_null,
            "returned_count": len(limited),
            "search": search,
            "sort_by": sort_by,
            "values": [
                _format_value(v)
                for v in limited
            ],
        }

    except (
        FileNotFoundError,
        ValueError,
    ) as e:
        return {"error": str(e)}

    except Exception as e:
        return {
            "error": f"Failed to get unique values: {str(e)}"
        }