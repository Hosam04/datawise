"""Shared, read-only column-classification helpers for the Statistical Engine.

These helpers are the single source of truth for the heuristics that decide
HOW a column may be analyzed statistically (e.g. whether a numeric-looking
column is really an ordinal categorical variable). Both the Statistical
Engine and the Cleaning Engine's detectors consume them; the historical
duplicated copies in backend/tools/outlier.py were consolidated here.
"""
import re
from typing import Optional

import numpy as np
import pandas as pd
import scipy.stats as stats


from backend.core.constants import ID_EXACT, ID_PATTERNS

# Ratio-based integer pseudo-id detection needs a meaningful sample; below
# this row count the ratio is noise (every small frame looks "all unique").
MIN_ROWS_FOR_ID_RATIO = 20
# A numeric column whose non-null values exceed this unique share AND are
# integers behaves like a row counter, not a measurement.
ID_RATIO_THRESHOLD = 0.98


def normalized_name(name) -> str:
    """Lowercase alphanumeric fingerprint of a column name."""
    return re.sub(r"[^a-z0-9]+", "", str(name).strip().lower())


def name_segments(name) -> set:
    """Split a column name into lowercase word segments."""
    return {s for s in re.split(r"[^a-z0-9]+", str(name).lower()) if s}


def _matches_id_name(col_name) -> bool:
    name = str(col_name).strip().lower()
    compact = re.sub(r"[^a-z0-9]+", "", name)
    if name in ID_EXACT or compact in ID_EXACT:
        return True
    if any(name.endswith(p) for p in ID_PATTERNS):
        return True
    # Compact suffix forms: passengerid, invoiceno, stockcode, hostid, ...
    if any(compact.endswith(p) for p in ("id", "uuid", "invoiceno", "stockcode")):
        if len(compact) >= 6:
            return True
    return False


def is_identifier_like(series: pd.Series, col_name) -> bool:
    """Identifier-like column detection for STATISTICAL analysis.

    Rules (in order):
      1. Name-based: exact vocabulary or id-like suffixes always match.
      2. Sequential integer counters (1,2,3,...) match at any size.
      3. Integer columns with near-perfect uniqueness on >= MIN_ROWS_FOR_ID_RATIO
         rows behave like row numbers.

    Float columns are NEVER ratio-flagged: continuous measurements legitimately
    have all-unique values (salaries, prices, sensor readings). This is the
    engine's refined rule; backend.utils.target_detection.is_identifier_column
    remains the project-wide (stricter) rule for pipeline filtering.
    """
    if _matches_id_name(col_name):
        return True

    if pd.api.types.is_integer_dtype(series):
        non_null = series.dropna()
        n = len(series)
        if len(non_null) > 1:
            sorted_vals = non_null.sort_values()
            diffs = sorted_vals.diff().dropna()
            if len(diffs) and bool((diffs == 1).all()):
                return True
        if (
            n >= MIN_ROWS_FOR_ID_RATIO
            and non_null.nunique() / n > ID_RATIO_THRESHOLD
        ):
            return True
    return False


def is_ordinal_categorical(series: pd.Series, col_name) -> bool:
    """Detect numeric columns that actually behave like ordinal categories.

    Canonical implementation (previously duplicated in tools/outlier.py and
    consumed by the Cleaning Engine's OutlierDetector): low-cardinality or
    rating/grade-like integer columns are NOT continuous measurements, so
    IQR/z-score style statistics are meaningless for them.
    """
    if not pd.api.types.is_numeric_dtype(series):
        return False
    unique = series.dropna().nunique()
    if unique <= 2:
        return True
    name = str(col_name).lower()
    ordinal_indicators = {
        "pclass", "class", "rating", "grade", "level", "tier", "rank",
    }
    if any(ind in name for ind in ordinal_indicators) and unique <= 10:
        return True
    if unique <= 5:
        try:
            vals = series.dropna()
            if len(vals) > 0 and all(float(v).is_integer() for v in vals):
                # Only treat as ordinal when the value range is small
                # (e.g. ratings 1-5). Large ranges with few integers
                # (e.g. 10,11,12,500) are continuous measurements with outliers.
                vmin, vmax = float(vals.min()), float(vals.max())
                if (vmax - vmin) <= 15:
                    return True
        except (ValueError, TypeError):
            pass
    return False


def is_string_like(series: pd.Series) -> bool:
    """pandas-3-safe check for textual dtypes (object OR str/string)."""
    return pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)


