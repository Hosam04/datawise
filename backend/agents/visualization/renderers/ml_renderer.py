"""ML-specific chart renderers for the Visualization Agent."""
import numpy as np
import pandas as pd
import plotly.express as px

from backend.agents.visualization.chart_helpers import histogram_payload


def render_ml_chart(chart_type, x_axis, y_axis, title, x_label, y_label, ml_results):
    """Render ML-specific charts.

    Returns (fig, visualization_data, extra_options). `extra_options`
    carries the chart's real payload (e.g. the confusion matrix) so the
    frontend renders the exact same numbers as the PDF.
    Returns (None, None, {}) when the request is not an ML chart.
    """
    if not ml_results or ml_results.status != "success":
        return None, None, {}

    # ML Feature Importance
    if chart_type == "bar" and x_axis == "feature" and y_axis == "importance":
        if not ml_results.feature_importance:
            return None, None, {}
        fi_data = ml_results.feature_importance[:15]
        fi_df = pd.DataFrame([
            {"feature": item.feature, "importance": item.importance}
            for item in fi_data
        ])
        fig = px.bar(fi_df, x="feature", y="importance")
        fig.update_layout(title=title, xaxis_title=x_label, yaxis_title=y_label)
        visualization_data = [
            {"name": item.feature, "value": item.importance}
            for item in fi_data
        ]
        return fig, visualization_data, {}

    if chart_type == "heatmap" and ml_results.confusion_matrix:
        cm_data = ml_results.confusion_matrix
        matrix = np.array(cm_data["matrix"])
        labels = cm_data.get("labels", [])
        if not labels:
            labels = [str(i) for i in range(len(matrix))]

        fig = px.imshow(
            matrix,
            labels=dict(x="Predicted", y="Actual", color="Count"),
            x=labels,
            y=labels,
            color_continuous_scale="Blues",
            aspect="auto",
        )

        max_val = matrix.max() if matrix.size > 0 else 1
        for i in range(len(labels)):
            for j in range(len(labels)):
                val = int(matrix[i, j])
                fig.add_annotation(
                    x=labels[j], y=labels[i],
                    text=str(val),
                    showarrow=False,
                    font=dict(color="white" if val > max_val / 2 else "black")
                )
        fig.update_layout(title=title)

        visualization_data = [
            {"name": f"{actual} \u2192 {pred}", "value": int(matrix[i, j])}
            for i, actual in enumerate(labels)
            for j, pred in enumerate(labels)
        ]
        # Single source of truth: the very same matrix rendered into the
        # PDF is shipped to the frontend for interactive rendering.
        extra_options = {
            "confusion_matrix": {
                "labels": [str(l) for l in labels],
                "matrix": [[int(v) for v in row] for row in matrix.tolist()],
            }
        }
        return fig, visualization_data, extra_options

    # Actual vs Predicted (regression)
    if chart_type == "scatter" and x_axis == "actual" and y_axis == "predicted":
        if not ml_results.actual_vs_predicted:
            return None, None, {}
        avp = ml_results.actual_vs_predicted[:500]
        avp_df = pd.DataFrame(avp)
        fig = px.scatter(avp_df, x="actual", y="predicted", opacity=0.6)
        max_val = max(avp_df["actual"].max(), avp_df["predicted"].max())
        min_val = min(avp_df["actual"].min(), avp_df["predicted"].min())
        fig.add_shape(type="line", x0=min_val, y0=min_val, x1=max_val, y1=max_val,
                      line=dict(color="red", dash="dash"))
        fig.update_layout(title=title, xaxis_title=x_label, yaxis_title=y_label)
        # labels = actual (x), data = predicted (y) so the interactive
        # scatter uses real coordinates instead of "Point N" indices.
        visualization_data = [
            {"name": str(float(row["actual"])), "value": float(row["predicted"])}
            for _, row in avp_df.iterrows()
        ]
        return fig, visualization_data, {}

    # Residual distribution
    if chart_type == "histogram" and x_axis == "residual":
        if not ml_results.residuals:
            return None, None, {}
        res_df = pd.DataFrame({"residual": ml_results.residuals})
        fig = px.histogram(res_df, x="residual", nbins=30)
        fig.update_layout(title=title, xaxis_title=x_label, yaxis_title=y_label or "Count")
        visualization_data = histogram_payload(res_df["residual"], nbins=30)
        return fig, visualization_data, {}

    return None, None, {}