"""
Insight extraction layer — v5.5 (FIXED: Always include compared_values + Filter text columns).
"""

from typing import Dict, Any, List
from backend.models.insight import InsightCandidate
import numpy as np

from backend.tools.insight_constants import (
    BASE_MIN_GROUP_DIFF_PCT,
    BASE_MIN_CORRELATION,
    BASE_MIN_FEATURE_IMPORTANCE,
    BASE_MIN_SEGMENT_GAP,
    DIVERSITY_CAPS,
)


def _is_outlier_flag_column(column_name: str) -> bool:
    """Check if a column name indicates an outlier flag column.

    These are meta-features produced by the cleaning pipeline (e.g. *_OutlierFlag)
    that should be excluded from insight generation as they are circular.
    """
    if not column_name:
        return False
    col_lower = str(column_name).lower()
    if col_lower.endswith("_outlierflag") or col_lower.endswith("_outlier_flag"):
        return True
    if "outlier" in col_lower and "flag" in col_lower:
        return True
    return False


def _is_target_related_outlier_flag(column_name: str, target_name: str) -> bool:
    """Check if a column is a target-related outlier/flag column.

    This catches target-derived flags like 'target_OutlierFlag' or 'target_Flag'
    that are circular when the target is the analysis target.
    """
    if not column_name or not target_name:
        return False
    col_lower = str(column_name).lower()
    target_lower = str(target_name).lower()
    if not col_lower.startswith(target_lower):
        return False
    # Target-specific: either "flag" OR "outlier" (not both required)
    if "flag" in col_lower or "outlier" in col_lower:
        return True
    return False


def _is_text_column(evidence: Dict[str, Any], col: str) -> bool:
    """Check if column is free-text (high cardinality object)."""
    if not col:
        return False
    semantics = evidence.get("column_semantics", {})
    col_info = semantics.get(col, {})
    inferred = col_info.get("inferred_type", "")
    unique_pct = col_info.get("unique_pct", 0)
    # Text if explicitly text OR object with >5% unique values
    if inferred == "text":
        return True
    if inferred == "other" and unique_pct > 5:
        return True
    if "column_types" in evidence:
        col_type = evidence["column_types"].get(col, "")
        if col_type in ("object", "string"):
            # High cardinality suggests free text
            if unique_pct > 5:
                return True
    
    return False


def generate_insight_candidates(evidence: Dict[str, Any]) -> List[InsightCandidate]:
    candidates = []
    candidates.extend(extract_outlier_insights(evidence))
    candidates.extend(extract_risk_segment_insights(evidence))
    candidates.extend(extract_group_difference_insights(evidence))
    candidates.extend(extract_correlation_insights(evidence))
    candidates.extend(extract_interaction_insights(evidence))
    candidates.extend(extract_segment_insights(evidence))
    candidates.extend(extract_feature_importance_insights(evidence))
    candidates.extend(extract_distribution_insights(evidence))
    candidates.extend(extract_categorical_target_insights(evidence))
    candidates.extend(extract_target_analysis_insights(evidence))
    candidates.extend(extract_data_quality_insights(evidence))

    candidates = [c for c in candidates if _is_actionable_insight(c)]

    if not candidates:
        candidates = _force_descriptive_insights(evidence)

    candidates.sort(key=lambda x: x.importance_score, reverse=True)
    candidates = _apply_diversity_control(candidates)

    return candidates


def _detect_target_from_correlations(correlations):
    if not correlations:
        return None
    items = []
    if isinstance(correlations, dict):
        items = list(correlations.items())
    elif isinstance(correlations, list):
        items = [(x.get("feature"), x.get("correlation")) for x in correlations]
    best = None
    best_strength = -1
    for feature, corr in items:
        if corr is None or feature is None:
            continue
        strength = abs(float(corr))
        if strength > best_strength:
            best_strength = strength
            best = feature
    return best


