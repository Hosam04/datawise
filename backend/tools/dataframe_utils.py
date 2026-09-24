"""Core DataFrame utilities for the DataWise toolkit.

Provides DataFrame loading/caching, memory management, JSON formatting,
column validation, and value parsing utilities.
"""
import os
import pandas as pd
import numpy as np
from typing import Any, Dict, List, Optional

_MAX_FILE_SIZE_MB = 2048
_MEMORY_WARNING_MB = 512
_df_cache: Dict[str, pd.DataFrame] = {}


def _get_dataframe(df_path: str) -> pd.DataFrame:
    """Read dataframe with file-size guard and LRU caching."""
    if not os.path.exists(df_path):
        raise FileNotFoundError(f"Dataset file not found: {df_path}")

    file_size_mb = os.path.getsize(df_path) / (1024 * 1024)

    if file_size_mb > _MAX_FILE_SIZE_MB:
        raise MemoryError(
            f"Dataset file too large ({file_size_mb:.0f} MB). "
            f"Max allowed: {_MAX_FILE_SIZE_MB} MB. Consider preprocessing."
        )

    if df_path not in _df_cache:
        if len(_df_cache) >= 10:
            _df_cache.pop(next(iter(_df_cache)))

        try:
            df = pd.read_pickle(df_path)
        except MemoryError as e:
            raise MemoryError(
                f"Not enough memory to load dataset ({file_size_mb:.0f} MB). "
                f"Free up RAM or reduce dataset size."
            ) from e

        if not isinstance(df, pd.DataFrame):
            raise TypeError(
                f"File at {df_path} is not a valid DataFrame"
            )

        _df_cache[df_path] = df

    return _df_cache[df_path]


def _safe_memory_usage(df: pd.DataFrame) -> float:
    """Calculate memory usage safely. Falls back to shallow estimate if deep fails."""
    try:
        return round(
            df.memory_usage(deep=True).sum() / (1024 ** 2),
            2,
        )
    except (MemoryError, OverflowError):
        shallow = df.memory_usage(deep=False).sum()
        return round(
            (shallow * 1.3) / (1024 ** 2),
            2,
        )


def _format_value(value: Any) -> Any:
    """Convert numpy/pandas types to JSON-safe Python types."""
    if pd.isna(value):
        return None

    if isinstance(value, (np.integer, np.int64, np.int32)):
        return int(value)

    if isinstance(value, (np.floating, np.float64, np.float32)):
        return float(value)

    if isinstance(value, pd.Timestamp):
        return str(value)

    return value


def _row_to_dict(row: pd.Series) -> Dict[str, Any]:
    """Convert a pandas Series to a dictionary with formatted values."""
    return {
        k: _format_value(v)
        for k, v in row.items()
    }


def _df_to_records(
    df: pd.DataFrame,
    max_rows: int = 20,
) -> List[Dict[str, Any]]:
    """Convert DataFrame to a list of dictionaries with formatted values."""
    return [
        {
            k: _format_value(v)
            for k, v in record.items()
        }
        for record in df.head(max_rows).to_dict(
            orient="records"
        )
    ]


def _validate_column(
    df: pd.DataFrame,
    column: str,
) -> None:
    """Validate that a column exists in the DataFrame."""
    if column not in df.columns:
        raise ValueError(
            f"Column '{column}' not found. "
            f"Available columns: {list(df.columns)}"
        )


def _parse_value_for_column(
    df: pd.DataFrame,
    column: str,
    value: Any,
) -> Any:
    """
    Parse the input value to match the column's dtype.
    Numeric columns get numeric conversion; others stay as string.
    """
    col_dtype = df[column].dtype

    if pd.api.types.is_numeric_dtype(col_dtype):
        try:
            if pd.api.types.is_integer_dtype(col_dtype):
                return int(value)

            return float(value)

        except (ValueError, TypeError):
            pass

    if pd.api.types.is_bool_dtype(col_dtype):
        if isinstance(value, str):
            return value.lower() in (
                "true",
                "1",
                "yes",
                "on",
            )

        return bool(value)

    return str(value)