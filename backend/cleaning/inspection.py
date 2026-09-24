"""Read-only dataset inspection and column understanding.

Nothing in this module modifies the DataFrame it receives; every function
only reads and returns structured profiles (backend.cleaning.contracts).

Reuses existing project infrastructure instead of duplicating it:
- backend.utils.target_detection.is_identifier_column (single source of truth)
- backend.core.constants (ID/date keyword lists)
"""
from typing import Any, Dict, Hashable, List, Optional
import re

import numpy as np
import pandas as pd

from backend.core.constants import DATE_KEYWORDS, ID_EXACT, ID_PATTERNS
from backend.utils.target_detection import is_identifier_column

from backend.cleaning.contracts import ColumnProfile, InspectionResult

# A column is "near constant" when a single value dominates this share of the
# observed values and cardinality stays tiny. Informational only.
_NEAR_CONSTANT_DOMINANT_SHARE = 0.98
_NEAR_CONSTANT_MAX_CARDINALITY = 5

# Text heuristics: free-text columns tend to be near-unique and verbose.
_TEXT_UNIQUE_RATIO = 0.5
_TEXT_MIN_AVG_LENGTH = 20


def inspect_dataframe(df: pd.DataFrame) -> InspectionResult:
    """Collect a structural overview of the dataset without modifying it."""
    rows = int(len(df))
    total_missing = int(df.isna().sum().sum()) if rows else 0

    constant_columns: List[str] = []
    near_constant_columns: List[str] = []
    for col in df.columns:
        non_null = df[col].dropna()
        if rows == 0 or non_null.empty:
            continue
        nunique = int(non_null.nunique())
        if nunique == 1:
            constant_columns.append(str(col))
            continue
        if nunique <= _NEAR_CONSTANT_MAX_CARDINALITY:
            top_share = float(non_null.value_counts().iloc[0] / len(non_null))
            if top_share >= _NEAR_CONSTANT_DOMINANT_SHARE:
                near_constant_columns.append(str(col))

    # Only exclude columns whose *name* is clearly an identifier (e.g. "id").
    # Do not use the statistical is_identifier_column heuristic here: that
    # flags high-cardinality integer measurements (income, score, …) as
    # identifiers, which would turn legitimate rows into false duplicates
    # when those columns are dropped from the comparison.
    id_cols = [c for c in df.columns if _name_is_id(str(c))]
    cols_for_dup = [c for c in df.columns if c not in id_cols]
    if rows and cols_for_dup:
        duplicate_count = int(df[cols_for_dup].duplicated().sum())
    else:
        duplicate_count = 0

    try:
        memory_mb = round(
            float(df.memory_usage(deep=True).sum()) / (1024**2), 4
        )
    except (MemoryError, OverflowError):
        shallow = df.memory_usage(deep=False).sum()
        memory_mb = round((float(shallow) * 1.3) / (1024**2), 4)

    return InspectionResult(
        rows=rows,
        column_count=int(len(df.columns)),
        column_names=[str(c) for c in df.columns],
        dtypes={str(c): str(t) for c, t in df.dtypes.items()},
        total_missing=total_missing,
        total_cells=rows * int(len(df.columns)),
        duplicate_row_count=duplicate_count,
        duplicate_ratio=round(duplicate_count / rows, 6) if rows else 0.0,
        constant_columns=constant_columns,
        near_constant_columns=near_constant_columns,
        memory_usage_mb=memory_mb,
    )


def build_column_profiles(df: pd.DataFrame) -> List[ColumnProfile]:
    """Build one semantic profile per column. Read-only."""
    return [_profile_column(df, col) for col in df.columns]


def profile_lookup(profiles: List[ColumnProfile]) -> Dict[str, ColumnProfile]:
    """Map profiles by column name for O(1) access during decisions."""
    return {p.name: p for p in profiles}