def _force_descriptive_insights(evidence: Dict[str, Any]) -> List[InsightCandidate]:
    insights = []
    target = evidence.get("target_detection", {}).get("target_column")
    stats = evidence.get("descriptive_stats", {})

    if target and target in stats:
        t_stat = stats[target]
        insights.append(InsightCandidate(
            type="distribution",
            title=f"{target} averages {t_stat.get('mean', 'N/A')} with std {t_stat.get('std', 'N/A')}",
            finding=f"{target} has mean={t_stat.get('mean')} and ranges from {t_stat.get('min')} to {t_stat.get('max')}.",
            business_interpretation=f"The target variable {target} shows a spread of {t_stat.get('min')} to {t_stat.get('max')}.",
            evidence={
                "column": target,
                "mean": t_stat.get("mean"), "std": t_stat.get("std"),
                "min": t_stat.get("min"), "max": t_stat.get("max")
            },
            confidence=0.85, importance_score=0.50
        ))

    correlations = evidence.get("target_correlations", {})
    if isinstance(correlations, dict) and correlations:
        top_feature = max(correlations.items(), key=lambda x: abs(x[1]))
        insights.append(InsightCandidate(
            type="correlation",
            title=f"{top_feature[0]} shows strongest relationship with {target}",
            finding=f"{top_feature[0]} has correlation of {top_feature[1]:.3f} with {target}.",
            business_interpretation=f"Among all features, {top_feature[0]} shows the strongest linear association with {target}.",
            evidence={"feature": top_feature[0], "correlation": top_feature[1]},
            confidence=0.60, importance_score=abs(top_feature[1])
        ))

    # FIX: Guard against empty deep_segmented_analysis to avoid ValueError on max()
    deep = evidence.get("deep_segmented_analysis", {})
    if deep:
        top_col = max(deep.items(), key=lambda x: abs(x[1].get("key_insight", {}).get("gap_pct", 0)))
        gap = top_col[1].get("key_insight", {}).get("gap_pct", 0)
        if gap:
            insights.append(InsightCandidate(
                type="group_difference",
                title=f"{top_col[0]} shows {abs(gap):.0f}% gap across segments",
                finding=f"Subgroups within {top_col[0]} vary by {abs(gap):.1f}% in {target}.",
                business_interpretation=f"{top_col[0]} creates meaningful segmentation in {target} outcomes.",
                evidence={
                    "group_column": top_col[0],
                    "difference_percent": gap,
                    "highest_group": top_col[1].get("key_insight", {}).get("highest_group"),
                    "lowest_group": top_col[1].get("key_insight", {}).get("lowest_group"),
                    "compared_values": [
                        top_col[1].get("key_insight", {}).get("highest_group"),
                        top_col[1].get("key_insight", {}).get("lowest_group")
                    ],
                    "groups": [
                        top_col[1].get("key_insight", {}).get("highest_group"),
                        top_col[1].get("key_insight", {}).get("lowest_group")
                    ]
                },
                confidence=0.70, importance_score=min(0.80, abs(gap) / 100)
            ))

    return insights


def _calculate_confidence(stat_confidence, sample_size=0, effect_size=0.0, p_value=None):
    base_part = min(0.50, max(0.10, stat_confidence * 0.50))
    sample_part = 0.25 if sample_size >= 1000 else 0.22 if sample_size >= 500 else 0.18 if sample_size >= 100 else 0.12 if sample_size >= 30 else 0.05
    effect_part = min(0.20, abs(effect_size) * 0.25)
    total = base_part + sample_part + effect_part
    if p_value is not None and p_value > 0.05:
        total *= 0.60
    return round(min(0.90, max(0.10, total)), 2)


