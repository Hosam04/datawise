"""Statistical outlier EVIDENCE (read-only).

This module computes IQR / z-score / robust-MAD evidence for numeric columns.
It NEVER deletes, replaces, caps, winsorizes or otherwise modifies values.

Architectural rule:

    Statistical Engine  ->  outlier evidence  ->  Cleaning Engine
                                                    |
                                                decision
                                                    |
                                          treat OR keep

A statistically unusual value is NOT automatically an erroneous value.
"""
from typing import List, Optional

import numpy as np
import pandas as pd

from backend.statistics.contracts import (
    MAX_OUTLIER_ROW_SAMPLES,
    ColumnOutlierEvidence,
    OutlierEvidence,
)
from backend.statistics.helpers import (
    is_identifier_like,
    is_ordinal_categorical,
    json_safe_number,
    sample_indices,
)

VALID_METHODS = {"iqr", "zscore"}

# Outlier evidence needs a minimum sample before quartiles/sigma are
# meaningful (mirrors the Cleaning Engine detector threshold).
MIN_VALUES_FOR_OUTLIERS = 8


def _severity(count: int, total_rows: int) -> str:
    pct = count / max(total_rows, 1) * 100
    if pct >= 10:
        return "high"
    if pct >= 1:
        return "medium"
    return "low"


def _mad_extreme_share(values: pd.Series, mask: pd.Series) -> Optional[float]:
    """Share of flagged (IQR/z-score) values that are ALSO extreme under MAD.

    Purely evidential cross-check: agreement between two independent rules
    raises confidence; disagreement argues for 'suspicious', not 'invalid'.

    Returns P(MAD-extreme | flagged), i.e. among values already flagged by
    the primary rule, what fraction is also extreme under the robust MAD rule.
    """
    non_null = values.dropna()
    if non_null.empty:
        return None
    median = float(non_null.median())
    mad = float((non_null - median).abs().median())
    if not np.isfinite(mad) or mad <= 0:
        return None
    mad_mask = (values - median).abs() > 3.5 * 1.4826 * mad
    mad_mask = mad_mask.fillna(False)
    flagged = mask.fillna(False)
    n_flagged = int(flagged.sum())
    if n_flagged == 0:
        return 0.0
    # Among flagged values, what share is also MAD-extreme
    both = mad_mask[flagged]
    return round(float(both.mean()) if len(both) else 0.0, 4)