def _profile_column(df: pd.DataFrame, col: Hashable) -> ColumnProfile:
    series = df[col]
    name = str(col)
    rows = max(len(series), 1)
    non_null = series.dropna()
    n_non_null = int(len(non_null))
    missing_count = int(series.isna().sum())
    missing_ratio = round(missing_count / rows, 6)

    cardinality = int(non_null.nunique()) if n_non_null else 0
    unique_ratio = round(cardinality / n_non_null, 6) if n_non_null else 0.0

    dominant_share = 0.0
    if n_non_null:
        counts = non_null.value_counts()
        dominant_share = round(float(counts.iloc[0] / n_non_null), 6)

    semantic_type = _infer_semantic_type(series, name, cardinality, unique_ratio, non_null)

    # ── Phase 4: semantic enrichment (read-only) ──────────────────────
    subtype: Optional[str] = None
    quasi_identifier = False
    pattern_signature = None
    value_class_histogram = None
    value_profile = None

    if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
        value_profile = _numeric_value_profile(series)
        if (value_profile.get("sequential")
                and unique_ratio > 0.9
                and _name_is_id(name)):
            semantic_type = "identifier"
        name_tokens_num = {
            s for s in re.split(r"[^a-z0-9]+", name.lower()) if s
        }
        if name_tokens_num & _GEO_NAME_TOKENS:
            subtype = "geo_coordinate"
    elif pd.api.types.is_datetime64_any_dtype(series):
        value_profile = _datetime_value_profile(series)

    if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
        subtype, protected = _detect_string_semantics(non_null)
        if subtype is None:
            name_tokens = set(
                s for s in re.split(r"[^a-z0-9]+", name.lower()) if s
            )
            if name_tokens & _GEO_NAME_TOKENS:
                subtype = "geo_coordinate"
        elif protected:
            quasi_identifier = True
            semantic_type = "identifier"
        if semantic_type in ("categorical", "text", "identifier"):
            pattern_signature = _pattern_signature(non_null.head(5000))
            value_class_histogram = _value_class_histogram(non_null)

    top_values: List[Dict[str, Any]] = []
    if n_non_null:
        value_counts = non_null.value_counts().head(5)
        for value, count in value_counts.items():
            top_values.append({"value": _json_scalar(value), "count": int(count)})

    numeric_stats = None
    if semantic_type == "numeric" and n_non_null:
        numeric_stats = _numeric_stats(pd.to_numeric(series, errors="coerce"))

    return ColumnProfile(
        name=name,
        physical_dtype=str(series.dtype),
        semantic_type=semantic_type,
        cardinality=cardinality,
        unique_ratio=unique_ratio,
        missing_count=missing_count,
        missing_ratio=missing_ratio,
        constant=cardinality == 1,
        near_constant=(
            1 < cardinality <= _NEAR_CONSTANT_MAX_CARDINALITY
            and dominant_share >= _NEAR_CONSTANT_DOMINANT_SHARE
        ),
        dominant_share=dominant_share,
        is_possible_id=_is_possible_id(series, name),
        is_possible_date=_is_possible_date(series, name),
        numeric_stats=numeric_stats,
        top_values=top_values,
        semantic_subtype=subtype,
        quasi_identifier=quasi_identifier,
        pattern_signature=pattern_signature,
        value_class_histogram=value_class_histogram,
        value_profile=value_profile,
    )


def _infer_semantic_type(
    series: pd.Series,
    name: str,
    cardinality: int,
    unique_ratio: float,
    non_null: pd.Series,
) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_numeric_dtype(series):
        # Only NAME-based ID evidence demotes a numeric column to
        # identifier. Cardinality alone must not: legitimate continuous
        # measures are often near-unique, and treating them as identifiers
        # would wrongly suppress imputation/outlier handling.
        if _name_is_id(name):
            return "identifier"
        return "numeric"

    # Non-numeric dtypes: consider name/content semantics before labelling.
    lowered = name.lower()

    # Explicit name evidence marks a non-numeric column as an identifier
    # regardless of cardinality — identifiers must be protected from
    # imputation/merging/formatting even when values repeat.
    if _name_is_id(name):
        return "identifier"

    if _looks_like_text_date(series, lowered, non_null):
        return "datetime"

    # CSVs frequently arrive with numeric measures stored as object/string
    # because of a few missing cells or formatting artifacts.  Do not let the
    # physical dtype alone turn such a column into a categorical variable.
    # This is deliberately conservative: require essentially every observed
    # value to parse as a finite number.  Protected semantic patterns (UUID,
    # URL, email, ZIP, etc.) are promoted to identifier later by the semantic
    # enrichment pass.
    if len(non_null) >= 5:
        parsed_numeric = pd.to_numeric(
            non_null.astype("string").str.strip().str.replace(",", "", regex=False),
            errors="coerce",
        )
        numeric_parse_ratio = float(parsed_numeric.notna().mean())
        if numeric_parse_ratio >= 0.98 and bool(np.isfinite(
            parsed_numeric.dropna().to_numpy(dtype=float)
        ).all()):
            return "numeric"

    if (
        unique_ratio >= _TEXT_UNIQUE_RATIO
        and cardinality > 20
        and _avg_text_length(non_null) >= _TEXT_MIN_AVG_LENGTH
    ):
        return "text"

    return "categorical"


