"""Data preprocessing utilities for MLAnalyzer.

Contains sampling, text column detection, preprocessor building, and
target leakage detection/removal.
"""
import re
import logging
from typing import Any, Dict, List

import numpy as np
import pandas as pd

logger = logging.getLogger("MLAnalyzer.preprocessing")

MAX_ROWS_FOR_TRAINING = 50_000


def _sample_if_needed(df: pd.DataFrame, max_rows: int = MAX_ROWS_FOR_TRAINING) -> pd.DataFrame:
    if len(df) > max_rows:
        logger.info(f"Dataset has {len(df)} rows; sampling to {max_rows} for training.")
        return df.sample(n=max_rows, random_state=42)
    return df


def _detect_text_columns(df: pd.DataFrame, profile: Dict[str, Any]) -> List[str]:
    """Detect text columns that need special handling."""
    text_cols = []
    for col in df.columns:
        if df[col].dtype == object or str(df[col].dtype) == "string":
            unique_ratio = df[col].nunique() / max(len(df), 1)
            avg_len = df[col].dropna().astype(str).str.len().mean()
            if unique_ratio > 0.05 and avg_len > 20:
                text_cols.append(col)
    return text_cols


def _build_preprocessor(
    df: pd.DataFrame,
    feature_cols: List[str],
    text_cols: List[str],
    categorical_cols: List[str],
    numeric_cols: List[str],
    model_name: str
) -> Any:
    """Build sklearn preprocessor pipeline."""

    # CatBoost and LightGBM handle raw DataFrames natively
    if model_name in {"catboost", "catboost_regressor", "lightgbm", "lightgbm_regressor"}:
        return None

    transformers = []

    # Text columns → TF-IDF (only for text_classification models)
    if text_cols and model_name == "tfidf_logistic_regression":
        from sklearn.feature_extraction.text import TfidfVectorizer
        return TfidfVectorizer(max_features=5000, stop_words="english", ngram_range=(1, 2))

    # Numeric → Scale (only for models that need it)
    from backend.ml.model_registry import NEEDS_SCALING
    if numeric_cols:
        if model_name in NEEDS_SCALING:
            from sklearn.preprocessing import StandardScaler
            transformers.append(("num", StandardScaler(), numeric_cols))
        else:
            transformers.append(("num", "passthrough", numeric_cols))

    # Categorical → OneHot
    if categorical_cols:
        from sklearn.preprocessing import OneHotEncoder
        transformers.append(("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical_cols))

    if not transformers:
        return None

    from sklearn.compose import ColumnTransformer
    return ColumnTransformer(transformers, remainder="drop")


def _detect_and_remove_leakage(df: pd.DataFrame, target: str) -> pd.DataFrame:
    """Detect and drop features that leak target information.

    Catches:
    - exact duplicates of the target
    - name-based ground-truth / probability columns
    - semantic twins (e.g. is_canceled ↔ reservation_status)
    - near-perfect association (binary/categorical purity ≥ 0.98)
    """
    df_clean = df.copy()
    cols_to_drop = []
    target_lower = str(target).lower().replace(" ", "_")

    leakage_keywords = (
        "confidence", "gold", "probability", "likelihood",
        "target", "label", "ground_truth", "groundtruth",
    )

    # Semantic twin pairs: if target matches one side, drop columns matching the other.
    # Covers classic hotel/booking and status/flag leakage.
    SEMANTIC_TWINS = (
        (("cancel", "canceled", "cancelled", "is_canceled", "is_cancelled"),
         ("reservation_status", "booking_status", "status")),
        (("churn", "is_churn", "churned"),
         ("status", "customer_status", "account_status")),
        (("default", "is_default", "defaulted"),
         ("loan_status", "credit_status", "status")),
        (("survived", "is_survived", "survival"),
         ("status", "outcome", "result")),
    )

    def _name_hits(name: str, tokens) -> bool:
        n = name.lower().replace(" ", "_")
        for t in tokens:
            # whole-token / substring with boundaries so "status" ∉ "target"
            if re.search(rf"(^|_)({re.escape(t)})(_|$)", n):
                return True
            # also allow exact match
            if n == t:
                return True
        return False

    target_series = df_clean[target]
    # Sample for association checks on large frames
    n_rows = len(df_clean)
    sample_n = min(n_rows, 50_000)
    if sample_n < n_rows:
        sample_idx = df_clean.sample(n=sample_n, random_state=42).index
        tgt_sample = target_series.loc[sample_idx]
    else:
        sample_idx = df_clean.index
        tgt_sample = target_series

    for col in list(df_clean.columns):
        if col == target:
            continue
        col_lower = str(col).lower().replace(" ", "_")

        # 1) Name-based leakage keywords
        if target_lower in col_lower and any(kw in col_lower for kw in leakage_keywords):
            cols_to_drop.append(col)
            logger.warning(
                f"NAME-BASED LEAKAGE: Dropping '{col}' (target-derived keyword)."
            )
            continue

        # 2) Exact duplicate
        try:
            if df_clean[col].equals(target_series):
                cols_to_drop.append(col)
                logger.warning(
                    f"DUPLICATE LEAKAGE: Dropping '{col}' (exact duplicate of target)."
                )
                continue
        except Exception:
            pass

        # 3) Semantic twin (is_canceled ↔ reservation_status, etc.)
        # Use token-boundary checks so bare "status" does not match "target".
        twin_hit = False
        for side_a, side_b in SEMANTIC_TWINS:
            target_on_a = _name_hits(target_lower, side_a)
            target_on_b = _name_hits(target_lower, side_b)
            col_on_a = _name_hits(col_lower, side_a)
            col_on_b = _name_hits(col_lower, side_b)
            if (target_on_a and col_on_b) or (target_on_b and col_on_a):
                twin_hit = True
                break
        if twin_hit:
            cols_to_drop.append(col)
            logger.warning(
                f"SEMANTIC LEAKAGE: Dropping '{col}' (semantic twin of target '{target}')."
            )
            continue


        # 3b) Target-stem date/time leakage
        # e.g. target=reservation_status → drop reservation_status_date
        _date_suffixes = ("_date", "_time", "_timestamp", "_at", "_on", "_datetime")
        if (
            col_lower == f"{target_lower}_date"
            or col_lower == f"{target_lower}_time"
            or col_lower == f"{target_lower}_timestamp"
            or (
                col_lower.startswith(f"{target_lower}_")
                and any(col_lower.endswith(s) for s in _date_suffixes)
            )
        ):
            cols_to_drop.append(col)
            logger.warning(
                f"STATUS-DATE LEAKAGE: Dropping '{col}' "
                f"(date/time column derived from target '{target}')."
            )
            continue

        # 4) Definitional leakage — conservative:
        # Only binary/ternary FLAG-like features (nunique ≤ 3) with near-perfect
        # purity. Broader purity checks destroy legitimate synthetic / predictive
        # features in unit tests and real data.
        try:
            feat = df_clean.loc[sample_idx, col]
            pair = pd.DataFrame({"f": feat, "t": tgt_sample}).dropna()
            if len(pair) < 50:
                continue
            nunique_f = int(pair["f"].nunique())
            nunique_t = int(pair["t"].nunique())

            if 2 <= nunique_f <= 3 and nunique_t >= 2:
                ct = pd.crosstab(pair["f"], pair["t"])
                if ct.size == 0:
                    continue
                row_purity = (ct.max(axis=1) / ct.sum(axis=1).replace(0, np.nan)).dropna()
                weights = ct.sum(axis=1).reindex(row_purity.index).astype(float)
                if weights.sum() == 0:
                    continue
                avg_purity = float((row_purity * weights).sum() / weights.sum())
                if avg_purity >= 0.98:
                    cols_to_drop.append(col)
                    logger.warning(
                        f"ASSOCIATION LEAKAGE: Dropping '{col}' "
                        f"(flag-like feature, avg target purity = {avg_purity:.3f})."
                    )
                    continue

            # Numeric near-perfect linear dependence with numeric target
            # (r ≈ ±1). Requires many distinct values so discrete encodings
            # are handled by the flag rule above, not here.
            if (
                pd.api.types.is_numeric_dtype(feat)
                and pd.api.types.is_numeric_dtype(tgt_sample)
                and nunique_f > 20
                and nunique_t > 20
            ):
                corr = pair["f"].corr(pair["t"])
                if corr is not None and abs(float(corr)) >= 0.999:
                    cols_to_drop.append(col)
                    logger.warning(
                        f"CORRELATION LEAKAGE: Dropping '{col}' (|corr|={abs(corr):.4f})."
                    )
                    continue
        except Exception:
            continue

    if cols_to_drop:
        # unique preserve order
        seen = set()
        ordered = []
        for c in cols_to_drop:
            if c not in seen:
                seen.add(c)
                ordered.append(c)
        logger.warning(f"TARGET LEAKAGE DETECTED: Dropping columns: {ordered}")
        df_clean = df_clean.drop(columns=ordered, errors="ignore")

    return df_clean