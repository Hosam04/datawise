"""Visualization Agent package for DataWise.

This package provides modular visualization components while maintaining
backward compatibility with existing imports.
"""
from backend.agents.visualization.viz_agent import VisualizationAgent
from backend.agents.visualization.constants import (
    CHART_COLORS,
    MAX_BAR_UNIQUE_VALUES,
    TEXT_COLUMN_NAMES,
)
from backend.agents.visualization.chart_helpers import (
    compute_box_stats,
    histogram_payload,
    render_correlation_heatmap,
)
from backend.agents.visualization.data_prep import (
    get_attr,
    is_text_column,
    is_url_column,
    extract_domain,
    get_missing_rate,
    prepare_missing_rate_chart,
    prepare_url_source_chart,
    prepare_text_box_chart,
    prepare_line_chart,
    prepare_text_y_axis,
    fallback_charts,
)
from backend.agents.visualization.renderers import render_ml_chart

__all__ = [
    "VisualizationAgent",
    "CHART_COLORS",
    "MAX_BAR_UNIQUE_VALUES",
    "TEXT_COLUMN_NAMES",
    "compute_box_stats",
    "histogram_payload",
    "render_correlation_heatmap",
    "get_attr",
    "is_text_column",
    "is_url_column",
    "extract_domain",
    "get_missing_rate",
    "prepare_missing_rate_chart",
    "prepare_url_source_chart",
    "prepare_text_box_chart",
    "prepare_line_chart",
    "prepare_text_y_axis",
    "fallback_charts",
    "render_ml_chart",
]