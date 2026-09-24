"""Shared constants for the insight pipeline.

Centralizes thresholds and diversity caps to avoid duplication across
insight_tools.py, insight_extractor.py, and insight_selector.py.
"""

# Minimum thresholds for insight candidate generation
BASE_MIN_GROUP_DIFF_PCT = 10.0
BASE_MIN_CORRELATION = 0.15
BASE_MIN_FEATURE_IMPORTANCE = 0.15
BASE_MIN_SEGMENT_GAP = 8.0

# Diversity caps per insight type (max candidates of each type to keep)
DIVERSITY_CAPS = {
    "group_difference": 5,
    "correlation": 3,
    "outlier": 2,
    "segment": 3,
    "distribution": 2,
    "feature_importance": 3,
    "interaction": 3,
    "risk_segment": 3,
    "data_quality": 2,
}

# Selection limits
TYPE_PRIORITY = {
    "group_difference": 5,
    "risk_segment": 4,
    "interaction": 3,
    "outlier": 3,
    "segment": 3,
    "correlation": 2,
    "feature_importance": 2,
    "distribution": 2,
}

MAX_PER_TYPE = {
    "group_difference": 2,
    "risk_segment": 2,
    "segment": 2,
    "interaction": 2,
    "outlier": 1,
    "correlation": 1,
    "feature_importance": 3,
    "distribution": 2,
}

REDUNDANT_PAIRS = {
    ("group_difference", "risk_segment"),
    ("risk_segment", "group_difference"),
    ("group_difference", "segment"),
    ("segment", "group_difference"),
    ("risk_segment", "segment"),
    ("segment", "risk_segment"),
    ("correlation", "feature_importance"),
    ("feature_importance", "correlation"),
    ("group_difference", "interaction"),
    ("interaction", "group_difference"),
    # Prevent feature importance from duplicating group/segment differences for the same feature
    ("group_difference", "feature_importance"),
    ("feature_importance", "group_difference"),
    ("risk_segment", "feature_importance"),
    ("feature_importance", "risk_segment"),
    ("segment", "feature_importance"),
    ("feature_importance", "segment"),
}

MIN_COMPOSITE_SCORE = 0.05
SCORE_ESCALATION_MARGIN = 1.15
MAX_INSIGHTS = 8