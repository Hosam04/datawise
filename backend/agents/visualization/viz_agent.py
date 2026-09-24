"""Visualization Agent for the DataWise analysis pipeline."""
import os
import plotly.express as px
import plotly.io as pio
import pandas as pd
import numpy as np
from backend.agents.base.base_agent import BaseAgent
from backend.core.state import AgentState
from backend.tools.chart_validator import validate_chart

from backend.agents.visualization.constants import (
    CHART_COLORS,
    MAX_BAR_UNIQUE_VALUES,
    MISSING_RATE_THRESHOLD_X,
    MISSING_RATE_THRESHOLD_Y,
    MISSING_RATE_THRESHOLD_SPARSE,
)
from backend.agents.visualization.chart_helpers import (
    compute_box_stats,
    histogram_payload,
    render_correlation_heatmap,
)
from backend.agents.visualization.data_prep import (
    get_attr,
    get_missing_rate,
    is_text_column,
    is_url_column,
    extract_domain,
    prepare_missing_rate_chart,
    prepare_url_source_chart,
    prepare_text_box_chart,
    prepare_line_chart,
    prepare_text_y_axis,
    fallback_charts,
)
from backend.agents.visualization.renderers import render_ml_chart

# Configure plotly/kaleido defaults
pio.defaults.default_format = "png"
pio.defaults.default_width = 800
pio.defaults.default_height = 500
pio.defaults.mathjax = None


