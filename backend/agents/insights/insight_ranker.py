from typing import List
from backend.models.insight import InsightCandidate


# RAISED THRESHOLDS
MIN_CORRELATION_KEEP = 0.35
MIN_FEATURE_KEEP = 0.35
MIN_GROUP_DIFF_KEEP = 30.0


def _safe_float(val, default=0.0):
    if val is None:
        return default
    try:
        f = float(val)
        return f if f == f else default  # NaN check
    except (TypeError, ValueError):
        return default


def _assign_severity(insight: InsightCandidate) -> str:
    ev = insight.evidence or {}

    # FIX 3: unreliable percent gap (near-zero baseline) can never be critical
    if ev.get("gap_reliability") == "low_baseline":
        return "moderate"

    p = ev.get("p_value")
    not_significant = (ev.get("statistically_significant") is False) or (
        p is not None and p >= 0.05
    )
    diff = abs(_safe_float(ev.get("difference_percent"))
               or _safe_float(ev.get("gap_percent"))
               or _safe_float(ev.get("gap_pct"))
               or _safe_float(ev.get("segment_gap")))

    if insight.type == "outlier":
        sev = ev.get("severity")
        return "strong" if sev == "severe" else "moderate" if sev in ("moderate", "mild") else "weak"

    # FIX 4: dedicated severity ladder for feature_importance (ML evidence has no p-value)
    if insight.type == "feature_importance":
        imp = _safe_float(ev.get("relative_importance"), None)
        if imp is None:
            raw_imp = _safe_float(ev.get("importance"))
            imp = min(1.0, raw_imp / 50.0) if raw_imp > 1.0 else min(1.0, raw_imp)
        imp_n = min(1.0, abs(imp))
        corr = abs(_safe_float(ev.get("correlation")))
        cramers = abs(_safe_float(ev.get("cramers_v")))
        effect = max(imp_n, corr, cramers)

        if not_significant:
            # validated but NOT significant → cap by effect size only
            return "moderate" if effect >= 0.5 else "weak"
        if effect >= 0.5:
            return "strong"
        if effect >= 0.2:
            return "moderate"
        return "weak"

    if insight.type == "interaction":
        return "moderate" if (p is not None and p < 0.05) else "weak"

    # Generic ladder (group_difference / risk_segment / segment / correlation / distribution)
    cramers = abs(_safe_float(ev.get("cramers_v")))
    effect = max(_extract_effect_size(insight), min(1.0, diff / 100.0), cramers)

    if diff >= 100 and (p is None or p < 0.01):
        return "critical"
    if p is not None and p < 0.01 and effect >= 0.4:
        return "strong"
    if (p is not None and p < 0.05) or effect >= 0.2:
        return "moderate"
    return "weak"


def rank_insights(insights: List[InsightCandidate], max_insights: int = None) -> List[InsightCandidate]:
    """Rank candidates while preserving the native ordering of ML importances.

    For feature-importance candidates, raw model importances are normalized
    against the strongest feature in the SAME candidate set. This prevents
    confidence/business bonuses from making a weak feature outrank the
    model's dominant feature.
    """
    if not insights:
        return []

    feature_candidates = [
        i for i in insights
        if i.type == "feature_importance"
        and _safe_float((i.evidence or {}).get("importance")) >= 0
    ]
    max_raw = max(
        (_safe_float((i.evidence or {}).get("importance")) for i in feature_candidates),
        default=0.0,
    )

    scored = []
    for insight in insights:
        if insight.type == "feature_importance":
            ev = dict(insight.evidence or {})
            raw = max(0.0, _safe_float(ev.get("importance")))
            # The extractor already computes a within-candidate-set relative
            # importance. Prefer it when present; only derive it from raw
            # values as a fallback. This prevents stale/duplicate evidence
            # from making a weaker feature outrank the dominant feature.
            candidate_relative = _safe_float(ev.get("relative_importance"), -1.0)
            if 0.0 <= candidate_relative <= 1.0:
                relative = candidate_relative
            elif max_raw > 0:
                relative = raw / max_raw
            else:
                relative = 0.0
            ev["relative_importance"] = round(min(1.0, max(0.0, relative)), 4)
            ev["importance_scale"] = "within_model_relative"
            insight.evidence = ev

        score = _calculate_rank_score(insight)
        insight.evidence["_rank_score"] = score
        insight.evidence["severity"] = _assign_severity(insight)
        scored.append((score, insight))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [insight for _, insight in scored]