def column_outlier_evidence(
    series: pd.Series,
    col_name: str,
    method: str = "iqr",
    threshold: float = 1.5,
    respect_identifiers: bool = True,
) -> ColumnOutlierEvidence:
    """Outlier evidence for ONE column, including explicit skip reasons.

    Columns where outlier statistics would be meaningless (identifiers,
    ordinal categoricals, binary flags, constants, all-missing) are returned
    with analyzed=False and an explanatory note instead of being silently
    dropped.
    """
    method = method.lower().strip()
    if method not in VALID_METHODS:
        raise ValueError(f"Invalid outlier method '{method}'. Use {sorted(VALID_METHODS)}.")
    threshold = float(threshold)
    if threshold <= 0:
        raise ValueError("threshold must be greater than 0")

    item = ColumnOutlierEvidence(
        column=str(col_name), method=method, threshold=threshold
    )

    if pd.api.types.is_bool_dtype(series):
        item.analyzed = False
        item.note = "Boolean column — outlier statistics not meaningful"
        return item

    values = pd.to_numeric(series, errors="coerce")
    non_null = values.dropna()

    if respect_identifiers and is_identifier_like(series, col_name):
        item.analyzed = False
        item.note = "Identifier-like column — skipped"
        return item
    if is_ordinal_categorical(series, col_name):
        item.analyzed = False
        item.note = "Ordinal categorical variable — skipped"
        return item
    if len(non_null) == 0:
        item.analyzed = False
        item.note = "All values are null"
        return item
    if non_null.nunique() <= 2:
        item.analyzed = False
        item.note = "Binary/categorical numeric variable — skipped"
        return item
    if len(non_null) < MIN_VALUES_FOR_OUTLIERS:
        item.analyzed = False
        item.note = (
            f"Only {len(non_null)} observed value(s); at least "
            f"{MIN_VALUES_FOR_OUTLIERS} required for outlier statistics"
        )
        return item

    if method == "iqr":
        q1 = non_null.quantile(0.25)
        q3 = non_null.quantile(0.75)
        iqr = q3 - q1
        if not np.isfinite(iqr) or iqr == 0:
            item.analyzed = False
            item.note = "IQR is zero — no reliable IQR outlier rule"
            return item
        lower = q1 - threshold * iqr
        upper = q3 + threshold * iqr
        mask = (values < lower) | (values > upper)
        item.lower_bound = json_safe_number(lower)
        item.upper_bound = json_safe_number(upper)
    else:  # zscore
        mean = non_null.mean()
        std = non_null.std(ddof=1)
        if not np.isfinite(std) or std == 0:
            item.analyzed = False
            item.note = "Standard deviation is zero"
            return item
        z_scores = (values - mean) / std
        mask = z_scores.abs() > threshold
        item.mean = json_safe_number(mean)
        item.std = json_safe_number(std)

    mask = mask.fillna(False)
    count = int(mask.sum())
    item.count = count
    item.percentage = round(float(mask.mean() * 100), 2) if len(mask) else 0.0
    item.severity = _severity(count, len(values))
    item.mad_extreme_share = _mad_extreme_share(values, mask)

    if count:
        flagged = values[mask]
        item.sample_row_indices = sample_indices(
            values.index[mask].tolist(), MAX_OUTLIER_ROW_SAMPLES
        )
        item.min_outlier_value = json_safe_number(flagged.min())
        item.max_outlier_value = json_safe_number(flagged.max())
    return item


def outlier_evidence(
    df: pd.DataFrame,
    method: str = "iqr",
    threshold: float = 1.5,
    columns: Optional[List[str]] = None,
    respect_identifiers: bool = True,
) -> OutlierEvidence:
    """Dataset-level statistical outlier evidence (read-only)."""
    result = OutlierEvidence(method=method, threshold=float(threshold),
                             total_rows=int(len(df)))

    if df.empty or len(df.columns) == 0:
        return result

    numeric_cols = [
        c for c in df.select_dtypes(include=[np.number]).columns
        if not pd.api.types.is_bool_dtype(df[c])
    ]
    if columns:
        missing = [c for c in columns if c not in numeric_cols]
        if missing:
            raise KeyError(
                f"Columns not found in eligible numeric data: {missing}; "
                f"available: {numeric_cols}"
            )
        numeric_cols = [c for c in columns]

    result.columns_analyzed = [str(c) for c in numeric_cols]
    for col in numeric_cols:
        result.columns.append(
            column_outlier_evidence(
                df[col], col, method=method, threshold=threshold,
                respect_identifiers=respect_identifiers,
            )
        )
    return result


def five_number_summary(values) -> dict:
    """Five-number summary + IQR fences for one value collection.

    Uses linear-interpolation quantiles (numpy default) so consumers such as
    box plots match the frontend exactly. Read-only: accepts any iterable.
    """
    arr = np.asarray([float(v) for v in values], dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return {"q1": None, "median": None, "q3": None, "iqr": None,
                "lo_fence": None, "hi_fence": None}
    q1 = float(np.percentile(arr, 25))
    median = float(np.percentile(arr, 50))
    q3 = float(np.percentile(arr, 75))
    iqr = q3 - q1
    return {
        "q1": q1,
        "median": median,
        "q3": q3,
        "iqr": iqr,
        "lo_fence": q1 - 1.5 * iqr,
        "hi_fence": q3 + 1.5 * iqr,
    }
