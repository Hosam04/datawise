"""Serialization helpers for the Insights Agent."""
import pandas as pd


def _confidence_label(value):
    """Map numeric or string confidence to frontend labels: high|medium|low."""
    if value is None:
        return "medium"
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("high", "medium", "low"):
            return v
        try:
            value = float(v)
        except ValueError:
            return "medium"
    try:
        score = float(value)
    except (TypeError, ValueError):
        return "medium"
    # Accept both 0-1 and 0-100 scales
    if score > 1.0:
        score = score / 100.0
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def _extract_metrics(evidence):
    """Pull a compact metrics dict the frontend can render as chips."""
    if not isinstance(evidence, dict):
        return {}
    metrics = {}
    key_map = {
        "p_value": "p_value",
        "p": "p_value",
        "correlation": "correlation",
        "r": "correlation",
        "effect_size": "effect_size",
        "importance": "importance",
        "relative_importance": "relative_importance",
        "percentage": "percentage",
        "count": "count",
        "rows_affected": "rows_affected",
        "strength": "strength",
        "score": "score",
    }
    for src, dst in key_map.items():
        if src in evidence and evidence[src] is not None and dst not in metrics:
            val = evidence[src]
            if isinstance(val, float):
                metrics[dst] = round(val, 4) if abs(val) < 10 else round(val, 2)
            elif isinstance(val, (int, str, bool)):
                metrics[dst] = val
    # Nested statistics block
    stats = evidence.get("statistics")
    if isinstance(stats, dict):
        for src, dst in (("p_value", "p_value"), ("correlation", "correlation"), ("mean", "mean")):
            if src in stats and dst not in metrics and stats[src] is not None:
                val = stats[src]
                metrics[dst] = round(float(val), 4) if isinstance(val, (int, float)) else val
    return metrics


def _serialize_finding(insight):
    """Normalize an InsightCandidate (or duck-typed object) for FE + DB.

    Frontend InsightFinding expects:
      title, description, evidence?, confidence?: 'high'|'medium'|'low', metrics?
    Extra fields (type, interpretation, importance_score, confidence_score)
    are kept for DB persistence and richer clients without breaking the UI.
    """
    evidence = getattr(insight, "evidence", None)
    if evidence is None and isinstance(insight, dict):
        evidence = insight.get("evidence")
    if not isinstance(evidence, dict):
        evidence = {}

    raw_confidence = (
        getattr(insight, "confidence", None)
        if not isinstance(insight, dict)
        else insight.get("confidence")
    )
    if raw_confidence is None:
        raw_confidence = evidence.get("confidence")

    title = getattr(insight, "title", None) if not isinstance(insight, dict) else insight.get("title")
    finding = getattr(insight, "finding", None) if not isinstance(insight, dict) else (
        insight.get("finding") or insight.get("description")
    )
    interpretation = (
        getattr(insight, "business_interpretation", None)
        if not isinstance(insight, dict)
        else insight.get("business_interpretation") or insight.get("interpretation")
    )
    insight_type = getattr(insight, "type", None) if not isinstance(insight, dict) else insight.get("type")
    importance = (
        getattr(insight, "importance_score", None)
        if not isinstance(insight, dict)
        else insight.get("importance_score")
    )

    metrics = _extract_metrics(evidence)

    return {
        "title": title or "",
        "description": finding or "",
        "finding": finding or "",
        "interpretation": interpretation,
        "type": insight_type or "key_finding",
        "evidence": evidence,
        "confidence": _confidence_label(raw_confidence),
        "confidence_score": raw_confidence if isinstance(raw_confidence, (int, float)) else None,
        "importance_score": importance,
        "metrics": metrics or None,
    }