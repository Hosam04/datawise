"""Data preparation utilities for the Visualization Agent."""
import re
from urllib.parse import urlparse

import pandas as pd
import numpy as np

from backend.agents.visualization.constants import TEXT_COLUMN_NAMES


def get_attr(config, key, default=None):
    """Get attribute from config (dict or object)."""
    if isinstance(config, dict):
        return config.get(key, default)
    return getattr(config, key, default)


def is_text_column(df: pd.DataFrame, col_name: str) -> bool:
    """Check if a column is a text column."""
    if col_name not in df.columns:
        return False
    if any(kw in str(col_name).lower() for kw in TEXT_COLUMN_NAMES):
        return True
    if df[col_name].dtype in (object, "string", "O"):
        n_unique = df[col_name].nunique()
        if n_unique / len(df) > 0.05:
            return True
    return False


def is_url_column(df: pd.DataFrame, col_name: str) -> bool:
    """Check if column contains URLs."""
    if col_name not in df.columns:
        return False
    sample = df[col_name].dropna().head(20)
    if len(sample) == 0:
        return False
    url_pattern = re.compile(r'^https?://')
    url_ratio = sample.astype(str).str.match(url_pattern).mean()
    return url_ratio > 0.5


def extract_domain(url) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(str(url))
        domain = parsed.netloc
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return "unknown"


def get_missing_rate(df: pd.DataFrame, col_name: str) -> float:
    """Get missing rate for a column."""
    if col_name and col_name in df.columns:
        return df[col_name].isna().mean()
    return 0.0


def prepare_missing_rate_chart(df: pd.DataFrame, x_axis: str, y_axis: str, x_label: str, y_label: str):
    """Prepare data for missing rate chart."""
    explicit_missing_rate_col = None
    if isinstance(y_axis, str) and y_axis.startswith("__missing_rate__:"):
        explicit_missing_rate_col = y_axis.split(":", 1)[1]
    
    missing_col = explicit_missing_rate_col or y_axis
    missing_rate = df.groupby(x_axis)[missing_col].apply(
        lambda x: x.isna().sum() / max(len(x), 1) * 100
    ).reset_index()
    missing_rate.columns = [x_axis, "missing_rate"]
    
    plot_df = missing_rate
    plot_y = "missing_rate"
    y_label = f"Missing {y_axis.title()} (%)"
    
    return plot_df, plot_y, y_label


def prepare_url_source_chart(df: pd.DataFrame, x_axis: str, y_axis: str, x_label: str, y_label: str):
    """Prepare data for URL/Source distribution chart."""
    plot_df = df[[x_axis, y_axis]].copy()
    plot_df["domain"] = plot_df[y_axis].apply(extract_domain)
    domain_counts = plot_df.groupby([x_axis, "domain"]).size().reset_index(name="count")
    top_domains = domain_counts.loc[domain_counts.groupby(x_axis)["count"].idxmax()]
    plot_df = top_domains[[x_axis, "domain", "count"]]
    plot_y = "count"
    y_label = "Source Count"
    
    return plot_df, plot_y, y_label


def prepare_text_box_chart(df: pd.DataFrame, x_axis: str, target: str):
    """Convert unreadable text bar chart to box plot."""
    chart_type = "box"
    y_axis = x_axis
    x_axis = target
    title = f"{str(y_axis).title()} Length by {str(target).title()}"
    x_label = target
    y_label = f"{str(y_axis).title()} Length (chars)"
    plot_df = df.copy()
    plot_df[f"{y_axis}_length"] = plot_df[y_axis].astype(str).str.len()
    plot_y = f"{y_axis}_length"
    
    return chart_type, x_axis, y_axis, title, x_label, y_label, plot_df, plot_y

def _to_datetime_safe(series: pd.Series) -> pd.Series:
    """Convert to datetime without treating year integers as epoch ns."""
    if pd.api.types.is_numeric_dtype(series):
        vals = pd.to_numeric(series, errors="coerce")
        non_null = vals.dropna()
        if (
            len(non_null) > 0
            and float(non_null.min()) >= 1900
            and float(non_null.max()) <= 2100
            and (non_null % 1 == 0).all()
        ):
            return pd.to_datetime(
                non_null.astype(int).astype(str), format="%Y", errors="coerce"
            ).reindex(series.index)
    return pd.to_datetime(series, errors="coerce")

def prepare_line_chart(plot_df: pd.DataFrame, x_axis: str, plot_y: str):
    """Prepare data for line chart."""
    plot_df = plot_df.copy()
    plot_df[x_axis] = _to_datetime_safe(plot_df[x_axis])
    plot_df = plot_df.dropna(subset=[x_axis])
    if plot_y == "count":
        plot_df = plot_df.groupby(x_axis).size().reset_index(name="count")
        plot_y = "count"
    else:
        plot_df = plot_df.groupby(x_axis)[plot_y].mean().reset_index()
    return plot_df, plot_y


def prepare_text_y_axis(plot_df: pd.DataFrame, df: pd.DataFrame, plot_y: str, y_axis: str, y_label: str):
    """Handle text columns on y_axis by computing length."""
    if plot_y and plot_y in df.columns:
        if df[plot_y].dtype in (object, "string", "O"):
            plot_df[f"{plot_y}_length"] = df[plot_y].astype(str).str.len()
            plot_y = f"{plot_y}_length"
            y_label = f"{y_axis.title()} Length (chars)"
    return plot_df, plot_y, y_label


def fallback_charts(df: pd.DataFrame):
    """Generate fallback charts when no plan is provided."""
    numeric = df.select_dtypes(include="number").columns.tolist()
    datetime_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    if not datetime_cols:
        datetime_cols = [c for c in df.columns if df[c].dtype == "object" and pd.to_datetime(df[c], errors="coerce").notna().sum() >= max(1, len(df) // 2)]
    categorical = [c for c in df.columns if c not in numeric and c not in datetime_cols]

    if datetime_cols and numeric:
        return [{"chart_type": "line", "x_axis": datetime_cols[0], "y_axis": numeric[0], "title": f"{numeric[0]} over time", "x_label": datetime_cols[0], "y_label": numeric[0]}]
    if categorical:
        return [{"chart_type": "bar", "x_axis": categorical[0], "y_axis": numeric[0] if numeric else None, "title": f"Distribution of {categorical[0]}", "x_label": categorical[0], "y_label": numeric[0] if numeric else "Count"}]
    if numeric:
        return [{"chart_type": "histogram", "x_axis": numeric[0], "y_axis": None, "title": f"Distribution of {numeric[0]}", "x_label": numeric[0], "y_label": "Count"}]
    return []