class VisualizationAgent(BaseAgent):

    def __init__(self):
        super().__init__("VisualizationAgent")

    def run(self, state: AgentState) -> AgentState:
        self.log_execution(state.session_id)
        df = state.get_df()

        if df is None or df.empty:
            self.logger.warning("No visualizable DataFrame found.")
            state.visualizations = []
            state.visualization_paths = []
            return state

        charts = get_attr(state.plan, 'charts', []) if state.plan else []
        self.logger.info(f"Charts count: {len(charts)}")

        if not charts:
            self.logger.info("No charts in plan; generating fallback charts.")
            charts = fallback_charts(df)

        os.makedirs(state.session_dir, exist_ok=True)

        saved_paths = []
        visualizations = []
        skipped_charts = []  # track intentional skips for the report

        for i, config in enumerate(charts):
            try:
                chart_type = get_attr(config, 'chart_type')
                x_axis = get_attr(config, 'x_axis')
                y_axis = get_attr(config, 'y_axis')
                title = get_attr(config, 'title', 'Untitled')
                x_label = get_attr(config, 'x_label', x_axis)
                y_label = get_attr(config, 'y_label', y_axis)

                self.logger.info(f"Chart {i}: {chart_type} | x={x_axis} | y={y_axis} | title={title}")

                x_missing = get_missing_rate(df, x_axis)
                y_missing = get_missing_rate(df, y_axis)

                if x_missing > MISSING_RATE_THRESHOLD_X:
                    reason = f"x_axis '{x_axis}' has {x_missing:.1%} missing values (>50% threshold)"
                    self.logger.warning(f"Chart {i}: SKIPPED - {reason}")
                    skipped_charts.append({"index": i, "title": title, "reason": reason})
                    continue

                if y_axis and not str(y_axis).startswith("__") and y_missing > MISSING_RATE_THRESHOLD_Y:
                    reason = f"y_axis '{y_axis}' has {y_missing:.1%} missing values (>50% threshold)"
                    self.logger.warning(f"Chart {i}: SKIPPED - {reason}")
                    skipped_charts.append({"index": i, "title": title, "reason": reason})
                    continue

                if y_axis and str(y_axis).startswith("__missing_rate__:"):
                    underlying_col = str(y_axis).split(":", 1)[1]
                    underlying_missing = get_missing_rate(df, underlying_col)
                    if underlying_missing > MISSING_RATE_THRESHOLD_SPARSE:
                        reason = (
                            f"missing rate chart for '{underlying_col}' with "
                            f"{underlying_missing:.1%} missing (too sparse)"
                        )
                        self.logger.warning(f"Chart {i}: SKIPPED - {reason}")
                        skipped_charts.append({"index": i, "title": title, "reason": reason})
                        continue

                # Defaults so ML/heatmap paths never hit a NameError below.
                plot_df = df
                plot_y = None

                # Per-chart options payload: box plots and heatmaps put their
                # FULL dataset here so the frontend renders exactly what the
                # PDF shows (one chart spec → two renderers).
                chart_options = {}

                # === Handle ML-specific charts FIRST ===
                fig, visualization_data, ml_options = render_ml_chart(
                    chart_type, x_axis, y_axis, title, x_label, y_label, state.ml_results
                )
                if fig is not None:
                    # ML chart was rendered successfully
                    chart_options.update(ml_options)
                elif chart_type == "heatmap":
                    # Non-ML heatmap (e.g. correlation matrix). Dataset-agnostic,
                    # so a heatmap is never reduced to an image-only artifact.
                    fig, visualization_data, hm_options = render_correlation_heatmap(df, title)
                    if fig is None:
                        self.logger.warning(f"Chart {i}: heatmap needs \u22652 numeric columns. Skipping.")
                        continue
                    chart_options.update(hm_options)
                elif x_axis not in df.columns:
                    self.logger.warning(f"Chart {i}: x_axis '{x_axis}' not in columns. Skipping.")
                    continue
                else:
                    # === Original chart rendering logic ===
                    plot_title_lower = title.lower()
                    explicit_missing_rate_col = None
                    if isinstance(y_axis, str) and y_axis.startswith("__missing_rate__:"):
                        explicit_missing_rate_col = y_axis.split(":", 1)[1]
                    is_missing_rate_chart = (
                        explicit_missing_rate_col in df.columns
                        if explicit_missing_rate_col else
                        ("missing" in plot_title_lower and y_axis and y_axis in df.columns)
                    )
                    is_source_dist_chart = "source" in plot_title_lower and "distribution" in plot_title_lower
                    is_url_chart = y_axis and is_url_column(df, y_axis)

                    # Handle missing rate FIRST
                    if is_missing_rate_chart:
                        plot_df, plot_y, y_label = prepare_missing_rate_chart(
                            df, x_axis, y_axis, x_label, y_label
                        )

                    # Handle URL/Source distribution
                    elif (is_url_chart or is_source_dist_chart) and y_axis and y_axis in df.columns:
                        plot_df, plot_y, y_label = prepare_url_source_chart(
                            df, x_axis, y_axis, x_label, y_label
                        )

                    # Auto-convert unreadable text bar charts to box plots
                    elif chart_type == "bar" and y_axis is None and is_text_column(df, x_axis):
                        target = state.target_detection.get("target_column") if state.target_detection else None
                        if target and target in df.columns:
                            chart_type, x_axis, y_axis, title, x_label, y_label, plot_df, plot_y = prepare_text_box_chart(
                                df, x_axis, target
                            )
                        else:
                            self.logger.warning(f"Chart {i}: No target found for text box plot. Skipping.")
                            continue

                    # Protection: Skip unreadable bar charts
                    elif chart_type == "bar" and y_axis is None:
                        n_unique = df[x_axis].nunique()
                        if n_unique > MAX_BAR_UNIQUE_VALUES:
                            self.logger.warning(
                                f"Chart {i}: Skipping bar chart for '{x_axis}' \u2014 "
                                f"{n_unique} unique values > {MAX_BAR_UNIQUE_VALUES}."
                            )
                            continue
                        plot_df = df[[x_axis]].copy()
                        plot_y = None

                    # Prepare data (for non-special charts)
                    else:
                        plot_df = df.copy()
                        plot_y = y_axis

                        # Convert date columns to datetime for line charts
                        if chart_type == "line" and x_axis in plot_df.columns:
                            from backend.agents.visualization.data_prep import _to_datetime_safe
                            plot_df[x_axis] = _to_datetime_safe(plot_df[x_axis])

                        # Handle line chart requesting explicit count aggregation
                        if chart_type == "line" and plot_y == "count":
                            plot_df, plot_y = prepare_line_chart(plot_df, x_axis, plot_y)

                        # Handle text columns on y_axis (compute length)
                        elif plot_y and plot_y in df.columns:
                            plot_df, plot_y, y_label = prepare_text_y_axis(
                                plot_df, df, plot_y, y_axis, y_label
                            )

                        if plot_y and plot_y not in plot_df.columns:
                            self.logger.warning(f"Chart {i}: y_axis '{plot_y}' not available. Skipping.")
                            continue

                    # Validation
                    if chart_type in {"histogram", "box", "bar"}:
                        valid, errors = True, []
                    else:
                        valid, errors = validate_chart(plot_df, config)

                    if not valid:
                        self.logger.warning(f"Chart rejected: {errors}")
                        continue

                    # Chart generation
                    fig = None

                    if chart_type == "histogram":
                        fig = px.histogram(plot_df, x=x_axis)

                    elif chart_type == "bar":
                        if plot_y and plot_y in plot_df.columns and pd.api.types.is_numeric_dtype(plot_df[plot_y]):
                            # Aggregate to mean so binary/rate targets render
                            # as a clean category-level rate chart instead of
                            # one bar per row.
                            agg_df = (
                                plot_df.groupby(x_axis, observed=True)[plot_y]
                                .mean()
                                .reset_index()
                            )
                            fig = px.bar(agg_df, x=x_axis, y=plot_y)
                        else:
                            counts = plot_df[x_axis].value_counts().reset_index()
                            counts.columns = [x_axis, "count"]
                            fig = px.bar(counts, x=x_axis, y="count")

                    elif chart_type == "scatter":
                        if not plot_y:
                            self.logger.warning(f"Chart {i}: scatter requires y_axis. Skipping.")
                            continue
                        fig = px.scatter(plot_df, x=x_axis, y=plot_y)

                    elif chart_type == "line":
                        if not plot_y:
                            plot_df[x_axis] = pd.to_datetime(plot_df[x_axis])
                            plot_df = plot_df.set_index(x_axis).resample('D').size().reset_index(name='count')
                            plot_y = "count"
                        else:
                            plot_df[x_axis] = pd.to_datetime(plot_df[x_axis])
                            plot_df = plot_df.groupby(x_axis)[plot_y].mean().reset_index()
                        fig = px.line(plot_df, x=x_axis, y=plot_y)

                    elif chart_type == "pie":
                        if not plot_y:
                            counts = plot_df[x_axis].value_counts().reset_index()
                            counts.columns = [x_axis, "count"]
                            fig = px.pie(counts, names=x_axis, values="count")
                        elif plot_y in plot_df.columns and pd.api.types.is_numeric_dtype(plot_df[plot_y]):
                            # Aggregate so duplicate categories become one slice
                            # (matches what the interactive payload ships).
                            pie_agg = (
                                plot_df.groupby(x_axis, observed=True)[plot_y]
                                .sum()
                                .reset_index()
                            )
                            fig = px.pie(pie_agg, names=x_axis, values=plot_y)
                        else:
                            fig = px.pie(plot_df, names=x_axis, values=plot_y)

                    elif chart_type == "box":
                        box_value_col = None
                        if plot_y and plot_y in plot_df.columns:
                            box_value_col = plot_y
                            fig = px.box(plot_df, x=x_axis, y=plot_y)
                        else:
                            numeric_cols = plot_df.select_dtypes(include=[np.number]).columns.tolist()
                            if numeric_cols and x_axis in plot_df.columns:
                                box_value_col = numeric_cols[0]
                                fig = px.box(plot_df, x=x_axis, y=box_value_col)
                            else:
                                self.logger.warning(f"Chart {i}: box requires numeric y_axis. Skipping.")
                                continue

                        # FIX (Box Plot): ship the full per-group five-number
                        # summary so the frontend draws one box per category
                        # (matching the PDF) instead of a single aggregated candle.
                        box_stats = compute_box_stats(plot_df, x_axis, box_value_col)
                        if box_stats:
                            chart_options["boxplot"] = box_stats
                            # Force the PDF to use the same category order as the
                            # payload, so report and UI show identical box order.
                            fig.update_layout(xaxis={
                                "categoryorder": "array",
                                "categoryarray": [b["label"] for b in box_stats],
                            })

                    else:
                        self.logger.warning(f"Unsupported chart type: {chart_type}")
                        continue

                    # Update layout
                    fig.update_layout(title=title)
                    if chart_type != "pie":
                        fig.update_layout(
                            xaxis_title=x_label,
                            yaxis_title=y_label if plot_y else "Count"
                        )

                    # Build visualization data \u2014 must mirror what was drawn into
                    # `fig` so the interactive frontend matches the PNG/report.
                    data = fig.data[0] if fig.data else None
                    if chart_type == "histogram":
                        visualization_data = histogram_payload(plot_df[x_axis])
                    elif chart_type == "bar":
                        if plot_y and plot_y in plot_df.columns and pd.api.types.is_numeric_dtype(plot_df[plot_y]):
                            # Must match the aggregated figure above (mean per
                            # category). Using raw plot_df.iterrows() produced
                            # one bar per row in the interactive frontend while
                            # the PNG correctly showed category-level means.
                            if x_axis in plot_df.columns:
                                agg_for_payload = (
                                    plot_df.groupby(x_axis, observed=True)[plot_y]
                                    .mean()
                                    .reset_index()
                                )
                                visualization_data = [
                                    {"name": str(row[x_axis]), "value": float(row[plot_y])}
                                    for _, row in agg_for_payload.iterrows()
                                ]
                            else:
                                visualization_data = []
                        else:
                            counts = plot_df[x_axis].dropna().value_counts().head(100)
                            visualization_data = [{"name": str(label), "value": float(value)}
                                                  for label, value in counts.items()]
                    elif chart_type == "box":
                        # Interactive box plot reads options.boxplot; labels here
                        # are only a lightweight index (medians), not the boxes.
                        if plot_y and plot_y in plot_df.columns:
                            medians = plot_df.groupby(x_axis)[plot_y].median().sort_values(ascending=False)
                            visualization_data = [{"name": str(label), "value": float(value)}
                                                  for label, value in medians.head(100).items()]
                        else:
                            counts = plot_df[x_axis].dropna().value_counts().head(100)
                            visualization_data = [{"name": str(label), "value": float(value)}
                                                  for label, value in counts.items()]
                    elif chart_type == "pie":
                        # Prefer the aggregated slices already on the figure so
                        # duplicate category rows never produce repeated slices.
                        if data and getattr(data, "labels", None) is not None and getattr(data, "values", None) is not None:
                            visualization_data = [
                                {"name": str(label), "value": float(val) if val is not None else 0}
                                for label, val in zip(data.labels, data.values)
                            ]
                        elif plot_y and plot_y in plot_df.columns and pd.api.types.is_numeric_dtype(plot_df[plot_y]):
                            pie_agg = (
                                plot_df.groupby(x_axis, observed=True)[plot_y]
                                .sum()
                                .reset_index()
                            )
                            visualization_data = [
                                {"name": str(row[x_axis]), "value": float(row[plot_y])}
                                for _, row in pie_agg.iterrows()
                            ]
                        else:
                            counts = plot_df[x_axis].value_counts().head(100)
                            visualization_data = [{"name": str(label), "value": float(value)}
                                                  for label, value in counts.items()]
                    elif chart_type in {"scatter", "line"}:
                        # Pull x/y straight off the figure so resampling /
                        # aggregation applied above is reflected 1:1.
                        if data is not None and getattr(data, "x", None) is not None and getattr(data, "y", None) is not None:
                            visualization_data = []
                            for x, y in zip(data.x, data.y):
                                if x is None or (isinstance(x, float) and np.isnan(x)):
                                    continue
                                visualization_data.append({
                                    "name": str(x),
                                    "value": float(y) if y is not None and not (isinstance(y, float) and np.isnan(y)) else 0,
                                })
                        else:
                            visualization_data = []
                    else:
                        visualization_data = []

                # Save chart
                output_path = os.path.join(state.session_dir, f"chart_{i + 1}.png")
                try:
                    # engine= is deprecated; Kaleido is the only supported backend now.
                    fig.write_image(output_path)
                    if not os.path.exists(output_path):
                        raise RuntimeError("Kaleido returned without creating the image file.")
                except Exception as img_err:
                    # A visualization is not considered successfully produced
                    # unless its artifact really exists.  Keeping a phantom path
                    # here makes the PDF/frontend believe a skipped/broken chart
                    # exists and misaligns chart IDs.
                    self.logger.warning(
                        f"Kaleido failed to save chart {i} ({chart_type}): {img_err}"
                    )
                    continue

                saved_paths.append(output_path)

                # FIX (id alignment): the id is the chart's index in the saved
                # image list \u2014 exactly what GET /charts/{chart_id} resolves.
                # Frontend \u2194 PDF linking happens by this id (never by array
                # position), which stays correct even when charts are skipped.
                chart_id = len(saved_paths)
                base_options = {"responsive": True, "plugins": {"legend": {"display": True}}}

                if chart_type == "heatmap":
                    # FIX (Heatmap): heatmaps are no longer excluded from the
                    # payload. The matrix + labels live in `options`, so the
                    # frontend renders the SAME numbers as the PDF instead of a
                    # PNG. `datasets` stays an (empty) array so the UI promotion
                    # filter accepts the chart as interactive.
                    hm = chart_options.get("confusion_matrix") or chart_options.get("heatmap") or {}
                    hm_labels = hm.get("labels") or hm.get("x") or []
                    if "confusion_matrix" in chart_options:
                        # Match the PDF axes exactly (px.imshow labels).
                        hm_x_label, hm_y_label = "Predicted", "Actual"
                    else:
                        hm_x_label, hm_y_label = x_label, y_label
                    visualizations.append({
                        "id": chart_id,
                        "type": "heatmap",
                        "title": title,
                        "xAxisLabel": hm_x_label,
                        "yAxisLabel": hm_y_label,
                        "labels": [str(l) for l in hm_labels],
                        "datasets": [],
                        "options": {**base_options, **chart_options},
                    })
                else:
                    visualizations.append({
                        "id": chart_id,
                        "type": chart_type,
                        "title": title,
                        "xAxisLabel": x_label,
                        "yAxisLabel": y_label if (y_axis or plot_y) else "Count",
                        "labels": [item["name"] for item in visualization_data],
                        "datasets": [{
                            "label": y_label or title,
                            "data": [item["value"] for item in visualization_data],
                            "backgroundColor": CHART_COLORS[i % len(CHART_COLORS)],
                            "borderColor": CHART_COLORS[i % len(CHART_COLORS)],
                        }],
                        "options": {**base_options, **chart_options},
                    })

                self.logger.info(f"Chart {i} saved to {output_path}")

            except Exception as e:
                self.logger.error(f"Failed to generate chart {i}: {str(e)}")
                import traceback
                self.logger.error(traceback.format_exc())
                continue

        state.visualization_paths = saved_paths
        state.visualizations = visualizations
        # Expose intentional skips so the report can document them
        try:
            state.skipped_charts = skipped_charts
        except Exception:
            pass
        self.logger.info(f"Total charts saved: {len(saved_paths)}")
        self.logger.info(f"Total visualizations: {len(visualizations)}")
        if skipped_charts:
            self.logger.info(f"Skipped charts: {len(skipped_charts)}")
        return state