def extract_correlation_insights(evidence: Dict[str, Any]) -> List[InsightCandidate]:
    insights = []
    target = evidence.get("target_detection", {}).get("target_column") or evidence.get("feature_importance", {}).get("target") or _detect_target_from_correlations(evidence.get("target_correlations", {}))
    correlations = evidence.get("target_correlations", {})

    if isinstance(correlations, dict):
        items = list(correlations.items())
    elif isinstance(correlations, list):
        items = [(x.get("feature"), x.get("correlation")) for x in correlations]
    else:
        return insights

    for feature, corr in items:
        if str(feature).strip().lower() == str(target).strip().lower() or corr is None:
            continue
        try:
            corr_float = float(corr)
            if not np.isfinite(corr_float):
                continue
        except (TypeError, ValueError):
            continue

        strength = abs(corr_float)
        if strength < BASE_MIN_CORRELATION:
            continue

        relation = "strong" if strength >= 0.5 else "moderate" if strength >= 0.35 else "weak"
        direction = "positive" if corr_float > 0 else "negative"

        insights.append(InsightCandidate(
            type="correlation",
            title=f"{feature} shows {relation} {direction} relationship with {target}",
            finding=f"{feature} has a {relation} {direction} correlation ({corr_float:.3f}) with {target}.",
            business_interpretation=f"{feature} systematically aligns with {target} in a {direction} direction, offering predictive signal.",
            evidence={"feature": feature, "correlation": round(corr_float, 3), "relation_strength": relation, "direction": direction},
            confidence=_calculate_confidence(strength, effect_size=strength),
            importance_score=round(min(0.90, max(0.15, strength)), 2)
        ))

    return insights


def extract_group_difference_insights(evidence: Dict[str, Any]) -> List[InsightCandidate]:
    insights = []
    target = evidence.get("target_detection", {}).get("target_column") or "target"
    groups = evidence.get("group_analysis", {})

    if not groups:
        groups = evidence.get("deep_segmented_analysis", {})

    target_lower = str(target).lower() if target else ""
    for column, stats in groups.items():
        if not isinstance(stats, dict):
            continue

        # === FIX: Skip free-text columns ===
        if _is_text_column(evidence, column):
            continue

        # Skip ALL derived outlier / annotation flags (meta-features).
        # Target-derived flags are circular; feature-derived flags are noisy.
        if _is_outlier_flag_column(column):
            continue
        if target_lower and _is_target_related_outlier_flag(column, target):
            continue

        values = stats.get("groups", stats)
        if isinstance(values, dict) and len(values) > 50:
            continue

        means = []
        for group, group_stats in values.items():
            if isinstance(group_stats, dict):
                mean = group_stats.get("mean")
                count = group_stats.get("count", 0)
                if mean is not None:
                    try:
                        means.append((group, float(mean), int(count)))
                    except (TypeError, ValueError):
                        continue

        if len(means) < 2:
            continue

        highest = max(means, key=lambda x: x[1])
        lowest = min(means, key=lambda x: x[1])

        if lowest[1] == 0:
            continue

        if highest[2] < 15 or lowest[2] < 15:
            continue

        difference = ((highest[1] - lowest[1]) / lowest[1]) * 100

        if abs(difference) < BASE_MIN_GROUP_DIFF_PCT:
            continue

        confidence = _calculate_confidence(
            stat_confidence=0.75,
            sample_size=highest[2] + lowest[2],
            effect_size=abs(difference) / 100.0
        )

        # === FIX: Always include compared_values and groups for specific t-test ===
        evidence_dict = {
            "feature": column,  # Crucial for deduplication in select_final_insights
            "group_column": column,
            "highest_group": highest[0], "highest_value": round(highest[1], 2), "highest_count": highest[2],
            "lowest_group": lowest[0], "lowest_value": round(lowest[1], 2), "lowest_count": lowest[2],
            "difference_percent": round(difference, 2),
            "p_value": None,
            # Always include top 2 for specific comparison
            "compared_values": [highest[0], lowest[0]],
            "groups": [highest[0], lowest[0]],
        }

        insights.append(InsightCandidate(
            type="group_difference",
            title=f"{column}: {highest[0]} shows {abs(difference):.0f}% higher {target} than {lowest[0]}",
            finding=f"{highest[0]} averages {highest[1]:.2f} (n={highest[2]}) vs {lowest[0]} at {lowest[1]:.2f} (n={lowest[2]}).",
            business_interpretation=f"{column} creates a {abs(difference):.0f}% spread in {target} between {highest[0]} and {lowest[0]}.",
            evidence=evidence_dict,
            confidence=confidence,
            importance_score=min(0.95, abs(difference) / 100)
        ))

    return insights


