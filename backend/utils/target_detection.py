import re
import os
from typing import Dict, List, Any, Optional

import pandas as pd
import numpy as np

from backend.statistics.helpers import is_identifier_like

from backend.core.constants import (
    STRONG_TARGET_KEYWORDS,
    TARGET_KEYWORDS,
    NEGATIVE_KEYWORDS,
    ID_PATTERNS,
    ID_EXACT,
    FILENAME_STOP_WORDS,
    DATE_KEYWORDS,
    CATEGORICAL_TARGET_KEYWORDS,  
)

# Extended target keywords for common datasets
_EXTENDED_TARGET_KEYWORDS = [
    "charges", "cost", "price", "premium", "claim", "amount", "total",
    "payment", "fee", "expenditure", "spending", "revenue", "sales",
    "income", "salary", "wage", "earnings", "profit", "loss",
    "survived", "survival", "death", "mortality", "outcome", "result",
    "response", "label", "class", "category", "prediction", "forecast",
]

def _is_acceptable_target_dtype(df, col) -> bool:
    """FIX: Accept numeric OR low-cardinality categorical targets; reject free text/dates."""
    series = df[col]
    if pd.api.types.is_datetime64_any_dtype(series):
        return False
    if pd.api.types.is_numeric_dtype(series):
        return True
    ratio = series.nunique() / max(1, len(series))
    return ratio < 0.2

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_identifier_column(series: pd.Series, name: str) -> bool:
    """Project-wide identifier classifier shared by all analysis stages.

    The Statistical Engine owns the refined, dataset-agnostic heuristic; this
    compatibility wrapper keeps the historical public API used by DataAgent,
    Planner, Insights and Cleaning while guaranteeing identical decisions.
    """
    return bool(is_identifier_like(series, name))



def _is_engineered_flag_column(col_name: str) -> bool:
    """True for columns produced by the cleaning pipeline (e.g. *_OutlierFlag).

    These must never be selected as the analysis target.
    """
    lower = str(col_name).lower().replace(" ", "").replace("-", "_")
    if lower.endswith("_outlierflag") or lower.endswith("outlierflag"):
        return True
    if lower.endswith("_flag") or lower.endswith("flag"):
        # only when clearly derived (contains outlier / missing / invalid etc.)
        markers = ("outlier", "missing", "invalid", "anomaly", "duplicate", "suppression")
        return any(m in lower for m in markers)
    return False