def _is_possible_id(series: pd.Series, name: str) -> bool:
    """Reuse the project-wide identifier heuristic (informational field)."""
    return bool(is_identifier_column(series, name))


def _name_is_id(name: str) -> bool:
    """Name-based identifier evidence, mirroring tools/cleaner.py rules."""
    lowered = name.lower()
    if lowered in ID_EXACT:
        return True
    if any(lowered.endswith(p) for p in ID_PATTERNS):
        return True
    return "identifier" in lowered


# ===========================================================================
# Phase 4: semantic value classification & pattern understanding
# ===========================================================================

# Ordered protected subtypes: >=90% sample match promotes the column to
# semantic_type="identifier" (never imputed / folded / converted).
_PROTECTED_SEMANTIC_PATTERNS = [
    ("uuid", re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"), 0.90),
    ("ip_address", re.compile(r"^(\d{1,3}\.){3}\d{1,3}$"), 0.90),
    ("email", re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$"), 0.90),
    ("url", re.compile(r"^https?://\S+$|^www\.\S+\.\S+", re.IGNORECASE), 0.90),
    ("phone", re.compile(r"^\+?[\d\s().-]{7,20}$"), 0.90),
    ("zip_code", re.compile(r"^\d{5}(-\d{4})?$"), 0.90),
]

# Informational-only subtypes (no protection semantics attached).
_INFO_SEMANTIC_PATTERNS = [
    ("currency_amount", re.compile(r"^[$€£¥]\s*[\d,]+(\.\d+)?$"), 0.90),
]

_GEO_NAME_TOKENS = {"latitude", "lat", "longitude", "lng", "lon"}


def _pattern_signature(sample_values) -> Optional[Dict[str, Any]]:
    """Dominant character-class fingerprint of a string sample.

    Character classes: a=alpha, d=digit, s=space; other chars verbatim.
    Runs are run-length encoded (e.g. zip '02139' -> 'd5',
    phone '(212) 555-0123' -> '(d3)sd3-d4').
    Returns {"signature": str, "share": float, "distinct_signatures": int}.
    """
    if not len(sample_values):
        return None

    def _rle(text: str) -> str:
        out = []
        prev_cls = None
        run = 0
        for ch in text:
            if ch.isalpha():
                cls = "a"
            elif ch.isdigit():
                cls = "d"
            elif ch.isspace():
                cls = "s"
            else:
                cls = ch
            if cls == prev_cls:
                run += 1
            else:
                if prev_cls is not None:
                    out.append(
                        prev_cls if run == 1 else f"{prev_cls}{run}"
                    )
                prev_cls = cls
                run = 1
        if prev_cls is not None:
            out.append(prev_cls if run == 1 else f"{prev_cls}{run}")
        return "".join(out)

    counts: Dict[str, int] = {}
    for raw in sample_values:
        key = _rle(str(raw))
        counts[key] = counts.get(key, 0) + 1
    total = sum(counts.values())
    top_sig, top_count = max(counts.items(), key=lambda kv: kv[1])
    return {
        "signature": top_sig,
        "share": round(top_count / total, 4),
        "distinct_signatures": len(counts),
    }


def classify_scalar(text: str) -> str:
    """Classify a scalar string as numeric / boolean / date / text."""
    t = str(text).strip()
    if not t:
        return "text"
    digits = sum(ch.isdigit() for ch in t)
    alnum = sum(ch.isalnum() for ch in t)
    if alnum and digits / alnum > 0.5 and _NUMERIC_RE.fullmatch(t):
        return "numeric"
    low = t.lower()
    if low in {"true", "false", "t", "f", "yes", "no", "y", "n"}:
        return "boolean"
    if ("-" in t or "/" in t or ":" in t) and pd.notna(
        pd.to_datetime(t, errors="coerce")
    ):
        return "date"
    return "text"


_NUMERIC_RE = re.compile(r"[+-]?(\d+(\.\d+)?|\.\d+)")


def _value_class_histogram(non_null: pd.Series) -> Dict[str, int]:
    hist: Dict[str, int] = {}
    for raw in non_null.head(5000):
        cls = classify_scalar(raw)
        hist[cls] = hist.get(cls, 0) + 1
    return hist


def _detect_string_semantics(
    non_null: pd.Series,
) -> tuple:
    """Return (subtype, quasi_identifier_or_protected)."""
    if non_null.empty:
        return None, False
    sample = non_null.head(5000).astype(str)
    total = max(len(sample), 1)

    for subtype, pattern, min_share in (
        list(_PROTECTED_SEMANTIC_PATTERNS) + list(_INFO_SEMANTIC_PATTERNS)
    ):
        matches = int(sample.str.match(pattern).sum())
        if total and matches / total >= min_share:
            protected = any(
                subtype == name for name, _, _ in _PROTECTED_SEMANTIC_PATTERNS
            )
            return subtype, protected
    return None, False


def _numeric_value_profile(series: pd.Series) -> Dict[str, Any]:
    values = pd.to_numeric(series, errors="coerce").dropna()
    profile: Dict[str, Any] = {}
    if values.empty:
        return profile
    finite = values[np.isfinite(values)]
    profile["integer_like"] = bool(
        len(finite) and np.all(np.isclose(finite % 1, 0))
    )
    profile["negative_count"] = int((finite < 0).sum())
    zero_share = float((finite == 0).mean()) if len(finite) else 0.0
    profile["zero_share"] = round(zero_share, 4)
    # Sequential-by-one detection (row-number style identifiers).
    ordered = values.sort_index()
    diffs = ordered.diff().dropna()
    profile["sequential"] = bool(
        len(diffs) >= 3 and (diffs == 1).mean() >= 0.95
    )
    return profile


def _datetime_value_profile(series: pd.Series) -> Dict[str, Any]:
    dt = pd.to_datetime(series, errors="coerce").dropna()
    if dt.empty:
        return {}
    span_days = float((dt.max() - dt.min()).total_seconds() / 86400.0)
    midnight_like = bool((dt.dt.time == pd.Timestamp("00:00:00").time()).all())
    return {
        "granularity": "date" if midnight_like else "datetime",
        "span_days": round(span_days, 3),
        "tz_aware": bool(dt.dt.tz is not None) if hasattr(dt.dt, "tz") else False,
    }


def _is_possible_date(series: pd.Series, name: str) -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    lowered = name.lower()
    segments = [s for s in lowered.replace("-", "_").split("_") if s]
    if lowered in DATE_KEYWORDS or any(seg in DATE_KEYWORDS for seg in segments):
        return not pd.api.types.is_numeric_dtype(series)
    return False


def _looks_like_text_date(series: pd.Series, lowered_name: str, non_null: pd.Series) -> bool:
    """A string column whose values parse as dates AND whose name hints at time."""
    if non_null.empty or not (
        lowered_name in DATE_KEYWORDS
        or any(seg in DATE_KEYWORDS for seg in lowered_name.replace("-", "_").split("_"))
    ):
        return False
    sample = non_null.astype(str).head(100)
    parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
    return bool(parsed.notna().mean() >= 0.85)


def _avg_text_length(non_null: pd.Series) -> float:
    lengths = non_null.astype(str).str.len()
    return float(lengths.mean()) if len(lengths) else 0.0


def _numeric_stats(numeric: pd.Series) -> Optional[Dict[str, float]]:
    values = numeric.dropna()
    if values.empty:
        return None
    q1 = float(values.quantile(0.25))
    q3 = float(values.quantile(0.75))
    stats: Dict[str, float] = {
        "count": float(len(values)),
        "mean": float(values.mean()),
        "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
        "min": float(values.min()),
        "q1": q1,
        "median": float(values.median()),
        "q3": q3,
        "max": float(values.max()),
        "iqr": q3 - q1,
    }
    for key, val in stats.items():
        if np.isnan(val) or np.isinf(val):
            stats[key] = 0.0
        else:
            stats[key] = round(val, 8)
    return stats


def _json_scalar(value) -> Any:
    """Convert numpy/pandas scalars to plain Python types for pydantic."""
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        val = float(value)
        return val if np.isfinite(val) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if hasattr(value, "isoformat"):
        return str(value)
    return value