def extract_feature_importance_insights(evidence: Dict[str, Any]) -> List[InsightCandidate]:
    insights = []
    target = evidence.get("target_detection", {}).get("target_column") or evidence.get("feature_importance", {}).get("target") or _detect_target_from_correlations(evidence.get("target_correlations", {}))

    all_features = []
    feature_data = evidence.get("feature_importance", {})
    features = []
    if isinstance(feature_data, dict):
        features = feature_data.get("top_5", []) or feature_data.get("features", [])
    elif isinstance(feature_data, list):
        features = feature_data

    for item in features:
        if not isinstance(item, dict):
            continue
        feature = item.get("feature")
        importance = item.get("importance")
        if feature is None or feature == target:
            continue
        try:
            all_features.append((feature, float(importance or 0)))
        except (TypeError, ValueError):
            continue

    if not all_features:
        correlations = evidence.get("target_correlations", {})
        if isinstance(correlations, dict):
            for feature, corr in correlations.items():
                if feature == target:
                    continue
                try:
                    all_features.append((feature, abs(float(corr))))
                except (TypeError, ValueError):
                    continue

    all_features.sort(key=lambda x: x[1], reverse=True)

    # ML tree importances are model-specific raw magnitudes and are not
    # probabilities.  Ranking them against each other requires normalization
    # within this model's returned feature set; otherwise every value > 1
    # saturates the candidate score at 1.0 and a weak feature can outrank the
    # genuinely dominant feature.
    max_importance = max((importance for _, importance in all_features), default=0.0)

    for feature, importance in all_features[:5]:
        if importance < BASE_MIN_FEATURE_IMPORTANCE:
            continue

        if max_importance > 0:
            imp_n = min(1.0, max(0.0, importance / max_importance))
        else:
            imp_n = 0.0
        strength = "strong" if imp_n >= 0.5 else "moderate" if imp_n >= 0.2 else "weak"

        insights.append(InsightCandidate(
            type="feature_importance",
            title=f"{feature} shows {strength} predictive importance",
            finding=f"{feature} has model importance of {importance:.4f} for predicting {target}.",
            business_interpretation=f"{feature} carries {strength} predictive signal for {target} and should be considered in modeling.",
            evidence={
                "feature": feature,
                "importance": importance,
                "relative_importance": round(imp_n, 4),
                "importance_scale": "within_model_relative",
            },
            confidence=_calculate_confidence(importance, effect_size=imp_n),
            importance_score=round(imp_n, 4)
        ))

    return insights


def extract_risk_segment_insights(evidence: Dict[str, Any]) -> List[InsightCandidate]:
    insights = []
    deep = evidence.get("deep_segmented_analysis", {})
    target = evidence.get("target_detection", {}).get("target_column")
    target_lower = str(target).lower() if target else ""

    for column, data in deep.items():
        # === FIX: Skip free-text columns ===
        if _is_text_column(evidence, column):
            continue

        # Skip ALL derived outlier / annotation flags — meta-features that
        # produce noisy risk-segment insights.
        if _is_outlier_flag_column(column):
            continue
        if target_lower and _is_target_related_outlier_flag(column, target):
            continue

        key = data.get("key_insight", {})
        gap = key.get("gap_pct")

        if gap is None or abs(gap) < BASE_MIN_GROUP_DIFF_PCT:
            continue

        highest_group = key.get("highest_group")
        lowest_group = key.get("lowest_group")
        lift = 1.0 + abs(gap) / 100.0 if gap else 1.0

        insights.append(InsightCandidate(
            type="risk_segment",
            title=f"{column} contains high-risk segments",
            finding=f"Subgroups in {column} show {abs(gap):.1f}% gap in target values.",
            business_interpretation=f"{column} segments into distinct risk tiers, enabling targeted intervention.",
            evidence={
                "column": column,
                "highest_group": highest_group,
                "lowest_group": lowest_group,
                "gap_percent": gap,
                "top_lift": round(lift, 2),
                "top_category": highest_group,
                "gap_reliability": key.get("gap_reliability"),
            },
            confidence=_calculate_confidence(0.75, effect_size=abs(gap) / 100.0),
            importance_score=min(1.0, abs(gap) / 100)
        ))

    return insights