def detect_target_variable(
    df: pd.DataFrame,
    profile: Optional[Dict[str, Any]] = None,
    filename_hints: Optional[List[str]] = None,
    filename: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Detect the target variable using a multi-stage generic approach.

    Returns a dict with guaranteed keys:
        - target_column   : str | None
        - confidence      : float (0.0 - 1.0)
        - method          : str
        - reason          : str
        - score           : int
        - candidates      : List[dict]
        - task_type       : "classification" | "regression" | "unknown"
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return _empty_result("empty_dataframe")

    date_columns = set()
    for col in df.columns:
        col_lower = str(col).lower()
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            date_columns.add(col)
        else:
            segments = re.split(r"[^a-z0-9]+", col_lower)
            if col_lower in DATE_KEYWORDS or any(seg in DATE_KEYWORDS for seg in segments):
                date_columns.add(col)

    # Auto-extract filename hints if filename provided but hints not given
    if filename_hints is None and filename is not None:
        filename_hints = _extract_filename_hint(filename)
    elif filename_hints is None:
        filename_hints = []

    # Build internal profile if not provided
    if profile is None:
        profile = _build_minimal_profile(df)

    # Include TARGET_KEYWORDS so common names like quality / score / rating are recognized
    all_target_keywords = list(dict.fromkeys(
        list(STRONG_TARGET_KEYWORDS) + list(TARGET_KEYWORDS) + _EXTENDED_TARGET_KEYWORDS
    ))
    all_strong_keywords = list(STRONG_TARGET_KEYWORDS) + _EXTENDED_TARGET_KEYWORDS[:5]

    # ------------------------------------------------------------------
    # Stage 1: Exact keyword match (highest confidence) — PREFER NUMERIC
    # ------------------------------------------------------------------
    for target_keyword in all_strong_keywords:
        for col in df.columns:
            str_col = str(col)
            if str_col in date_columns: 
                continue
            if target_keyword == str_col.lower():
                # FIX: accept low-cardinality categorical targets (e.g. string "label")
                if _is_acceptable_target_dtype(df, col):
                    return _build_result(
                        column=str_col,
                        confidence=0.95,
                        method="exact_match_numeric" if pd.api.types.is_numeric_dtype(df[col]) else "exact_match_categorical",
                        reason=f"exact_name_match:{target_keyword}",
                        score=10,
                        candidates=[],
                        df=df,
                    )

    # ------------------------------------------------------------------
    # Stage 1.5: Exact match for ALL known target keywords
    # ------------------------------------------------------------------
    # Extended keywords (e.g. "survived", "charges") must be checked as
    # exact column names before substring scoring. Otherwise a predictor such
    # as "Pclass" can incorrectly win because it contains the word "class".
    # Exact target names are substantially stronger evidence than semantic
    # substring matches.
    for target_keyword in all_target_keywords:
        for col in df.columns:
            str_col = str(col)
            if str_col in date_columns:
                continue
            if str_col.lower() == target_keyword.lower() and _is_acceptable_target_dtype(df, col):
                return _build_result(
                    column=str_col,
                    confidence=0.97 if target_keyword.lower() in {"survived", "target", "label", "outcome", "charges"} else 0.94,
                    method="exact_target_keyword",
                    reason=f"exact_target_keyword:{target_keyword}",
                    score=12,
                    candidates=[],
                    df=df,
                )

    # ------------------------------------------------------------------
    # Stage 2: Word-boundary keyword substring match — PREFER NUMERIC
    # Skip ultra-short keywords (e.g. "y") — they match suffixes like feature_y
    # and create false positives. Exact match already handled in Stage 1.
    # ------------------------------------------------------------------
    for target_keyword in all_strong_keywords:
        if len(target_keyword) <= 1:
            continue
        for col in df.columns:
            str_col = str(col)
            if str_col in date_columns:
                continue
            pattern = r"(?<![a-zA-Z0-9])" + re.escape(target_keyword) + r"(?![a-zA-Z0-9])"
            if re.search(pattern, str_col, re.IGNORECASE):
                if pd.api.types.is_numeric_dtype(df[col]):
                    return _build_result(
                        column=str_col,
                        confidence=0.90,
                        method="keyword_match_numeric",
                        reason=f"keyword_match_numeric:{target_keyword}",
                        score=8,
                        candidates=[],
                        df=df,
                    )

    numeric_keyword_col = None
    for kw in all_target_keywords:
        if len(kw) <= 1:
            continue
        for col in df.columns:
            if str(col) in date_columns:
                continue
            if pd.api.types.is_numeric_dtype(df[col]) and re.search(
                r"(?<![a-zA-Z0-9])" + re.escape(kw) + r"(?![a-zA-Z0-9])", str(col), re.IGNORECASE
            ):
                numeric_keyword_col = str(col)
                break
        if numeric_keyword_col:
            break

    if numeric_keyword_col is None:
        for kw in CATEGORICAL_TARGET_KEYWORDS:
            for col in df.columns:
                str_col = str(col)
                if str_col in date_columns:
                    continue
                if (
                    not pd.api.types.is_numeric_dtype(df[col])
                    and _is_acceptable_target_dtype(df, col)
                    and re.search(r"(?<![a-zA-Z0-9])" + re.escape(kw) + r"(?![a-zA-Z0-9])", str_col, re.IGNORECASE)
                ):
                    return _build_result(
                        column=str_col,
                        confidence=0.90,
                        method="keyword_match_categorical",
                        reason=f"keyword_match_categorical:{kw}",
                        score=8,
                        candidates=[],
                        df=df,
                    )

    for kw in CATEGORICAL_TARGET_KEYWORDS:
        for col in df.columns:
            if col in date_columns:
                continue
            col_lower = str(col).lower()
            if re.search(r"(?<![a-zA-Z0-9])" + re.escape(kw) + r"(?![a-zA-Z0-9])", col_lower, re.IGNORECASE):
                if not pd.api.types.is_numeric_dtype(df[col]) and df[col].nunique() < 20:
                    return _build_result(
                        column=col,
                        confidence=0.90,
                        method="keyword_match_categorical",
                        reason=f"keyword_match_categorical:{kw}",
                        score=8,
                        candidates=[],
                        df=df,
                    )
    # ------------------------------------------------------------------
    # Stage 3: Filename + Last Column Match (GUARANTEED TARGET)
    # ------------------------------------------------------------------
    last_column = str(df.columns[-1]) if len(df.columns) > 0 else None
    if last_column and last_column in date_columns:
        last_column = None
    if last_column and _is_engineered_flag_column(last_column):
        last_column = None
    if last_column and filename_hints:
        col_lower = last_column.lower()
        for hint in filename_hints:
            if hint in col_lower:
                # REJECT if last column is free text
                if df[last_column].dtype == object and df[last_column].nunique() / len(df) > 0.05:
                    break  # Don't return text columns
                return _build_result(
                    column=last_column,
                    confidence=0.95,
                    method="filename_last_column_match",
                    reason=f"last_column + filename_hint({hint})",
                    score=99,
                    candidates=[],
                    df=df,
                )

    # ------------------------------------------------------------------
    # Stage 4: Score-based detection for all columns — STRONG NUMERIC BIAS
    # ------------------------------------------------------------------
    candidates = _score_target_candidates(df, profile, filename_hints, all_target_keywords)

    candidates = [c for c in candidates if c["column"] not in date_columns]

    if not candidates:
        return _empty_result("no_candidates")

    candidates.sort(key=lambda x: x["score"], reverse=True)
    best = candidates[0]

    if best["score"] < 3:
        # Fallback: highest variance numeric column
        return _variance_fallback(df, profile, candidates)

    confidence = _score_to_confidence(best["score"])

    return _build_result(
        column=best["column"],
        confidence=confidence,
        method="scored",
        reason=best["reason"],
        score=best["score"],
        candidates=candidates[:5],
        df=df,
    )

# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _build_result(
    column: str,
    confidence: float,
    method: str,
    reason: str,
    score: int,
    candidates: List[Dict],
    df: pd.DataFrame,
) -> Dict[str, Any]:
    """Build a standardized result dict."""
    series = df[column].dropna()
    is_numeric = pd.api.types.is_numeric_dtype(series)

    if is_numeric:
        task_type = (
            "classification"
            if series.nunique() <= 20
            else "regression"
        )
    else:
        # Categorical target
        task_type = "classification"

    return {
        "target_column": column,
        "confidence": confidence,
        "method": method,
        "reason": reason,
        "score": score,
        "candidates": candidates,
        "task_type": task_type,
        "is_numeric": is_numeric,
    }


