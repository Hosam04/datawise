"""Constants for the Insights Agent."""
# FIX: Human-readable labels for insight types (used by _build_summary)
TYPE_LABELS = {
    "group_difference": "group differences",
    "feature_importance": "key predictors",
    "interaction": "subgroup effects",
    "risk_segment": "risk segments",
    "outlier": "outlier patterns",
    "correlation": "correlations",
    "segment": "segment gaps",
    "distribution": "distribution shapes",
    "data_quality": "data-quality notes",
    "target_summary": "target overview",
    "model_performance": "model performance",
}

# Keywords for leakage detection in ML feature importance
LEAKAGE_KEYWORDS = ("confidence", "prob", "score", "likelihood", "certainty")