def extract_outlier_insights(evidence: Dict[str, Any]) -> List[InsightCandidate]:
    insights = []
    outliers = evidence.get("outliers", {})
    target = evidence.get("target_detection", {}).get("target_column")

    if not target or target not in outliers:
        return insights

    target_outliers = outliers.get(target, {})
    iqr_data = target_outliers.get("iqr_method", {}) or {}
    count = iqr_data.get("count", target_outliers.get("count", target_outliers.get("outlier_count", 0)))
    pct = iqr_data.get("pct", target_outliers.get("pct",
        target_outliers.get("percentage", target_outliers.get("outlier_pct", 0))))
    severity = target_outliers.get("severity")
    if not severity:
        severity = "severe" if pct >= 10 else "moderate" if pct >= 5 else "mild" if pct >= 1 else "minimal"

    if severity in ("none", "minimal") or count < 5 or pct < 2.0:
        return insights

    insights.append(InsightCandidate(
        type="outlier",
        title=f"High {target} concentrated in {count} records ({pct}%)",
        finding=f"{count} records ({pct}%) show unusually high {target} values.",
        business_interpretation=f"A concentrated high-risk group of {count} records may require investigation.",
        evidence={"outlier_count": count, "outlier_pct": pct, "severity": severity, "column": target},
        confidence=_calculate_confidence(0.85, effect_size=pct / 100.0),
        importance_score=0.75 if severity == "severe" else 0.55 if severity == "moderate" else 0.35
    ))

    return insights


def extract_interaction_insights(evidence: Dict[str, Any]) -> List[InsightCandidate]:
    insights = []
    correlations = evidence.get("target_correlations", {})
    deep = evidence.get("deep_segmented_analysis", {})

    if not isinstance(correlations, dict) or not deep:
        return insights

    for col, data in deep.items():
        # === FIX: Skip free-text columns ===
        if _is_text_column(evidence, col):
            continue

        corr = correlations.get(col, 0)
        if abs(corr) < 0.15:
            gap = data.get("key_insight", {}).get("gap_pct")
            if gap and abs(gap) > 15:
                partner = None
                partner_corr = 0
                for other_col, other_corr in correlations.items():
                    if other_col != col and abs(other_corr) > partner_corr:
                        partner_corr = abs(other_corr)
                        partner = other_col

                interaction_cols = [col]
                if partner:
                    interaction_cols.append(partner)

                insights.append(InsightCandidate(
                    type="interaction",
                    # FIX: Descriptive phrasing instead of causal "hidden effect"
                    title=f"{col} shows substantial subgroup variation despite weak overall correlation",
                    finding=f"While the overall linear correlation is weak (r={corr:.2f}), subgroups within {col} differ by up to {abs(gap):.0f}% in the target variable.",
                    business_interpretation=f"The relationship between {col} and the target is non-linear or highly dependent on specific subgroups, rather than following a simple overall trend.",
                    evidence={
                        "column": col,
                        "overall_correlation": corr,
                        "segment_gap": float(gap),
                        "interaction_columns": interaction_cols,
                        "f_statistic": None,
                        "p_value": None,
                    },
                    confidence=_calculate_confidence(0.65, effect_size=abs(gap) / 100.0),
                    importance_score=0.60
                ))

    return insights


