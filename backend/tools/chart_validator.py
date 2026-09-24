import pandas as pd


def validate_chart(df: pd.DataFrame, chart):
    errors = []

    # ── 1. Column existence ──
    if chart.x_axis not in df.columns:
        errors.append(f"x_axis '{chart.x_axis}' does not exist")

    if chart.y_axis and chart.y_axis not in df.columns:
        errors.append(f"y_axis '{chart.y_axis}' does not exist")

    if errors:
        return False, errors

    x = df[chart.x_axis]
    y = df[chart.y_axis] if chart.y_axis else None
    ctype = chart.chart_type.lower()

    # ── 2. Histogram ──
    if ctype == "histogram":
        # Histogram works with any x_axis type
        pass  # No additional validation needed

    # ── 3. Heatmap ──
    elif ctype == "heatmap":
        # Correlation/confusion heatmaps are built directly by the viz agent from the
        # numeric columns or the ML results; there is no x/y column contract to check.
        pass

    # ── 4. Box ──
    elif ctype == "box":
        # Box plot: x_axis can be categorical, y_axis should be numeric
        # If y_axis is None, we'll use first numeric column in vis_agent
        if y is not None and not pd.api.types.is_numeric_dtype(y):
            errors.append("Box y_axis must be numeric")
        if x.nunique() > 100:
            errors.append("Too many categories for box plot (max 100)")

    # ── 5. Pie ──
    elif ctype == "pie":
        if y is None:
            errors.append("Pie chart requires a values column (y_axis)")

        if y is not None and not pd.api.types.is_numeric_dtype(y):
            errors.append("Pie y_axis must be numeric")

        if x.nunique() > 20:
            errors.append("Too many categories for pie chart (max 20)")

    # ── 6. Scatter ──
    elif ctype == "scatter":
        if y is None:
            errors.append("Scatter chart requires y_axis")

        if not pd.api.types.is_numeric_dtype(x):
            errors.append("Scatter x_axis must be numeric")

        if y is not None and not pd.api.types.is_numeric_dtype(y):
            errors.append("Scatter y_axis must be numeric")

    # ── 7. Line ──
    elif ctype == "line":
        if y is None:
            errors.append("Line chart requires y_axis")

        if not pd.api.types.is_numeric_dtype(x) \
           and not pd.api.types.is_datetime64_any_dtype(x):
            errors.append("Line x_axis must be numeric or datetime")

        if y is not None and not pd.api.types.is_numeric_dtype(y):
            errors.append("Line y_axis must be numeric")

    # ── 8. Bar ──
    elif ctype == "bar":
        if x.nunique() > 100:
            errors.append("Too many categories for bar chart (max 100)")

        if y is not None and not pd.api.types.is_numeric_dtype(y):
            errors.append("Bar y_axis must be numeric")

    # ── 9. Unknown type ──
    else:
        return False, [f"Unknown chart type: '{chart.chart_type}'"]

    return (True, []) if not errors else (False, errors)