def _empty_result(reason: str) -> Dict[str, Any]:
    """Return an empty result when no target can be detected."""
    return {
        "target_column": None,
        "confidence": 0.0,
        "method": "none",
        "reason": reason,
        "score": 0,
        "candidates": [],
        "task_type": "unknown",
        "is_numeric": False,
    }


def _score_to_confidence(score: int) -> float:
    """Convert integer score to float confidence."""
    if score >= 8:
        return 0.95
    elif score >= 5:
        return 0.85
    elif score >= 3:
        return 0.70
    elif score > 0:
        return 0.50
    return 0.0


def _extract_filename_hint(filename: str) -> List[str]:
    """Extract meaningful words from the dataset filename."""
    if not filename:
        return []

    name_without_ext = os.path.splitext(filename)[0]
    words = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)|\d+", name_without_ext)
    words = [w.lower() for w in words if len(w) > 2]

    for sep in ["_", "-", " ", "."]:
        if sep in name_without_ext:
            parts = [p.lower() for p in name_without_ext.split(sep) if len(p) > 2]
            words.extend(parts)

    return [w for w in set(words) if w not in FILENAME_STOP_WORDS and len(w) >= 3]


def _build_minimal_profile(df: pd.DataFrame) -> Dict[str, Any]:
    """Build a minimal profile when full profile is not available."""
    possible_id = set()
    for col in df.columns:
        series = df[col]
        if is_identifier_column(series, str(col)):
            possible_id.add(str(col))

    return {
        "possible_id_columns": list(possible_id),
        "possible_date_columns": [],
    }


