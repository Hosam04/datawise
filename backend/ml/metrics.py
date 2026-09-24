"""Metrics computation and feature importance extraction for MLAnalyzer."""
import logging
from typing import List, Optional, Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, classification_report, precision_score, recall_score, f1_score, roc_auc_score,
    mean_squared_error, mean_absolute_error, r2_score,
    confusion_matrix
)
from sklearn.preprocessing import LabelEncoder

from backend.ml.schemas import MLMetrics, FeatureImportanceItem, ClassMetrics

logger = logging.getLogger("MLAnalyzer.metrics")


def _compute_classification_metrics(y_true, y_pred, y_proba=None, label_encoder=None) -> MLMetrics:
    metrics = MLMetrics()
    try:
        metrics.accuracy = round(float(accuracy_score(y_true, y_pred)), 4)
        metrics.precision = round(float(precision_score(y_true, y_pred, average="weighted", zero_division=0)), 4)
        metrics.recall = round(float(recall_score(y_true, y_pred, average="weighted", zero_division=0)), 4)
        metrics.f1 = round(float(f1_score(y_true, y_pred, average="weighted", zero_division=0)), 4)

        report_dict = classification_report(y_true, y_pred, output_dict=True, zero_division=0)
        per_class_metrics = {}

        classes = label_encoder.classes_ if label_encoder else np.unique(y_true).astype(str)

        for cls in classes:
            cls_str = str(cls)
            if cls_str in report_dict and isinstance(report_dict[cls_str], dict):
                per_class_metrics[cls_str] = ClassMetrics(
                    precision=round(report_dict[cls_str]['precision'], 4),
                    recall=round(report_dict[cls_str]['recall'], 4),
                    f1=round(report_dict[cls_str]['f1-score'], 4),
                    support=int(report_dict[cls_str]['support'])
                )

        metrics.per_class = per_class_metrics

        if y_proba is not None:
            try:
                n_classes = len(np.unique(y_true))
                if n_classes == 2:
                    metrics.auc_roc = round(float(roc_auc_score(y_true, y_proba[:, 1])), 4)
                else:
                    metrics.auc_roc = round(float(roc_auc_score(y_true, y_proba, multi_class="ovr", average="weighted")), 4)
            except Exception as auc_err:
                logger.warning(f"AUC-ROC calculation failed: {auc_err}")

    except Exception as e:
        logger.warning(f"Classification metrics failed: {e}")
    return metrics


def _compute_regression_metrics(y_true, y_pred) -> MLMetrics:
    metrics = MLMetrics()
    try:
        metrics.mse = round(float(mean_squared_error(y_true, y_pred)), 4)
        metrics.rmse = round(float(np.sqrt(metrics.mse)), 4)
        metrics.mae = round(float(mean_absolute_error(y_true, y_pred)), 4)
        metrics.r2 = round(float(r2_score(y_true, y_pred)), 4)
    except Exception as e:
        logger.warning(f"Regression metrics failed: {e}")
    return metrics


def _extract_feature_importance(model, feature_names: List[str], model_name: str) -> List[FeatureImportanceItem]:
    """Extract feature importance from trained model."""
    importances = []
    try:
        if hasattr(model, "feature_importances_"):
            raw = model.feature_importances_
        elif hasattr(model, "coef_"):
            raw = np.abs(model.coef_)
        else:
            return []

        if raw.ndim > 1:
            raw = raw.mean(axis=0)

        for name, val in zip(feature_names, raw):
            importances.append(FeatureImportanceItem(feature=name, importance=float(val)))

        importances.sort(key=lambda x: x.importance, reverse=True)
        return importances[:20]
    except Exception as e:
        logger.warning(f"Could not extract feature importance: {e}")
        return []