"""
Insight Pipeline — v6.1 (FIXED: Lower thresholds, better fallback).
"""

from typing import List, Dict, Any, Tuple, Union
from backend.agents.insights.insight_ranker import _assign_severity
from backend.models.insight import InsightCandidate
from backend.tools.insight_constants import (
    TYPE_PRIORITY,
    MAX_PER_TYPE,
    REDUNDANT_PAIRS,
    MIN_COMPOSITE_SCORE,
    SCORE_ESCALATION_MARGIN,
    MAX_INSIGHTS,
)


def rank_insights(insights: List[InsightCandidate], max_insights: int = None) -> List[InsightCandidate]:
    """Rank candidates using evidence-native signals.

    Feature-importance candidates are normalized against the strongest feature
    in the same candidate set before final selection.
    """
    if not insights:
        return []

    feature_candidates = [
        i for i in insights
        if i.type == "feature_importance"
        and isinstance((i.evidence or {}).get("importance"), (int, float))
    ]
    max_importance = max(
        (float((i.evidence or {}).get("importance", 0) or 0) for i in feature_candidates),
        default=0.0,
    )

    scored = []
    for insight in insights:
        evidence = insight.evidence or {}
        if insight.type == "feature_importance":
            raw = float(evidence.get("importance", 0) or 0)
            relative = raw / max_importance if max_importance > 0 else 0.0
            evidence["relative_importance"] = round(max(0.0, min(1.0, relative)), 4)
            insight.importance_score = evidence["relative_importance"]

        score = _calculate_rank_score(insight)
        evidence["_rank_score"] = score
        evidence["severity"] = _assign_severity(insight)
        scored.append((score, insight))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [insight for _, insight in scored]


def _calculate_rank_score(insight: InsightCandidate) -> float:
    evidence = insight.evidence or {}

    # ML feature importance is a model-native ordering signal. Do not let a
    # p-value on a secondary validation signal promote a weak predictor above
    # a materially stronger predictor from the same model.
    if insight.type == "feature_importance":
        relative = evidence.get("relative_importance")
        if relative is None:
            raw = abs(float(evidence.get("importance", 0) or 0))
            relative = min(1.0, raw / 50.0) if raw > 1.0 else min(1.0, raw)
        relative = min(1.0, max(0.0, float(relative)))

        p_val = evidence.get("p_value")
        stat_sig = 1.0 if isinstance(p_val, (int, float)) and p_val < 0.05 else 0.75
        confidence = getattr(insight, "confidence", 0.5)
        if not isinstance(confidence, (int, float)):
            confidence = 0.5
        business = _business_impact_weight("feature_importance")

        # 80% native importance + small supporting bonuses.
        return round(
            relative * 0.80 + stat_sig * 0.05 + confidence * 0.05 + business * 0.10,
            3,
        )

    p_val = evidence.get("p_value", 0.5)
    if isinstance(p_val, (int, float)):
        if p_val < 0.05:
            stat_sig = 1.0
        elif p_val < 0.1:
            stat_sig = 0.6
        else:
            stat_sig = 0.2
    else:
        stat_sig = 0.5

    effect_size = _extract_effect_size(insight)
    if evidence.get("statistically_significant") is False:
        effect_size *= 0.5

    confidence = getattr(insight, "confidence", 0.5)
    if not isinstance(confidence, (int, float)):
        confidence = 0.5

    business = _business_impact_weight(insight.type)
    type_bonus = {
        "group_difference": 1.0,
        "risk_segment": 0.85,
        "interaction": 0.75,
        "correlation": 0.8,
        "outlier": 1.0
    }
    business *= type_bonus.get(insight.type, 1.0)

    score = stat_sig * 0.35 + effect_size * 0.30 + confidence * 0.20 + business * 0.15

    strength_bonus = {"confirmed": 1.0, "exploratory": 0.7, "weak": 0.4}
    strength = evidence.get("strength", "confirmed")
    score += strength_bonus.get(strength, 0.5) * 0.10

    return round(score, 3)


def _extract_effect_size(insight: InsightCandidate) -> float:
    evidence = insight.evidence or {}

    effect = evidence.get("effect_size")
    if effect is not None:
        return min(1.0, abs(float(effect)))

    corr = evidence.get("correlation")
    if corr is not None:
        return min(1.0, abs(float(corr)))

    gap = evidence.get("gap_percent") or evidence.get("difference_percent") or evidence.get("gap_pct")
    if gap is not None:
        return min(1.0, abs(float(gap)) / 100)

    if insight.type == "feature_importance":
        relative = evidence.get("relative_importance")
        if relative is not None:
            return min(1.0, max(0.0, float(relative)))

    imp = evidence.get("importance")
    if imp is not None:
        imp = abs(float(imp))
        return min(1.0, imp / 50.0) if imp > 1.0 else min(1.0, imp)

    lift = evidence.get("top_lift")
    if lift is not None:
        return min(1.0, max(0, float(lift) - 1.0) / 2.0)

    return 0.3