def _score_target_candidates(
    df: pd.DataFrame,
    profile: Dict[str, Any],
    filename_hints: List[str],
    all_target_keywords: List[str],
) -> List[Dict[str, Any]]:
    """Score every column as a potential target."""
    candidates = []

    id_columns = set(profile.get("possible_id_columns", []))
    date_columns = set(profile.get("possible_date_columns", []))
    last_column = str(df.columns[-1]) if len(df.columns) > 0 else None

    for col_raw in df.columns:
        col = str(col_raw)
        if col in id_columns or col in date_columns:
            continue
        if _is_engineered_flag_column(col):
            continue

        series = df[col_raw]
        n_total = len(series)
        n_unique = series.nunique()
        n_missing = series.isna().sum()

        if n_total == 0:
            continue

        unique_ratio = n_unique / n_total
        missing_ratio = n_missing / n_total
        is_numeric = pd.api.types.is_numeric_dtype(series)
        is_text = series.dtype == object and unique_ratio >= 0.05

        col_lower = col.lower()
        score = 0
        reasons = []

        # === HEAVY PENALTY for free-text columns ===
        if is_text:
            score -= 15
            reasons.append("free_text_penalty")

        # Penalty: too many missing values
        if missing_ratio > 0.5:
            score -= 5
            reasons.append(f"high_missing({missing_ratio:.2%})")
            candidates.append({
                "column": col,
                "score": score,
                "reason": "; ".join(reasons),
            })
            continue

        # Check for negative keywords
        has_negative = any(kw in col_lower for kw in NEGATIVE_KEYWORDS)

        # Target keywords (only if no negative keyword present)
        if not has_negative:
            if any(kw == col_lower for kw in all_target_keywords):
                score += 5
                reasons.append("exact_target_keyword")
            else:
                # Substring / word-boundary match. Skip ultra-short keywords
                # (e.g. "y") — they match inside unrelated names like density.
                matched = False
                for kw in all_target_keywords:
                    if len(kw) <= 1:
                        continue
                    if kw == "class" and col_lower in {"pclass", "class_id", "classid"}:
                        continue
                    # Prefer word-boundary so "y" / short tokens do not fire
                    pattern = r"(?<![a-zA-Z0-9])" + re.escape(kw) + r"(?![a-zA-Z0-9])"
                    if re.search(pattern, col_lower, re.IGNORECASE):
                        matched = True
                        break
                    # Also allow longer keywords as plain substring (quality, outcome...)
                    if len(kw) >= 4 and kw in col_lower:
                        matched = True
                        break
                if matched:
                    score += 4
                    reasons.append("target_keyword")

        # FIX: semantic boost for categorical target columns
        if not is_numeric and not is_text:
            if any(kw in col_lower for kw in CATEGORICAL_TARGET_KEYWORDS):
                score += 6
                reasons.append("semantic_categorical_target")

        # Filename hint
        if filename_hints:
            for hint in filename_hints:
                if hint in col_lower:
                    score += 12
                    reasons.append(f"filename_hint({hint})")
                    break

        # Last column convention — MAJOR BOOST (only if numeric or low-cardinality categorical)
        if col == last_column:
            if is_numeric:
                score += 7
                reasons.append("last_column_numeric")
            elif unique_ratio < 0.05:
                score += 5
                reasons.append("last_column_categorical")
            else:
                score += 1
                reasons.append("last_column_text")

        # === STRONG NUMERIC BONUS ===
        if is_numeric:
            score += 3
            reasons.append("numeric_bonus")

        # Penalty: almost unique (likely ID that slipped through)
        # BUT: do NOT penalize last column if it has no negative keywords
        #      (it's likely a legitimate continuous target like 'charges')
        if unique_ratio > 0.95:
            if col == last_column and not has_negative:
                # Last column with no negative keywords = likely legitimate target
                score += 2  # Actually boost it instead of penalizing
                reasons.append("last_column_continuous")
            else:
                score -= 5
                reasons.append(f"near_unique({unique_ratio:.2%})")

        # Negative keyword penalty
        if has_negative:
            if col == last_column:
                score -= 1
            else:
                score -= 5
            reasons.append("negative_keyword")

        # Cardinality-based hints
        if is_numeric:
            if n_unique <= 2:
                score += 1
                reasons.append("binary")
            elif n_unique <= 20:
                score += 1
                reasons.append("low_cardinality")
            elif unique_ratio < 0.8:
                score += 1
                reasons.append("continuous")
        else:
            # Non-numeric: only reward low cardinality (categorical)
            if n_unique <= 2:
                score += 1
                reasons.append("categorical_binary")
            elif n_unique <= 10 and unique_ratio < 0.05:
                score += 1
                reasons.append("categorical_low_card")

        # Penalty: constant column
        if n_unique <= 1:
            score -= 10
            reasons.append("constant")

        candidates.append({
            "column": col,
            "score": score,
            "reason": "; ".join(reasons) if reasons else "no_strong_signals",
        })

    return candidates