def extract_segment_insights(evidence: Dict[str, Any]) -> List[InsightCandidate]:
    insights = []
    segments = evidence.get("top_segments", {})

    if not segments:
        return insights

    for col, data in segments.items():
        # === FIX: Skip free-text columns ===
        if _is_text_column(evidence, col):
            continue

        gap = data.get("gap_pct")
        if not gap or abs(gap) < BASE_MIN_SEGMENT_GAP:
            continue

        high = data.get("highest_quartile", {})
        low = data.get("lowest_quartile", {})

        insights.append(InsightCandidate(
            type="segment",
            title=f"{col} quartiles show {abs(gap):.0f}% target gap",
            finding=f"Top quartile ({high.get('range')}) averages {high.get('mean_target')} vs bottom ({low.get('range')}) at {low.get('mean_target')}.",
            business_interpretation=f"Quartile analysis reveals {abs(gap):.0f}% tiering in {col}.",
            evidence={"column": col, "gap_pct": gap, "difference_pct": gap, "highest_quartile": high, "lowest_quartile": low},
            confidence=_calculate_confidence(0.75, effect_size=abs(gap) / 100.0),
            importance_score=min(1.0, abs(gap) / 80)
        ))

    return insights


def extract_distribution_insights(evidence: Dict[str, Any]) -> List[InsightCandidate]:
    insights = []
    distributions = evidence.get("distributions", {})

    for column, stats in distributions.items():
        if not isinstance(stats, dict):
            continue

        mean = stats.get("mean")
        median = stats.get("median")

        if mean is None or median is None or mean == 0 or median == 0:
            continue

        if abs(mean / median - 1.0) < 0.20:
            continue

        skewness = "right-skewed" if mean > median else "left-skewed"

        insights.append(InsightCandidate(
            type="distribution",
            title=f"{column} shows {skewness} distribution",
            finding=f"{column} has mean={mean:.1f} and median={median:.1f}.",
            business_interpretation=f"Values cluster {'below' if mean > median else 'above'} the average, suggesting separate analysis for extremes.",
            evidence={"column": column, "mean": mean, "median": median, "skewness": skewness},
            confidence=0.85,
            importance_score=0.45
        ))

    return insights


def extract_data_quality_insights(evidence: Dict[str, Any]) -> List[InsightCandidate]:
    insights = []
    missing = evidence.get("missing_values", {})

    for col, data in missing.items():
        pct = data.get("pct", 0)
        if pct > 5:
            insights.append(InsightCandidate(
                type="data_quality",
                title=f"{col} has {pct:.1f}% missing data",
                finding=f"{col} is missing in {pct:.1f}% of records.",
                business_interpretation=f"Missing data in {col} may introduce bias if not handled.",
                evidence={"column": col, "max_missing_pct": pct, "computed_missing_pct": pct},
                confidence=0.85,
                importance_score=min(0.70, pct / 20)
            ))

    return insights