def _business_impact_weight(insight_type: str) -> float:
    weights = {
        "outlier": 0.75, "risk_segment": 0.75, "group_difference": 1.0,
        "segment": 0.85, "interaction": 0.90, "distribution": 0.75,
        "correlation": 0.65, "feature_importance": 0.65, "data_quality": 0.05
    }
    return weights.get(insight_type, 0.50)


def select_final_insights(
    insights: List[InsightCandidate],
    max_insights: int = None,
    max_per_feature: int = 2,
    return_metadata: bool = False
):
    if not insights:
        return ([], {}) if return_metadata else []

    max_insights = max_insights or MAX_INSIGHTS

    evaluated = []
    for idx, insight in enumerate(insights):
        evidence = insight.evidence or {}
        feature = evidence.get("feature") or evidence.get("column") or evidence.get("group_column")

        feature_key = (
            str(feature).lower().replace("_", " ").strip()
            if feature
            else f"__none_{idx}"
        )

        composite_score = _calculate_composite_score(insight)

        evaluated.append({
            "insight": insight,
            "feature": feature_key,
            "type": insight.type,
            "score": composite_score,
            "priority": TYPE_PRIORITY.get(insight.type, 0),
            "status": "pending",
            "reason": None
        })

    viable = []
    type_counts = {}
    for item in evaluated:
        if item["score"] < MIN_COMPOSITE_SCORE:
            item["status"] = "rejected"
            item["reason"] = f"below threshold ({MIN_COMPOSITE_SCORE})"
            continue

        type_cap = MAX_PER_TYPE.get(item["type"], 999)
        if type_counts.get(item["type"], 0) >= type_cap:
            item["status"] = "rejected"
            item["reason"] = f"type cap ({type_cap})"
            continue

        type_counts[item["type"]] = type_counts.get(item["type"], 0) + 1
        item["status"] = "viable"
        viable.append(item)

    viable.sort(key=lambda x: x["score"], reverse=True)
    selected_items = []
    feature_map = {}

    for item in viable:
        feature_key = item["feature"]
        insight_type = item["type"]
        composite_score = item["score"]
        insight = item["insight"]
        existing = feature_map.get(feature_key, [])

        if any(e["type"] == insight_type for e in existing):
            item["status"] = "rejected"
            item["reason"] = "duplicate type for feature"
            continue

        is_redundant = False
        for e in existing:
            if (e["type"], insight_type) in REDUNDANT_PAIRS:
                if composite_score <= e["score"] * SCORE_ESCALATION_MARGIN:
                    is_redundant = True
                    item["status"] = "rejected"
                    item["reason"] = f"redundant with {e['type']}"
                    break
        if is_redundant:
            continue

        if len(existing) >= max_per_feature:
            lowest = min(existing, key=lambda x: x["priority"])
            if (item["priority"] > lowest["priority"] and 
                composite_score >= lowest["score"] * SCORE_ESCALATION_MARGIN):
                selected_items.remove(lowest)
                existing.remove(lowest)
                lowest["status"] = "replaced"
                lowest["reason"] = f"replaced by {insight_type}"
            else:
                item["status"] = "rejected"
                item["reason"] = f"feature cap ({max_per_feature})"
                continue

        selected_items.append(item)
        existing.append(item)
        feature_map[feature_key] = existing

    selected_items.sort(key=lambda x: x["score"], reverse=True)
    final_selected = []
    overflow = []

    for i, item in enumerate(selected_items):
        if i < max_insights:
            item["status"] = "selected"
            final_selected.append(item["insight"])
        else:
            item["status"] = "overflow"
            item["reason"] = f"beyond max_insights ({max_insights})"
            overflow.append(item)

    if return_metadata:
        metadata = {
            "total_evaluated": len(evaluated),
            "selected_count": len(final_selected),
            "type_breakdown": _count_types(selected_items, "selected"),
            "features_covered": list({item["feature"] for item in selected_items if item["status"] == "selected"}),
            "rejected": [{"insight": item["insight"].title, "type": item["type"], "feature": item["feature"], "score": item["score"], "reason": item["reason"]} for item in evaluated + overflow if item["status"] in ("rejected", "overflow", "replaced")]
        }
        return final_selected, metadata

    return final_selected


def _calculate_composite_score(insight: InsightCandidate) -> float:
    importance = getattr(insight, "importance_score", 0.5)
    confidence = getattr(insight, "confidence", 0.5)
    type_weight = max(0.5, TYPE_PRIORITY.get(insight.type, 3) / 5.0)
    score = importance * confidence * type_weight
    if getattr(insight, "business_interpretation", None):
        score *= 1.05
    return round(min(score, 1.0), 3)


def _count_types(items, status):
    counts = {}
    for item in items:
        if item["status"] == status:
            counts[item["type"]] = counts.get(item["type"], 0) + 1
    return counts