def _variance_fallback(
    df: pd.DataFrame,
    profile: Dict[str, Any],
    candidates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """When no column scores high enough, pick the highest-variance numeric column."""
    id_columns = set(profile.get("possible_id_columns", []))
    numeric_cols = [
        c for c in df.select_dtypes(include=[np.number]).columns
        if str(c) not in id_columns
    ]

    variance_scores = []
    for col in numeric_cols:
        series = df[col].dropna()
        if len(series) < 2 or series.nunique() <= 1:
            continue
        zero_pct = (series == 0).sum() / len(series) if len(series) > 0 else 0
        if zero_pct > 0.95:
            continue
        cv = series.std() / series.mean() if series.mean() != 0 else series.std()
        variance_scores.append((str(col), cv, series.std()))

    if variance_scores:
        variance_scores.sort(key=lambda x: x[1], reverse=True)
        col = variance_scores[0][0]
        return _build_result(
            column=col,
            confidence=0.50,
            method="highest_variance_fallback",
            reason="No clear target detected; using highest-variance numeric column",
            score=2,
            candidates=[{"column": c[0], "score": 0, "reason": "variance_fallback"} for c in variance_scores[:3]],
            df=df,
        )

    # Absolute fallback: first non-id, non-text column
    for col in df.columns:
        if str(col) in id_columns:
            continue
        series = df[col]
        # Skip free text
        if series.dtype == object and series.nunique() / len(series) > 0.05:
            continue
        return _build_result(
            column=str(col),
            confidence=0.30,
            method="first_valid_fallback",
            reason="No suitable numeric target found; using first valid column",
            score=1,
            candidates=[],
            df=df,
        )

    return _empty_result("no_numeric_columns")


# ---------------------------------------------------------------------------
# Legacy Compatibility Helpers
# ---------------------------------------------------------------------------

def get_target_column(result: Dict[str, Any]) -> Optional[str]:
    """Safely extract the target column name from a detection result."""
    return result.get("target_column")


def has_target(result: Dict[str, Any]) -> bool:
    """Check if a valid target was detected."""
    return result.get("target_column") is not None and result.get("confidence", 0) > 0