def extract_categorical_target_insights(evidence: Dict[str, Any]) -> List[InsightCandidate]:
    insights = []
    target = evidence.get("target_detection", {}).get("target_column")
    target_is_numeric = evidence.get("target_detection", {}).get("is_numeric", False)

    if target_is_numeric or not target:
        return insights

    cat_analysis = evidence.get("categorical_target_analysis", {})
    if not cat_analysis:
        return insights

    dist = cat_analysis.get("distribution", {})
    if dist:
        top_values = dist.get("top_values", {})
        top_val = list(top_values.keys())[0] if top_values else "unknown"
        top_count = list(top_values.values())[0] if top_values else 0
        total = sum(top_values.values()) if top_values else 0
        top_pct = round(top_count / total * 100, 1) if total else 0

        insights.append(InsightCandidate(
            type="distribution",
            title=f"{target} spans {dist.get('unique_values', 0)} categories with {top_val} leading",
            finding=f"{target} has {dist.get('unique_values', 0)} categories; '{top_val}' is most frequent ({top_pct}%).",
            business_interpretation=f"The dataset covers {dist.get('unique_values', 0)} distinct {target} categories.",
            evidence={"column": target, "unique_values": dist.get("unique_values"), "top_value": top_val, "top_pct": top_pct},
            confidence=0.90,
            importance_score=0.60
        ))

    for col, data in cat_analysis.get("associations", {}).items():
        if not data.get("significant"):
            continue

        # FIX: Handle perfect association (column exists only in one target class)
        if data.get("perfect_association"):
            target_val = data.get("target_value", "unknown")
            insights.append(InsightCandidate(
                type="group_difference",
                title=f"{col} exists exclusively in {target_val} {target}",
                finding=f"'{col}' is present ONLY when {target} = '{target_val}' — a perfect structural association.",
                business_interpretation=f"The presence of '{col}' perfectly identifies {target_val} outcomes.",
                evidence={
                    "group_column": col, "cramers_v": 1.0, "p_value": 0.0,
                    "statistically_significant": True, "perfect_association": True,
                    "target_value": target_val,
                },
                confidence=0.95,
                importance_score=0.95
            ))
            continue

        cramers = data.get("cramers_v", 0)
        if cramers < 0.15:
            continue
        assoc = data.get("strongest_association", {})
        target_val = assoc.get("target_value")
        col_val = assoc.get("column_value")
        lift = assoc.get("lift", 1.0)

        # FIX: Richer, more actionable title
        if target_val and col_val:
            title = f"{col_val} ({col}) is {lift:.1f}x more likely in {target_val} {target}"
            finding = (
                f"'{col_val}' in {col} is strongly associated with '{target_val}' {target} "
                f"(Cramér's V = {cramers:.3f}, lift = {lift:.2f})."
            )
        else:
            title = f"{col} associated with {target}"
            finding = f"{col} shows significant association with {target} (Cramér's V = {cramers:.3f})."

        insights.append(InsightCandidate(
            type="group_difference",
            title=title,
            finding=finding,
            business_interpretation=f"Segment '{col_val}' in {col} is disproportionately associated with {target_val} outcomes.",
            evidence={
                "group_column": col,
                "cramers_v": cramers,
                "p_value": data.get("p_value"),
                "statistically_significant": True,
                "lift": lift,
                "target_value": target_val,
                "column_value": col_val,
            },
            confidence=0.75,
            importance_score=min(0.95, cramers * 2.5 + (lift - 1) * 0.1)
        ))

    for text_col, stats in cat_analysis.get("text_by_category", {}).items():
        if not stats or len(stats) < 2:
            continue
        max_cat = max(stats.items(), key=lambda x: x[1].get("avg_length", 0))
        min_cat = min(stats.items(), key=lambda x: x[1].get("avg_length", 0))
        max_len = max_cat[1].get("avg_length", 0)
        min_len = min_cat[1].get("avg_length", 0)
        if max_len > min_len * 1.15:
            diff_pct = round((max_len - min_len) / max(min_len, 1) * 100, 1)
            insights.append(InsightCandidate(
                type="segment",
                title=f"{text_col} length varies by {target}",
                finding=f"{max_cat[0]} avg {max_len:.0f} chars vs {min_cat[0]} at {min_len:.0f} chars.",
                business_interpretation=f"Content length differs across {target} categories.",
                evidence={"column": text_col, "difference_pct": diff_pct, "max_category": max_cat[0], "min_category": min_cat[0]},
                confidence=0.75,
                importance_score=0.55
            ))

    for col, missing_data in cat_analysis.get("missing_by_category", {}).items():
        if not missing_data:
            continue
        max_cat = max(missing_data.items(), key=lambda x: x[1])
        min_cat = min(missing_data.items(), key=lambda x: x[1])
        if max_cat[1] > min_cat[1] + 10:
            insights.append(InsightCandidate(
                type="data_quality",
                title=f"Missing {col} concentrated in {max_cat[0]}",
                finding=f"{max_cat[0]} has {max_cat[1]:.1f}% missing {col} vs {min_cat[0]} at {min_cat[1]:.1f}%.",
                business_interpretation=f"Data completeness varies by {target}, may introduce bias.",
                evidence={"column": col, "max_missing_pct": max_cat[1], "min_missing_pct": min_cat[1]},
                confidence=0.85,
                importance_score=0.50
            ))

    return insights


