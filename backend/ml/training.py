"""Training and evaluation logic for MLAnalyzer.

Contains the main _train_and_evaluate function that orchestrates the full
training pipeline: preprocessing, model building, training, evaluation,
and feature importance extraction.
"""
import time
import logging
import re
from typing import Optional, Tuple, Any, Dict, List

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder, LabelEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import confusion_matrix

from backend.ml.schemas import MLResults, MLMetrics, FeatureImportanceItem, ClassMetrics
from backend.ml.model_registry import (
    _get_model_class, _is_model_available, _build_model_instance,
    ALLOWED_MODELS, MIN_ROWS_FOR_ML, NATIVE_CATEGORICAL_MODELS
)
from backend.ml.preprocessing import (
    _sample_if_needed, _detect_text_columns, _build_preprocessor,
    _detect_and_remove_leakage
)
from backend.ml.metrics import (
    _compute_classification_metrics, _compute_regression_metrics,
    _extract_feature_importance
)
from backend.core.constants import ID_EXACT, ID_PATTERNS

logger = logging.getLogger("MLAnalyzer.training")


def _train_and_evaluate(
    df: pd.DataFrame,
    target: str,
    model_name: str,
    problem_type: str,
    profile: Dict[str, Any]
) -> Tuple[Optional[MLResults], Optional[Any]]:
    """Train a single model and return results + trained model."""
    start_time = time.time()

    model_class = _get_model_class(model_name)
    if model_class is None:
        return None, None

    df = _sample_if_needed(df)
    df = df.dropna(subset=[target]).copy()
    df = _detect_and_remove_leakage(df, target)

    if len(df) < MIN_ROWS_FOR_ML:
        return MLResults(status="skipped", reason=f"Too few rows after dropping missing target: {len(df)}"), None

    y = df[target]
    target_lower = str(target).lower()
    feature_cols = []
    for c in df.columns:
        if c == target:
            continue
        c_lower = str(c).lower()
        # Exclude annotation columns derived from the target itself
        # (e.g. price_OutlierFlag when target is price) — pure leakage.
        if c_lower.endswith("_outlierflag") or c_lower.endswith("_outlier_flag"):
            base = (
                c_lower.replace("_outlierflag", "").replace("_outlier_flag", "")
            )
            if base == target_lower or target_lower in base or base in target_lower:
                continue
        if c_lower.startswith(target_lower) and (
            "flag" in c_lower or "outlier" in c_lower
        ):
            continue
        feature_cols.append(c)

    if not feature_cols:
        return MLResults(status="skipped", reason="No feature columns available."), None

    X = df[feature_cols].copy()

    # ------------------------------------------------------------------
    # Remove identifiers and raw high-cardinality source fields.
    # - Exact / pattern-based ID columns (PassengerId, row_id, ...)
    # - Near-unique numeric columns (unique ratio ~ 1.0)
    # - Raw text fields already represented by engineered features
    # ------------------------------------------------------------------
    drop_raw = []
    normalized_cols = {
        re.sub(r"[^a-z0-9]+", "", str(c).lower()): c for c in X.columns
    }

    def _is_identifier_name(col: str) -> bool:
        c = str(col).lower()
        c_compact = re.sub(r"[^a-z0-9]+", "", c)
        if c in ID_EXACT or c_compact in ID_EXACT:
            return True
        if any(c.endswith(p) for p in ID_PATTERNS):
            return True
        if any(c_compact.endswith(p) for p in ID_PATTERNS if p.isalnum()):
            return True
        # Also catch "passengerid", "ticketid" style names without underscore
        if c_compact.endswith("id") and c_compact != "id":
            # Avoid dropping legitimate short codes like "paid", "valid"
            if len(c_compact) >= 6:  # passengerid, customerid, ...
                return True
        if c_compact.endswith("number") and len(c_compact) >= 8:
            # ticketnumber, accountnumber — high-cardinality numeric IDs
            return True
        # Retail / booking transaction keys (often moderate cardinality because
        # one invoice has many line items — unique_ratio alone is not enough).
        transaction_tokens = (
            "invoice", "invoiceno", "stockcode", "stock_code",
            "hostid", "host_id", "listingid", "listing_id",
            "orderid", "order_id", "transactionid", "transaction_id",
        )
        if c_compact in transaction_tokens or any(
            t in c_compact for t in ("invoiceno", "stockcode", "hostid", "listingid", "orderid")
        ):
            return True
        return False

    for col in list(X.columns):
        norm = re.sub(r"[^a-z0-9]+", "", str(col).lower())
        series = X[col]
        n = max(len(X), 1)
        nunique = series.nunique(dropna=True)
        unique_ratio = nunique / n

        # 1) Name-based identifier detection
        if _is_identifier_name(col):
            drop_raw.append(col)
            continue

        # 2) Near-unique INTEGER columns are almost always IDs / sequence numbers.
        # Continuous floats (price, amount, measurements) legitimately have
        # unique_ratio ≈ 1.0 and must NOT be dropped — otherwise datasets that
        # only retain continuous features after leakage removal end up with
        # zero usable columns and ML status=failed/skipped.
        if pd.api.types.is_numeric_dtype(series) and unique_ratio > 0.90:
            non_null = series.dropna()
            if len(non_null) > 0:
                integer_like = (
                    pd.api.types.is_integer_dtype(series)
                    or bool((non_null % 1 == 0).all())
                )
            else:
                integer_like = False
            if integer_like:
                drop_raw.append(col)
                continue

        if pd.api.types.is_numeric_dtype(series):
            continue

        avg_len = (
            series.dropna().astype(str).str.len().mean()
            if series.notna().any()
            else 0
        )

        # Titanic-like raw fields with engineered replacements.
        if norm == "name" and "title" in normalized_cols:
            drop_raw.append(col)
            continue
        if norm == "ticket" and any(
            k in normalized_cols
            for k in ("ticketprefix", "ticketnumber", "ticketcount")
        ):
            drop_raw.append(col)
            continue

        # Generic near-unique long text is not a useful tabular categorical
        # feature. Keep short/low-cardinality categoricals.
        if unique_ratio > 0.50 and avg_len > 25:
            drop_raw.append(col)

    if drop_raw:
        # Deduplicate while preserving order
        seen = set()
        drop_raw = [c for c in drop_raw if not (c in seen or seen.add(c))]
        X = X.drop(columns=drop_raw)
        feature_cols = [c for c in X.columns]
        logger.info(
            "Dropped identifier / high-cardinality features from ML: %s",
            drop_raw,
        )

    if not feature_cols:
        return MLResults(status="skipped", reason="No usable feature columns after preprocessing."), None

    # Detect column types
    text_cols = _detect_text_columns(X, profile)
    numeric_cols = X.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = [c for c in X.columns if c not in numeric_cols and c not in text_cols]

    # ─── Target encoding ───
    # XGBoost classification requires labels to be consecutive integers.
    # Encode all XGBoost classification targets, including numeric labels
    # such as [1, 2] or [10, 20].
    label_encoder = None
    if problem_type in ("classification", "text_classification"):
        if model_name == "xgboost":
            label_encoder = LabelEncoder()
            y = label_encoder.fit_transform(pd.Series(y).astype(str))
            y = np.asarray(y)
        elif y.dtype == object or y.dtype.name == "string":
            label_encoder = LabelEncoder()
            y = label_encoder.fit_transform(y.astype(str))
            y = np.asarray(y)
        else:
            y = np.asarray(y)
    else:
        y = pd.to_numeric(y, errors="coerce").values
        valid_mask = ~np.isnan(y)
        X = X.iloc[valid_mask]
        y = y[valid_mask]

    if len(X) < MIN_ROWS_FOR_ML:
        return MLResults(status="skipped", reason=f"Too few valid rows: {len(X)}"), None

    # Single-class (constant) target is meaningless for a classifier.
    if problem_type in ("classification", "text_classification"):
        n_classes = len(np.unique(y))
        if n_classes < 2:
            return MLResults(
                status="skipped",
                reason="Only one class present in target; cannot train a classifier.",
            ), None

    # ─── CatBoost categorical cleanup ───
    # CatBoost receives the raw DataFrame, so categorical columns should
    # contain no NaN values and should be represented consistently as strings.
    if model_name in ("catboost", "catboost_regressor"):
        for col in categorical_cols:
            # Convert category/string columns to plain strings before filling;
            # pandas Categorical does not allow assigning a new category via
            # fillna("missing") unless that category is registered first.
            X[col] = X[col].astype("string").fillna("missing").astype(str)

    # ─── Train/test split with rare-class fallback ───
    if problem_type == "classification":
        try:
            X_train, X_test, y_train, y_test = train_test_split(
                X,
                y,
                test_size=0.2,
                stratify=y,
                random_state=42,
            )
        except ValueError as e:
            error_message = str(e)

            if "least populated class" in error_message.lower():
                logger.warning(
                    f"Stratified split failed because of rare classes: {e}. "
                    "Filtering classes with fewer than 2 samples."
                )

                class_counts = pd.Series(y).value_counts()
                min_samples = 2
                keep_classes = class_counts[class_counts >= min_samples].index
                mask = pd.Series(y).isin(keep_classes).to_numpy()

                logger.warning(
                    f"Keeping {len(keep_classes)} classes and removing "
                    f"{len(class_counts) - len(keep_classes)} classes with "
                    f"<{min_samples} samples."
                )

                # We need at least 2 classes and enough rows to train.
                if len(keep_classes) >= 2 and mask.sum() >= MIN_ROWS_FOR_ML:
                    X_filtered = X.iloc[mask].copy()
                    y_filtered = np.asarray(y)[mask]

                    try:
                        X_train, X_test, y_train, y_test = train_test_split(
                            X_filtered,
                            y_filtered,
                            test_size=0.2,
                            stratify=y_filtered,
                            random_state=42,
                        )
                    except ValueError as fallback_error:
                        # Last resort: if stratification still fails because
                        # of the requested test size, use an unstratified split.
                        logger.warning(
                            "Stratified fallback failed again: "
                            f"{fallback_error}. Using unstratified split."
                        )
                        X_train, X_test, y_train, y_test = train_test_split(
                            X_filtered,
                            y_filtered,
                            test_size=0.2,
                            random_state=42,
                        )

                    X = X_filtered
                    y = y_filtered
                else:
                    logger.error(
                        "Cannot train classification model: fewer than 2 "
                        "valid classes or too few rows after rare-class filtering."
                    )
                    return MLResults(
                        status="failed",
                        reason=(
                            "Cannot perform stratified split: fewer than 2 "
                            "valid classes after filtering."
                        ),
                    ), None
            else:
                logger.warning(f"Train/test split failed: {e}")
                return MLResults(
                    status="failed",
                    reason=f"Train/test split failed: {e}",
                ), None
        except Exception as e:
            logger.warning(f"Train/test split failed: {e}")
            return MLResults(
                status="failed",
                reason=f"Train/test split failed: {e}",
            ), None
    else:
        try:
            X_train, X_test, y_train, y_test = train_test_split(
                X,
                y,
                test_size=0.2,
                random_state=42,
            )
        except Exception as e:
            logger.warning(f"Train/test split failed: {e}")
            return MLResults(
                status="failed",
                reason=f"Train/test split failed: {e}",
            ), None

    # Build preprocessor
    preprocessor = _build_preprocessor(X_train, feature_cols, text_cols, categorical_cols, numeric_cols, model_name)

    # Build model
    model = _build_model_instance(model_name, model_class, X_train, categorical_cols)

    # Train
    try:
        if model_name == "tfidf_logistic_regression" and preprocessor is not None:
            X_train_text = X_train[text_cols[0]].fillna("").astype(str)
            X_test_text = X_test[text_cols[0]].fillna("").astype(str)
            X_train_vec = preprocessor.fit_transform(X_train_text)
            X_test_vec = preprocessor.transform(X_test_text)
            model.fit(X_train_vec, y_train)
            y_pred = model.predict(X_test_vec)
            y_proba = model.predict_proba(X_test_vec) if hasattr(model, "predict_proba") else None
            feature_names = preprocessor.get_feature_names_out().tolist()

        elif preprocessor is not None:
            pipeline = Pipeline([("preprocessor", preprocessor), ("model", model)])
            pipeline.fit(X_train, y_train)
            y_pred = pipeline.predict(X_test)
            y_proba = pipeline.predict_proba(X_test) if hasattr(pipeline, "predict_proba") else None
            try:
                feature_names = preprocessor.get_feature_names_out().tolist()
            except Exception:
                feature_names = list(X_train.columns)
            model = pipeline.named_steps["model"]

        else:
            # No preprocessing needed (CatBoost, LightGBM with raw DataFrame)
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            y_proba = model.predict_proba(X_test) if hasattr(model, "predict_proba") else None
            feature_names = list(X_train.columns)

    except Exception as e:
        logger.error(f"Training failed for {model_name}: {e}")
        return MLResults(status="failed", reason=f"Training failed: {e}"), None

    # Evaluate
    if problem_type in ("classification", "text_classification"):
        metrics = _compute_classification_metrics(y_test, y_pred, y_proba, label_encoder)
        cm = confusion_matrix(y_test, y_pred)
        confusion = {
            "matrix": cm.tolist(),
            "labels": label_encoder.classes_.tolist() if label_encoder else np.unique(y_test).tolist()
        }
        actual_vs_predicted = None
        residuals = None
    else:
        metrics = _compute_regression_metrics(y_test, y_pred)
        confusion = None
        actual_vs_predicted = [{"actual": float(a), "predicted": float(p)} for a, p in zip(y_test[:500], y_pred[:500])]
        residuals = (y_test - y_pred).tolist()[:500]

    # Feature importance
    feature_importance = _extract_feature_importance(model, feature_names, model_name)
    training_time = round(time.time() - start_time, 2)

    results = MLResults(
        status="success",
        problem_type=problem_type,
        selected_model=model_name,
        metrics=metrics,
        feature_importance=feature_importance,
        confusion_matrix=confusion,
        actual_vs_predicted=actual_vs_predicted,
        residuals=residuals,
        training_time_sec=training_time,
        rows_used=len(df),
    )
    return results, model