def _calculate_rank_score(insight: InsightCandidate) -> float:
    """Rank insights using evidence on its native scale.

    ML feature importance is model-specific and often not normalized.  For
    feature-importance insights, ``relative_importance`` is the primary
    ranking signal; raw importances must never saturate at 1.0 merely because
    they are greater than one.
    """
    evidence = insight.evidence or {}

    if insight.type == "feature_importance":
        rel = evidence.get("relative_importance")
        if rel is None:
            raw = abs(_safe_float(evidence.get("importance")))
            rel = min(1.0, raw / 50.0) if raw > 1.0 else min(1.0, raw)
        rel = min(1.0, max(0.0, _safe_float(rel)))

        confidence = _safe_float(getattr(insight, "confidence", 0.5), 0.5)
        p_val = evidence.get("p_value")
        stat_sig = 1.0 if isinstance(p_val, (int, float)) and p_val < 0.05 else 0.75
        business = _business_impact_weight(insight.type)

        # Keep model importance dominant. Statistical/business bonuses must
        # not be able to promote a weak predictor above a materially stronger
        # predictor from the same model.
        score = rel * 0.80 + stat_sig * 0.05 + confidence * 0.05 + business * 0.10
        return round(score, 3)

    # 1. Statistical significance (0.35)
    p_val = evidence.get("p_value")
    if isinstance(p_val, (int, float)):
        if p_val < 0.05:
            stat_sig = 1.0
        elif p_val < 0.1:
            stat_sig = 0.6
        else:
            stat_sig = 0.2
    else:
        cramers = _safe_float(evidence.get("cramers_v"))
        stat_sig = 0.85 if cramers >= 0.20 else 0.5

    # 2. Effect size (0.30)
    effect_size = _extract_effect_size(insight)
    if evidence.get("statistically_significant") is False:
        effect_size *= 0.5

    # 3. Confidence (0.20)
    confidence = getattr(insight, "confidence", 0.5)
    if not isinstance(confidence, (int, float)):
        confidence = 0.5

    # 4. Business impact (0.15)
    business = _business_impact_weight(insight.type)
    type_bonus = {
        "group_difference": 1.0, "risk_segment": 0.85,
        "interaction": 0.75, "correlation": 0.8, "outlier": 1.0
    }
    business *= type_bonus.get(insight.type, 1.0)

    score = stat_sig * 0.35 + effect_size * 0.30 + confidence * 0.20 + business * 0.15
    strength_bonus = {"confirmed": 1.0, "exploratory": 0.7, "weak": 0.4}
    score += strength_bonus.get(evidence.get("strength", "confirmed"), 0.5) * 0.10
    return round(score, 3)


def _extract_effect_size(insight: InsightCandidate) -> float:
    evidence = insight.evidence or {}

    effect = evidence.get("effect_size")
    if effect is not None:
        return min(1.0, abs(_safe_float(effect)))

    corr = evidence.get("correlation")
    if corr is not None:
        return min(1.0, abs(_safe_float(corr)))

    gap = (evidence.get("gap_percent") or evidence.get("difference_percent")
           or evidence.get("gap_pct"))
    if gap is not None:
        return min(1.0, abs(_safe_float(gap)) / 100)

    imp = evidence.get("importance")
    if imp is not None:
        imp = abs(_safe_float(imp))
        # FIX 2: normalize raw ML importance (>1) to the 0..1 scale
        return min(1.0, imp / 50.0) if imp > 1.0 else min(1.0, imp)

    lift = evidence.get("top_lift")
    if lift is not None:
        return min(1.0, max(0, _safe_float(lift) - 1.0) / 2.0)

    return 0.3


def _business_impact_weight(insight_type: str) -> float:
    weights = {
        "outlier": 0.75,
        "risk_segment": 0.75,
        "group_difference": 1.0,
        "segment": 0.85,
        "interaction": 0.90,
        "distribution": 0.75,
        "correlation": 0.65,
        "feature_importance": 0.65,
        "data_quality": 0.05
    }
    return weights.get(insight_type, 0.50)


# Gatekeeper function matching statistical_validator
def _should_keep_insight(insight: InsightCandidate) -> bool:
    evidence = insight.evidence or {}

    if insight.type == "group_difference":
        p_value = evidence.get("p_value")
        diff = _safe_float(evidence.get("difference_percent"))
        high_count = _safe_float(evidence.get("highest_count"))
        low_count = _safe_float(evidence.get("lowest_count"))

        if p_value is not None and p_value < 0.05 and abs(diff) >= MIN_GROUP_DIFF_KEEP:
            return True
        if diff >= 70 and high_count >= 50 and low_count >= 50 and p_value is not None and p_value < 0.1:
            return True
        return False

    if insight.type == "correlation":
        return abs(_safe_float(evidence.get("correlation"))) >= MIN_CORRELATION_KEEP

    if insight.type == "feature_importance":
        return _safe_float(evidence.get("importance")) >= MIN_FEATURE_KEEP

    if insight.type == "risk_segment":
        p_value = evidence.get("p_value")
        lift = _safe_float(evidence.get("top_lift"))
        if p_value is not None and p_value < 0.05:
            return True
        if lift >= 1.5:
            return True
        return False

    if insight.type == "interaction":
        p_value = evidence.get("p_value")
        f_stat = _safe_float(evidence.get("f_statistic"))
        if p_value is not None and p_value < 0.05:
            return True
        if f_stat >= 3.0:
            return True
        return False

    return True