def extract_target_analysis_insights(evidence: Dict[str, Any]) -> List[InsightCandidate]:
    insights = []
    target = evidence.get("target_detection", {}).get("target_column")
    target_analysis = evidence.get("target_analysis", {})

    if not target or not target_analysis or "error" in target_analysis:
        return insights

    for col, data in target_analysis.get("top_segments", {}).items():
        # === FIX: Skip free-text columns ===
        if _is_text_column(evidence, col):
            continue

        gap = data.get("gap_pct")
        if not gap or abs(gap) < BASE_MIN_SEGMENT_GAP:
            continue

        high = data.get("highest_quartile", {})
        low = data.get("lowest_quartile", {})

        insights.append(InsightCandidate(
            type="segment",
            title=f"{col} quartiles show {abs(gap):.0f}% {target} gap",
            finding=f"Top quartile ({high.get('range')}) averages {high.get('mean_target')} vs bottom ({low.get('range')}) at {low.get('mean_target')}.",
            business_interpretation=f"Quartile analysis of {col} reveals {abs(gap):.0f}% tiering in {target}.",
            evidence={"column": col, "gap_pct": gap, "difference_pct": gap, "highest_quartile": high, "lowest_quartile": low},
            confidence=0.75,
            importance_score=min(0.90, abs(gap) / 100)
        ))

    for col, data in target_analysis.get("risk_groups", {}).items():
        # === FIX: Skip free-text columns ===
        if _is_text_column(evidence, col):
            continue

        top = data.get("top_over_represented", [])
        if not top:
            continue
        best = top[0]
        lift = best.get("lift", 1)

        insights.append(InsightCandidate(
            type="risk_segment",
            title=f"{col} '{best.get('category')}' over-represented in high-{target}",
            finding=f"{best.get('category')} appears {lift:.1f}x more in high-{target} group.",
            business_interpretation=f"{col} category '{best.get('category')}' is disproportionately associated with elevated {target}.",
            evidence={
                "column": col,
                "top_lift": lift,
                "top_category": best.get("category"),
                "gap_percent": (lift - 1) * 100,
                "over_represented": top[:3],
            },
            confidence=0.80,
            importance_score=min(0.85, lift * 0.3)
        ))

    return insights


def _apply_diversity_control(insights: List[InsightCandidate]) -> List[InsightCandidate]:
    type_counts = {}
    result = []

    for insight in insights:
        cap = DIVERSITY_CAPS.get(insight.type, 999)
        current = type_counts.get(insight.type, 0)
        if current < cap:
            result.append(insight)
            type_counts[insight.type] = current + 1

    return result


def _is_actionable_insight(insight: InsightCandidate) -> bool:
    evidence = insight.evidence or {}

    if insight.type == "feature_importance":
        return evidence.get("importance", 0) >= BASE_MIN_FEATURE_IMPORTANCE

    if insight.type == "correlation":
        return abs(evidence.get("correlation", 0)) >= BASE_MIN_CORRELATION

    if insight.type == "group_difference":
        diff = abs(evidence.get("difference_percent", 0))
        if diff < BASE_MIN_GROUP_DIFF_PCT:
            return False
        return True

    if insight.type == "outlier":
        return evidence.get("outlier_pct", 0) >= 2.0

    if insight.type == "distribution":
        return True

    if insight.type == "data_quality":
        return evidence.get("max_missing_pct", 0) > 5 or evidence.get("computed_missing_pct", 0) > 5

    if insight.type == "segment":
        return evidence.get("difference_pct", 0) >= BASE_MIN_SEGMENT_GAP

    if insight.type == "risk_segment":
        return evidence.get("gap_percent", 0) >= BASE_MIN_GROUP_DIFF_PCT or evidence.get("top_lift", 1) > 1.15

    if insight.type == "interaction":
        return evidence.get("segment_gap", 0) >= 15

    return True