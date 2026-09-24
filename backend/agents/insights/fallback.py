"""Fallback insight generation for the Insights Agent."""
import pandas as pd
import numpy as np

from backend.agents.insights.constants import TYPE_LABELS


class _Insight:
    """Simple insight class for fallback generation."""
    def __init__(self, type, title, finding, evidence):
        self.type = type
        self.title = title
        self.finding = finding
        self.evidence = evidence


def _generate_fallback_insights(evidence, target):
    """Generate fallback insights when the main pipeline fails."""
    insights = []
    ta = evidence.get("target_analysis", {})

    if ta and ta.get("mean") is not None:
        insights.append(_Insight(
            "target_summary",
            f"{target} Overview",
            f"{target} averages {ta['mean']:.2f} (std: {ta['std']:.2f}, range {ta['min']:.2f}–{ta['max']:.2f}).",
            {"confidence": 1.0}
        ))
    elif ta and ta.get("type") == "categorical":
        insights.append(_Insight(
            "distribution",
            f"{target} Distribution",
            f"{target} is categorical with {ta['unique_values']} categories. Most common: {ta['top_category']} ({ta['top_category_pct']:.1f}%).",
            {"confidence": 1.0, "column": target, "unique_values": ta.get("unique_values"), "top_value": ta.get("top_category"), "top_pct": ta.get("top_category_pct")}
        ))

    cat_analysis = evidence.get("categorical_target_analysis", {})

    dist = cat_analysis.get("distribution", {})
    if dist and not any(i.type == "distribution" for i in insights):
        top_values = dist.get("top_values", {})
        top_val = list(top_values.keys())[0] if top_values else "unknown"
        top_count = list(top_values.values())[0] if top_values else 0
        total = sum(top_values.values()) if top_values else 0
        top_pct = round(top_count / total * 100, 1) if total else 0
        insights.append(_Insight(
            "distribution",
            f"{target} spans {dist.get('unique_values', 0)} categories",
            f"{target} has {dist.get('unique_values', 0)} categories with '{top_val}' being most common ({top_pct}%).",
            {"confidence": 0.90, "column": target, "unique_values": dist.get("unique_values"), "top_value": top_val, "top_pct": top_pct}
        ))

    associations = cat_analysis.get("associations", {})
    for col, data in associations.items():
        if not data.get("significant"):
            continue
        cramers = data.get("cramers_v", 0)
        if cramers < 0.20:
            continue
        insights.append(_Insight(
            "group_difference",
            f"Key Segment: {col} associated with {target}",
            f"{col} shows significant association with {target} (Cramér's V = {cramers:.3f}).",
            {"confidence": 0.80, "group_column": col, "cramers_v": cramers, "p_value": data.get("p_value"), "statistically_significant": True}
        ))

    text_by_cat = cat_analysis.get("text_by_category", {})
    for text_col, stats in text_by_cat.items():
        if not stats or len(stats) < 2:
            continue
        max_cat = max(stats.items(), key=lambda x: x[1].get("avg_length", 0))
        min_cat = min(stats.items(), key=lambda x: x[1].get("avg_length", 0))
        max_len = max_cat[1].get("avg_length", 0)
        min_len = min_cat[1].get("avg_length", 0)
        if max_len > min_len * 1.15:
            diff_pct = round((max_len - min_len) / max(min_len, 1) * 100, 1)
            insights.append(_Insight(
                "segment",
                f"{text_col} length varies by {target} category",
                f"{max_cat[0]} entries average {max_len:.0f} chars vs {min_cat[0]} at {min_len:.0f} chars ({diff_pct}% longer).",
                {"confidence": 0.75, "column": text_col, "max_category": max_cat[0], "min_category": min_cat[0], "difference_pct": diff_pct}
            ))

    tc = evidence.get("target_correlations", {})
    if not tc:
        fi = evidence.get("feature_importance", {})
        top5 = fi.get("top_5", []) if isinstance(fi, dict) else []
        for item in top5:
            if isinstance(item, dict) and "feature" in item:
                tc[item["feature"]] = item.get("importance", 0)

        if isinstance(tc, dict):
            top = sorted(
                [(k, v) for k, v in tc.items() if isinstance(v, (int, float)) and pd.notna(v)],
                key=lambda x: abs(x[1]), reverse=True
            )[:3]
            for col, val in top:
                if abs(val) < 0.30:
                    continue
                insights.append(_Insight(
                    "correlation",
                    f"Strong Predictor: {col}",
                    f"{col} correlates with {target} at {abs(val):.3f}.",
                    {"confidence": 0.9 if abs(val) > 0.5 else 0.7}
                ))

    fi = evidence.get("feature_importance", {})
    top5 = fi.get("top_5", []) if isinstance(fi, dict) else []
    if top5:
        top_feat = top5[0]
        if top_feat.get("importance", 0) >= 0.30:
            insights.append(_Insight(
                "feature_importance",
                f"Top Feature: {top_feat['feature']}",
                f"{top_feat['feature']} shows highest predictive signal (score: {top_feat['importance']:.3f}).",
                {"confidence": 0.85}
            ))

    ml_analysis = evidence.get("ml_analysis", {})
    if ml_analysis:
        ml_features = ml_analysis.get("top_predictive_features", [])
        if ml_features:
            top_ml = ml_features[0]
            insights.append(_Insight(
                "feature_importance",
                f"ML Top Predictor: {top_ml['feature']}",
                f"According to {ml_analysis.get('selected_model', 'ML model')}, {top_ml['feature']} is the most important predictor (importance: {top_ml['importance']:.3f}).",
                {"confidence": 0.85, "source": "ml_model"}
            ))

        metrics = ml_analysis.get("metrics", {})
        if metrics.get("r2") is not None:
            insights.append(_Insight(
                "model_performance",
                f"ML Model R² = {metrics['r2']:.3f}",
                f"The {ml_analysis.get('selected_model')} model explains {metrics['r2']:.1%} of variance in {target}.",
                {"confidence": 0.80, "r2": metrics['r2'], "rmse": metrics.get('rmse')}
            ))
        elif metrics.get("accuracy") is not None:
            insights.append(_Insight(
                "model_performance",
                f"ML Model Accuracy = {metrics['accuracy']:.1%}",
                f"The {ml_analysis.get('selected_model')} model achieves {metrics['accuracy']:.1%} accuracy on held-out test data.",
                {"confidence": 0.80, "accuracy": metrics['accuracy'], "f1": metrics.get('f1')}
            ))

    dq = evidence.get("data_quality", {})
    if isinstance(dq, dict) and dq.get("missing_count", 0) > 0:
        insights.append(_Insight(
            "data_quality",
            "Data Quality Note",
            f"Dataset contains {dq.get('missing_count', 0)} missing values ({dq.get('missing_pct', 0):.1f}%).",
            {"confidence": 1.0}
        ))

    return insights