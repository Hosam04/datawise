"""Base detector class and shared utilities for the DataWise Cleaning Engine.

All detectors must inherit from BaseDetector and follow the read-only contract.
"""
import re
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

import numpy as np
import pandas as pd

from backend.cleaning.contracts import (
    AGE_MAX_PLAUSIBLE,
    CO_MISSING_LIFT,
    CO_MISSING_MIN_SUPPORT,
    COMPONENT_MUTUAL_CORR_FLOOR,
    DERIVED_EXACT_COVERAGE,
    DERIVED_MIN_ROWS,
    DERIVED_OFFSET_SEARCH,
    DERIVED_SUSPECT_COVERAGE,
    MISSINGNESS_GROUP_SUPPORT,
    MISSINGNESS_RATE_GAP,
    NEAR_DUPLICATE_FLAG_SHARE,
    NEAR_DUPLICATE_HIGH_SHARE,
    SEPARATOR_FOLD_DOMINANCE,
    SEMANTIC_MIN_ROWS,
    SEMANTIC_NO_RELATIONSHIP_RHO,
    TEMPORAL_FUTURE_TOLERANCE_DAYS,
    TEMPORAL_MIN_YEAR,
    TYPE_ANOMALY_MIN_CONFLICTS,
    TYPE_DOMINANCE_RATIO,
    UNIT_MODE_GAP_ORDERS,
    UNIT_MODE_MIN_PER_MODE,
    UNIT_MODE_MIN_SHARE,
    ColumnProfile,
    Evidence,
    InspectionResult,
)
from backend.core.constants import (
    AGE_KEYWORDS,
    AGGREGATE_SUFFIXES,
    CONSTRAINT_PAIR_VOCAB,
    COUNT_KEYWORDS,
    DAYOFWEEK_PAIR_TOKENS,
    DAYOFWEEK_TOKENS,
    MISSING_STRING_TOKENS,
    PERCENTAGE_KEYWORDS,
    PLAUSIBILITY_AGE_MIN,
    PLAUSIBILITY_COUNT_HIGH,
    PROBABILITY_KEYWORDS,
    SUPPRESSION_TOKEN_CANDIDATES,
)

# Reuse the canonical ordinal-categorical heuristic from the Statistical Engine
from backend.statistics.helpers import is_ordinal_categorical as _is_ordinal_categorical

# Cap the row indices stored in evidence so logs stay bounded on large data.
_MAX_AFFECTED_ROW_SAMPLES = 100
# Outlier detection needs a minimum sample before quartiles are meaningful
_MIN_VALUES_FOR_OUTLIERS = 8
# Example values kept in type-anomaly evidence.
_MAX_EXAMPLES = 5

# English weekday names for day-of-week derivation checks.
_WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday",
                  "Friday", "Saturday", "Sunday"]

# Formatting-specific: pure numeric strings (no separators/symbols).
_NUMERIC_VALUE_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?$")

# Encoding artifact patterns (common UTF-8 misinterpreted as Latin-1)
_MOJIBAKE_PATTERNS = [
    re.compile(p) for p in (
        r"\xc3.", r"\xe2\x80\x9d", r"\xe2\x80\x99", r"\xc2 ", r"\xe2\x80\x9c", r"\xc3\xa2",
        r"\xc3\xa5", r"\xe4\xb8", r"\xc3\xa6",
    )
]
_HTML_ENTITY_RE = re.compile(r"&(?:amp|lt|gt|quot|nbsp|#\d+);")
_HTML_TAG_RE = re.compile(r"</?(?:br|p|div|span|b|i|a)[ >/]", re.IGNORECASE)


def _sample_indices(indices: List[int]) -> List[int]:
    """Cap row indices to keep evidence logs bounded."""
    return [int(i) for i in indices[:_MAX_AFFECTED_ROW_SAMPLES]]


def _finite_or_none(value) -> Optional[float]:
    try:
        val = float(value)
    except (TypeError, ValueError):
        return None
    return val if np.isfinite(val) else None


def _name_segments(name) -> set:
    """Split a column name into lowercase word segments."""
    return {s for s in re.split(r"[^a-z0-9]+", str(name).lower()) if s}


def _is_string_like(series: pd.Series) -> bool:
    """pandas-3-safe check for textual dtypes (object OR str/string)."""
    return pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)


def _name_has_keyword(segments: set, keyword: str) -> bool:
    """A keyword matches when ALL of its word tokens appear as segments."""
    tokens = {t for t in re.split(r"[^a-z0-9]+", keyword.lower()) if t}
    return bool(tokens) and tokens <= segments


def _jsonable(value):
    """Convert numpy/pandas scalars to JSON-serializable Python types."""
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        val = float(value)
        return val if np.isfinite(val) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return str(value)


class BaseDetector(ABC):
    """Base class for all detectors. Read-only by contract."""

    name: str = "base"
    problem_type: str = "missing_values"
    # When True, the engine re-runs this detector AFTER mutation actions have
    # committed, so annotation-style evidence (e.g. outlier fences) always
    # describes the final data state instead of going stale.
    rerun_after_actions: bool = False

    @abstractmethod
    def detect(
        self,
        df: pd.DataFrame,
        profiles: Dict[str, ColumnProfile],
        inspection: InspectionResult,
    ) -> List[Evidence]:
        """Analyze the DataFrame and return evidence. MUST NOT modify df."""