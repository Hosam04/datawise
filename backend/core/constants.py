import os

SESSION_BASE_DIR = os.path.join("storage", "sessions")
DATASET_FILENAME = "dataset.csv"
REPORT_FILENAME = "final_report.pdf"
SUPPORTED_CHART_TYPES = ["bar", "scatter", "line", "pie", "heatmap", "box"]



###======================================================================================

"""
Centralized dataset analysis constants.
Import from here instead of redefining in every agent/tool.
"""


# ==================== TARGET DETECTION ====================
STRONG_TARGET_KEYWORDS = [
    "target", "label", "y", "outcome", "prediction",
    "response", "dependent", "ground_truth"
]

TARGET_KEYWORDS = [
    "target", "label", "outcome", "result", "prediction",
    "y", "response", "dependent", "output", "class", "minutes", "hours",
    "quality", "score", "rating",
]

# ==================== STRUCTURAL / NON-FEATURE COLUMNS ====================
NEGATIVE_KEYWORDS = [
    "id", "uuid", "index", "row", "key", "code", "identifier",
    "serial", "numbering", "sequence", "order",
    "date", "timestamp", "created", "updated", "modified",
    "name", "email", "phone", "address", "location", "coordinates",
    "description", "note", "comment", "text", "message", "content",
    "url", "path", "file", "link", "reference", "source",
    "image", "photo", "video", "audio", "document", "attachment",
    # Engineered / derived flags produced by cleaning pipeline — never targets
    "outlierflag", "outlier_flag", "outliers", "flag",
]

# ==================== ID COLUMN PATTERNS ====================
ID_PATTERNS = [
    # Prefer explicit id-like suffixes. Avoid bare "_num" — it matches
    # ordinal encodings such as education_num which are real features.
    "_id", "_uuid", "_key", "_code", "_no", "_seq",
    "id",  # also match suffix without underscore (passengerid, customerid)
]

ID_EXACT = [
    "id", "uuid", "index", "row_num", "row_id", "serial",
    "sequence", "record_id", "entry_id", "passengerid", "customerid",
    "userid", "accountid", "ticketnumber",
]

# ==================== DATE KEYWORDS ====================
DATE_KEYWORDS = [
    "date", "time", "timestamp", "datetime", "day", "month", "year",
    "hour", "minute", "second", "period", "epoch", "era", "calendar",
    "schedule", "deadline", "start", "end", "begin", "finish",
    "created", "updated", "modified", "published", "released",
    "birth", "death", "anniversary", "holiday", "event"
]

# ==================== FILENAME STOP WORDS ====================
FILENAME_STOP_WORDS = {
    "data", "dataset", "table", "file", "csv", "xlsx", "json",
    "export", "report", "backup", "copy", "new", "old", "final",
    "draft", "temp", "test"
}

# ==================== CATEGORICAL TARGET KEYWORDS ====================
CATEGORICAL_TARGET_KEYWORDS = [
    "sentiment", "satisfaction", "churn", "status", "severity",
    "diagnosis", "rating", "class", "category", "segment", "quality",
]

# ==================== CLEANING ENGINE VOCABULARIES ====================
"""
Name-based semantic vocabularies used by the Cleaning Engine detectors
(backend/cleaning). These are NAME signals only — never treated as proof
on their own; every detector combines them with value-level evidence.
"""

# Columns whose name suggests a percentage in [0, 100].
PERCENTAGE_KEYWORDS = [
    "percent", "percentage", "pct",
]

# Columns whose name suggests a probability in [0, 1].
PROBABILITY_KEYWORDS = [
    "probability", "prob_", "_prob", "likelihood",
]

# Columns whose name suggests a non-negative count.
COUNT_KEYWORDS = [
    "count", "qty", "quantity", "num_", "_num", "number_of",
    "total_count",
]

# Columns whose name suggests an age in [0, AGE_MAX_PLAUSIBLE].
AGE_KEYWORDS = ["age"]

