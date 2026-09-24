"""Chart data preparation helpers for the Visualization Agent.

These are single source of truth for BOTH the PDF and the interactive frontend.
Dataset-agnostic: no hardcoded column names.
"""
import numpy as np
import pandas as pd

from backend.statistics.bivariate import raw_numeric_matrix
from backend.statistics.outliers import five_number_summary
from backend.agents.visualization.constants import CHART_COLORS


def compute_box_stats(df: pd.DataFrame, group_col: str, value_col: str):
    """Five-number summary + outliers per group.

    Uses linear-interpolation quantiles (numpy default), which is exactly
    what the frontend `quantile()` uses, so the interactive boxes match
    the PDF boxes one-to-one. Quantile/fence mathematics is delegated to
    the Statistical Engine (single authoritative implementation).
    Returns one entry per group (sorted order).
    """
    boxes = []
    if value_col not in df.columns or group_col not in df.columns:
        return boxes
    work = pd.DataFrame({
        "group": df[group_col],
        "value": pd.to_numeric(df[value_col], errors="coerce"),
    }).dropna(subset=["value"])
    for name, sub in work.groupby("group", sort=True):
        values = sorted(float(v) for v in sub["value"].tolist())
        if not values:
            continue
        summary = five_number_summary(values)
        q1, median, q3 = summary["q1"], summary["median"], summary["q3"]
        lo_fence, hi_fence = summary["lo_fence"], summary["hi_fence"]
        in_whisker = [v for v in values if lo_fence <= v <= hi_fence]
        outliers = [v for v in values if v < lo_fence or v > hi_fence]
        boxes.append({
            "label": str(name),
            "min": float(in_whisker[0]) if in_whisker else float(values[0]),
            "q1": q1,
            "median": median,
            "q3": q3,
            "max": float(in_whisker[-1]) if in_whisker else float(values[-1]),
            "outliers": outliers,
        })
    return boxes


def histogram_payload(series: pd.Series, nbins=None):
    """Build binned histogram payload that mirrors px.histogram.

    Continuous numeric series -> numpy bins (midpoint labels).
    Categorical / non-numeric -> value_counts (same as a discrete bar).
    """
    s = series.dropna()
    if len(s) == 0:
        return []
    numeric = pd.to_numeric(s, errors="coerce")
    if numeric.notna().mean() >= 0.9 and numeric.nunique() > 15:
        vals = numeric.dropna().to_numpy(dtype=float)
        bins = nbins if nbins is not None else "auto"
        counts, edges = np.histogram(vals, bins=bins)
        out = []
        for i, c in enumerate(counts):
            if c <= 0:
                continue
            mid = (edges[i] + edges[i + 1]) / 2.0
            out.append({"name": f"{mid:.6g}", "value": float(c)})
        return out
    counts = s.astype(str).value_counts().head(100)
    return [{"name": str(label), "value": float(value)} for label, value in counts.items()]


def render_correlation_heatmap(df: pd.DataFrame, title: str):
    """General (non-ML) heatmap: correlation matrix of all numeric columns.

    Dataset-agnostic -- never assumes a confusion matrix. Guarantees that a
    requested heatmap is always backed by real data (not image-only).
    Correlation math is delegated to the Statistical Engine's rendering-
    parity helper (unfiltered numeric matrix) so the rendered output is
    byte-identical to the historical pandas implementation.
    Returns (fig, visualization_data, extra_options) or (None, None, {}).
    """
    import plotly.express as px

    cols, grid = raw_numeric_matrix(df, method="pearson")
    if len(cols) < 2:
        return None, None, {}
    z = [
        [float(v) if v is not None else 0.0 for v in row]
        for row in grid
    ]
    fig = px.imshow(z, x=cols, y=cols, color_continuous_scale="Blues", aspect="auto")
    # Show cell values inside the PDF exactly like the frontend does for
    # small matrices.
    if len(cols) <= 10:
        for i in range(len(cols)):
            for j in range(len(cols)):
                fig.add_annotation(
                    x=cols[j], y=cols[i],
                    text=f"{z[i][j]:.2f}",
                    showarrow=False,
                    font=dict(color="white" if z[i][j] > 0.5 else "black"),
                )
    fig.update_layout(title=title)
    visualization_data = [
        {"name": f"{cols[i]} \u00d7 {cols[j]}", "value": z[i][j]}
        for i in range(len(cols)) for j in range(len(cols))
    ]
    extra_options = {"heatmap": {"x": cols, "y": cols, "z": z}}
    return fig, visualization_data, extra_options