def is_boolean_like(series: pd.Series) -> bool:
    """True when a non-boolean-dtype column holds only True/False/missing.

    Object columns containing [True, False, None] lose their bool dtype in
    pandas; they are semantically boolean and must be analyzed as such.
    """
    if pd.api.types.is_bool_dtype(series):
        return True
    non_null = series.dropna()
    if non_null.empty or len(non_null) > 10_000:
        sample = non_null.head(10_000)
    else:
        sample = non_null
    if sample.empty:
        return False
    return all(isinstance(v, (bool, np.bool_)) for v in sample)


def classify_column_kind(series: pd.Series, col_name) -> str:
    """Classify a column into one statistical analysis kind.

    Returns one of: numeric | boolean | datetime | identifier | text |
    categorical. High-cardinality string columns are reported as text so we
    never compute frequency tables over near-unique identifier-like content,
    and identifiers are separated from genuine categorical variables.
    """
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_numeric_dtype(series):
        if is_identifier_like(series, col_name):
            return "identifier"
        return "numeric"
    if is_boolean_like(series):
        return "boolean"
    if is_string_like(series):
        if is_identifier_like(series, col_name):
            return "identifier"

        # Do not classify small categorical columns as free text merely
        # because their unique-value ratio is high. A ratio-only rule makes
        # tiny datasets (e.g. 5 rows / 5 categories) look like text.
        # High-cardinality text is identified using both scale and ratio,
        # while genuinely small categorical domains remain categorical.
        non_null = series.dropna().astype("string")
        unique_count = int(non_null.nunique(dropna=True))
        row_count = max(len(series), 1)
        unique_ratio = unique_count / row_count

        if unique_count > 20 and unique_ratio > 0.50:
            return "text"

        # Long strings with substantial cardinality are text even when the
        # dataset is not large enough for the absolute-cardinality rule.
        if unique_count >= 5 and unique_ratio > 0.25:
            lengths = non_null.str.len()
            if not lengths.empty and float(lengths.mean()) >= 40.0:
                return "text"

        return "categorical"
    # Fallback for exotic dtypes: attempt string coercion as categorical.
    return "categorical"


def json_safe_number(val) -> Optional[float]:
    """Convert numpy/pandas scalars to JSON-safe floats (NaN/Inf -> None)."""
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating, float)):
        f = float(val)
        return round(f, 6) if np.isfinite(f) else None
    if isinstance(val, (int,)):
        return val
    try:
        f = float(val)
        return round(f, 6) if np.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def strength_label(value: float) -> str:
    """Bucket |correlation| into qualitative strengths."""
    absolute = abs(value)
    if absolute >= 0.7:
        return "strong"
    if absolute >= 0.3:
        return "moderate"
    return "weak"


def correlation_strength_label(value: float) -> str:
    """Finer-grained strength buckets used by insight evidence."""
    absolute = abs(value)
    if absolute >= 0.8:
        return "very_strong"
    if absolute >= 0.6:
        return "strong"
    if absolute >= 0.4:
        return "moderate"
    if absolute >= 0.2:
        return "weak"
    return "negligible"


def correlation_p_value(r: float, n: int) -> Optional[float]:
    """Two-sided p-value for a Pearson correlation under t-distribution."""
    

    if n < 3 or not np.isfinite(r) or abs(r) >= 1.0:
        return 0.0 if (np.isfinite(r) and abs(r) >= 1.0 and n >= 2) else None
    try:
        t_stat = r * np.sqrt((n - 2) / (1 - r * r))
        return float(2 * (1 - stats.t.cdf(abs(t_stat), n - 2)))
    except Exception:
        return None


def sample_indices(indices, limit: int = 100) -> list:
    """Bounded, JSON-safe row-index sample for evidence payloads."""
    out = []
    for i in list(indices)[:limit]:
        try:
            out.append(int(i))
        except (TypeError, ValueError):
            continue
    return out


def entropy(labels_counts: pd.Series) -> float:
    """Shannon entropy (bits) of a value-count distribution."""
    prob = labels_counts / labels_counts.sum() if labels_counts.sum() else labels_counts
    prob = prob[prob > 0]
    if prob.empty:
        return 0.0
    return float(-np.sum(prob * np.log2(prob)))


def safe_series_to_numeric(series: pd.Series) -> pd.Series:
    """Numeric view of a series without ever mutating the source object."""
    return pd.to_numeric(series, errors="coerce")