# Ordered column-name pairs for cross-column constraint checks:
# (left_word, right_word) means left must be <= right.
CONSTRAINT_PAIR_VOCAB = [
    ("start", "end"),
    ("begin", "finish"),
    ("begin", "end"),
    ("from", "to"),
    ("min", "max"),
    ("lower", "upper"),
    ("first", "last"),
    ("earliest", "latest"),
    ("departure", "arrival"),
    ("checkin", "checkout"),
    ("check_in", "check_out"),
    ("opened", "closed"),
    ("created", "resolved"),
]

# Columns whose name suggests a monetary amount / rate that must be >= 0.
PRICE_KEYWORDS = [
    "price", "fare", "cost", "fee", "amount", "charge", "payment",
    "revenue", "salary", "wage", "adr", "avg_daily_rate", "daily_rate",
    "room_rate", "unit_price", "list_price",
]

# Name suffixes that suggest an aggregate metric derived from components
# sharing the same prefix (e.g. engagement_score vs engagement_like_count).
AGGREGATE_SUFFIXES = ["score", "index"]

# ==================== MISSINGNESS / SUPPRESSION VOCABULARY ====================
# Tokens that may represent SUPPRESSED or non-applicable values rather than
# ordinary missing data. These are CLASSIFICATION evidence only: the engine
# never converts them automatically (a bare "s" must never become a 0).
SUPPRESSION_TOKEN_CANDIDATES = [
    # Include bare "s" so suppression-token heuristic can flag columns where
    # a large share of values are the letter s (common suppression marker in
    # some government/survey datasets). Share-based guards in MissingValueDetector
    # still prevent pure categorical codes from being treated as suppression.
    "s", "suppressed", "suppression", "not available", "na (suppressed)",
    "withheld", "redacted", "masked",
]

# Common string tokens that represent missing / unknown values in real-world
# tabular data (UCI Adult uses "?", many CSVs use "NA" / "N/A" / "null").
# These are treated as missing-equivalent during detection so they can be
# imputed or flagged — they are NOT auto-converted without a decision.
MISSING_STRING_TOKENS = [
    "?", "na", "n/a", "nan", "null",
    "missing", "not applicable", "n.a.", "n.a",
]


def missing_equivalent_mask(series, exclude_values=None):
    """Boolean mask of NaN / empty / whitespace / missing-string tokens.

    `exclude_values` are never treated as missing (so a fill of "Unknown"
    does not immediately re-count as a missing token).
    """
    import pandas as pd

    mask = series.isna()
    exclude = {
        str(v).strip().lower()
        for v in (exclude_values or [])
        if v is not None and not (isinstance(v, float) and pd.isna(v))
    }
    try:
        as_str = series.astype("string")
        stripped = as_str.str.strip()
        empty = stripped.isna() | (stripped == "")
        tokens = {t.lower() for t in MISSING_STRING_TOKENS} - exclude
        token_hit = stripped.str.lower().isin(tokens)
        mask = mask | empty | token_hit
        if exclude:
            mask = mask & ~stripped.str.lower().isin(exclude)
    except Exception:
        pass
    return mask.fillna(False)

# Whitespace-only / empty-string values behave like missing cells for
# profiling purposes but are NEVER converted without an approved action.
EMPTY_MISSING_TOKENS = [""]

# ==================== DAY-OF-WEEK VOCABULARY ====================
# Column-name tokens indicating a weekday column whose value is derived from
# a datetime source (day_of_week = weekday(posted_datetime)).
DAYOFWEEK_TOKENS = ["weekday", "dow"]
DAYOFWEEK_PAIR_TOKENS = [("day", "week"), ("day", "wk")]

# Plausibility rule: an age-like column below this value combined with a
# count-like column above this threshold is SUSPICIOUS (flag-only), never
# automatically invalid.
PLAUSIBILITY_AGE_MIN = 16
PLAUSIBILITY_COUNT_HIGH = 3