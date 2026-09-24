"""Visualization-specific constants for the DataWise Visualization Agent."""

# Chart colors used for dataset rendering
CHART_COLORS = [
    "#3b82f6",  # blue
    "#10b981",  # emerald
    "#f59e0b",  # amber
    "#8b5cf6",  # violet
    "#ef4444",  # red
    "#06b6d4",  # cyan
    "#f97316",  # orange
]

# Maximum unique values allowed for bar charts (prevents unreadable charts)
MAX_BAR_UNIQUE_VALUES = 35

# Column names that suggest text content (used for auto-detection)
TEXT_COLUMN_NAMES = {
    "link", "title", "content", "description", "text", "url", "name", "body", "snippet"
}

# Default plotly rendering settings
DEFAULT_PLOTLY_FORMAT = "png"
DEFAULT_PLOTLY_WIDTH = 800
DEFAULT_PLOTLY_HEIGHT = 500

# Missing value thresholds for chart skipping
MISSING_RATE_THRESHOLD_X = 0.50  # 50%
MISSING_RATE_THRESHOLD_Y = 0.50  # 50%
MISSING_RATE_THRESHOLD_SPARSE = 0.80  # 80%