from typing import List, Tuple
import numpy as np
import pandas as pd
from backend.core.constants import TARGET_KEYWORDS, NEGATIVE_KEYWORDS
from backend.models.insight import InsightCandidate
from backend.statistics.bivariate import (
    anova_test,
    chi2_from_contingency,
    correlation_p_value,
    series_correlation,
    welch_ttest,
)
from backend.tools.insight_extractor import BASE_MIN_FEATURE_IMPORTANCE as MIN_FEATURE_IMPORTANCE
from backend.utils.target_detection import detect_target_variable


MIN_CORRELATION_KEEP = 0.15
MIN_FEATURE_KEEP = 0.15
MIN_GROUP_DIFF_KEEP = 10.0
MIN_LIFT_KEEP = 1.15
MIN_F_STAT_KEEP = 1.0

P_VALUE_THRESHOLDS = {
    "group_difference": 0.10,
    "risk_segment": 0.15,
    "interaction": 0.20,
    "correlation": 0.05,
    "segment": 0.10,
    "feature_importance": 0.05,
}

TEXT_LENGTH_COLUMNS = {"link", "title", "content", "description", "text", "url", "name"}


def validate_insights(
    insights: List[InsightCandidate],
    dataframe,
    target: str = None
):
    validated = []
    n_rows = len(dataframe)

    for insight in insights:
        col = (insight.evidence.get("column") or
           insight.evidence.get("group_column") or
           insight.evidence.get("feature"))
        
        # Check if this is a text column (by semantics or high cardinality)
        is_text_col = False
        if col and col in dataframe.columns:
            # Check by column semantics
            col_semantics = dataframe[col].dtype
            is_object_or_string = col_semantics in (object, "string", "O")
            
            # Check by high cardinality (text columns typically have >5% unique values)
            if is_object_or_string:
                unique_ratio = dataframe[col].nunique() / max(1, len(dataframe))
                if unique_ratio > 0.05:
                    is_text_col = True
        
        if is_text_col:
            # Allow text length statistics (segment insights with difference_pct)
            if insight.type == "segment":
                evidence = insight.evidence or {}
                # Check if this is a text length insight
                if "difference_pct" in evidence or "avg_length" in evidence:
                    print(f"VALIDATION CHECK: {insight.type} ALLOWED (text_length_analysis: {col})")
                    # Continue processing this insight
                else:
                    print(f"VALIDATION CHECK: {insight.type} SKIPPED (text_column_complex_analysis: {col})")
                    continue
                
            else:
                # Skip other insight types for text columns
                print(f"VALIDATION CHECK: {insight.type} SKIPPED (text_column: {col})")
                continue

        if insight.evidence.get("n_samples") is None:
            col = (insight.evidence.get("column") or 
                   insight.evidence.get("group_column") or 
                   insight.evidence.get("feature"))
            if col and col in dataframe.columns:
                insight.evidence["n_samples"] = int(dataframe[col].notna().sum())
            else:
                insight.evidence["n_samples"] = n_rows

        if insight.type == "group_difference":
            result = validate_group_difference(insight, dataframe, target)
        elif insight.type == "correlation":
            result = validate_correlation(insight, dataframe)
        elif insight.type == "segment":
            result = validate_segment(insight, dataframe, target)
        elif insight.type == "risk_segment":
            result = validate_risk_segment(insight, dataframe, target)
        elif insight.type == "interaction":
            result = validate_interaction(insight, dataframe, target)
        elif insight.type == "feature_importance":
            result = validate_feature_importance(insight, dataframe, target)
        elif insight.type == "distribution":
            result = validate_distribution(insight, dataframe, target)
        elif insight.type == "data_quality":
            result = validate_data_quality(insight, dataframe, target)
        else:
            result = insight

        result = _recalculate_confidence(result, dataframe)
        keep, reason = _should_keep_insight(result, n_rows)
        
        print(f"VALIDATION CHECK: {result.type} p={result.evidence.get('p_value')} "
              f"keep={keep} ({reason})")

        if keep:
            validated.append(result)

    return validated


def validate_group_difference(
    insight: InsightCandidate,
    df,
    target: str = None
):
    evidence = insight.evidence
    column = evidence.get("group_column")

    if column not in df.columns:
        return insight

    if df[column].dtype == object and df[column].nunique() > 50:
        insight.evidence["validation_error"] = "text_column_high_cardinality"
        insight.evidence["validation_method"] = "skipped_high_cardinality"
        return insight

    if target is None:
        result = detect_target_variable(df)
        target = result.get("target_column")
    if target is None or target not in df.columns:
        return insight

    if not pd.api.types.is_numeric_dtype(df[target]):
        try:
            pair = df[[target, column]].dropna()
            if len(pair) < 20:
                return insight
            contingency = pd.crosstab(pair[target], pair[column])
            if contingency.shape[0] < 2 or contingency.shape[1] < 2:
                return insight
            # Chi-square / Cramér's V via the Statistical Engine.
            assoc = chi2_from_contingency(contingency)
            chi2 = assoc.get("chi2")
            p_val = assoc.get("p_value") if assoc.get("p_value") is not None else 1.0
            cramers_v = assoc.get("cramers_v") or 0

            insight.evidence.update({
                "p_value": round(float(p_val), 4),
                "statistically_significant": bool(p_val < 0.05),
                "chi2": round(float(chi2), 3) if chi2 is not None else None,
                "cramers_v": round(float(cramers_v), 3),
                "validation_method": "chi_square",
                "n_samples": int(assoc.get("n") or contingency.sum().sum())
            })
        except Exception as e:
            insight.evidence["validation_error"] = str(e)
        return insight

    specific_groups = evidence.get("compared_values") or evidence.get("groups", [])
    if specific_groups and len(specific_groups) == 2:
        try:
            val1, val2 = specific_groups[0], specific_groups[1]
            group1 = df[df[column] == val1][target].dropna()
            group2 = df[df[column] == val2][target].dropna()
            
            if len(group1) >= 5 and len(group2) >= 5:
                # Welch t-test via the Statistical Engine.
                stat, p_val = welch_ttest(group1, group2)
                diff_pct = ((group1.mean() - group2.mean()) / max(abs(group2.mean()), 0.001)) * 100
                insight.title = f"{column}: {val1} shows {abs(diff_pct):.0f}% higher {target} than {val2}"

                insight.evidence.update({
                    "p_value": round(float(p_val), 4) if p_val is not None else None,
                    "statistically_significant": bool(p_val < 0.05) if p_val is not None else False,
                    "t_statistic": round(float(stat), 3) if stat is not None else None,
                    "difference_percent": round(float(diff_pct), 2),
                    "n_samples": len(group1) + len(group2),
                    "validation_method": "specific_groups_ttest"
                })
                return insight
        except Exception:
            pass

    groups = []
    grouped = df.groupby(column)

    for _, group in grouped:
        values = group[target].dropna()
        if len(values) >= 10:
            groups.append(values)

    if len(groups) < 2:
        return insight

    try:
        # One-way ANOVA via the Statistical Engine.
        anova_res = anova_test(groups)
        stat = anova_res.get("f_statistic")
        p_value = anova_res.get("p_value")
        p_val = _to_scalar(p_value) if p_value is not None else None
        f_stat = _to_scalar(stat) if stat is not None else None

        insight.evidence.update({
            "p_value": round(p_val, 4) if p_val is not None else None,
            "statistically_significant": bool(p_val < 0.05) if p_val is not None else False,
            "f_statistic": round(f_stat, 3) if f_stat is not None else None,
            "n_samples": sum(len(g) for g in groups),
            "validation_method": "anova_all_groups"
        })
    except Exception as e:
        insight.evidence["validation_error"] = str(e)

    return insight


def validate_risk_segment(
    insight: InsightCandidate,
    df,
    target: str = None
):
    evidence = insight.evidence
    column = evidence.get("column")

    if column not in df.columns:
        return insight

    if target is None:
        result = detect_target_variable(df)
        target = result.get("target_column")
    if target is None or target not in df.columns:
        return insight

    if not pd.api.types.is_numeric_dtype(df[target]):
        insight.evidence["validation_error"] = "target_not_numeric"
        return insight

    try:
        target_series = df[target].dropna()
        if len(target_series) < 20:
            return insight

        threshold = target_series.quantile(0.75)
        df_temp = df[[column, target]].dropna()

        is_text = df[column].dtype == object
        n_unique = df[column].nunique()
        is_numeric_col = pd.api.types.is_numeric_dtype(df[column])

        if is_text and n_unique > 20:
            insight.evidence.update({
                "threshold": round(float(threshold), 2),
                "high_risk_count": int((df_temp[target] >= threshold).sum()),
                "normal_count": int((df_temp[target] < threshold).sum()),
                "validation_method": "text_descriptive",
                "n_samples": len(df_temp),
                "p_value": None,
                "statistically_significant": None,
                "top_lift": evidence.get("top_lift", 1.0),
                "top_category": evidence.get("top_category", "N/A"),
            })
            return insight

        # ---------- CATEGORICAL column: chi-square ONLY ----------
        if is_text or n_unique <= 10:
            high_risk = df_temp[df_temp[target] >= threshold]
            normal = df_temp[df_temp[target] < threshold]

            if len(high_risk) < 10 or len(normal) < 10:
                return insight

            try:
                contingency = pd.crosstab(
                    pd.cut(df_temp[target], bins=[-np.inf, threshold, np.inf],
                           labels=["normal", "high_risk"]),
                    df_temp[column]
                )

                if contingency.shape[0] >= 2 and contingency.shape[1] >= 2:
                    # Chi-square via the Statistical Engine.
                    assoc = chi2_from_contingency(contingency)
                    p_value = assoc.get("p_value")

                    risk_dist = high_risk[column].value_counts(normalize=True)
                    normal_dist = normal[column].value_counts(normalize=True)

                    over_represented = []
                    for cat_val in risk_dist.index:
                        risk_pct = risk_dist.get(cat_val, 0)
                        normal_pct = normal_dist.get(cat_val, 0)
                        if risk_pct > normal_pct * 1.1 and high_risk[column].value_counts().get(cat_val, 0) >= 3:
                            over_represented.append({
                                "category": str(cat_val),
                                "risk_group_pct": round(risk_pct * 100, 2),
                                "normal_group_pct": round(normal_pct * 100, 2),
                                "lift": round(risk_pct / max(normal_pct, 0.001), 2),
                                "count": int(high_risk[column].value_counts().get(cat_val, 0)),
                            })

                    update = {
                        "p_value": round(float(p_value), 4) if p_value is not None else None,
                        "statistically_significant": bool(p_value < 0.05) if p_value is not None else False,
                        "chi2_statistic": round(float(assoc["chi2"]), 3) if assoc.get("chi2") is not None else None,
                        "threshold": round(float(threshold), 2),
                        "high_risk_count": int(len(high_risk)),
                        "normal_count": int(len(normal)),
                        "n_samples": len(df_temp),
                        "validation_method": "chi_square",
                    }
                    if over_represented:
                        over_represented.sort(key=lambda x: x["lift"], reverse=True)
                        top = over_represented[0]
                        update["top_category"] = top["category"]
                        update["top_lift"] = top["lift"]
                        update["over_represented"] = over_represented[:3]
                    insight.evidence.update(update)
                return insight          # FIX: never fall through to t-test on strings
            except Exception as e:
                insight.evidence["validation_error"] = str(e)
                return insight          # FIX: graceful exit, no string t-test

        # ---------- NUMERIC column: t-test ONLY ----------
        if is_numeric_col:
            high_risk = df_temp[df_temp[target] >= threshold][column]
            normal = df_temp[df_temp[target] < threshold][column]

            if len(high_risk) >= 10 and len(normal) >= 10:
                # Welch t-test via the Statistical Engine.
                stat, p_value = welch_ttest(high_risk, normal)
                insight.evidence.update({
                    "p_value": round(float(p_value), 4) if p_value is not None else None,
                    "statistically_significant": bool(p_value < 0.05) if p_value is not None else False,
                    "t_statistic": round(float(stat), 3) if stat is not None else None,
                    "threshold": round(float(threshold), 2),
                    "high_risk_mean": round(float(high_risk.mean()), 2),
                    "normal_mean": round(float(normal.mean()), 2),
                    "difference_pct": round((high_risk.mean() - normal.mean()) / max(normal.mean(), 0.001) * 100, 2),
                    "n_samples": len(df_temp),
                    "validation_method": "t_test"
                })

    except Exception as e:
        insight.evidence.update({
            "p_value": None,
            "statistically_significant": False,
            "validation_error": str(e),
        })

    return insight


def validate_interaction(
    insight: InsightCandidate,
    df,
    target: str = None
):
    evidence = insight.evidence
    column = evidence.get("column")
    interaction_cols = evidence.get("interaction_columns", [])
    
    if not interaction_cols and column:
        interaction_cols = [column]

    if not interaction_cols or not all(c in df.columns for c in interaction_cols):
        return insight

    if target is None:
        result = detect_target_variable(df)
        target = result.get("target_column")
    if target is None or target not in df.columns:
        return insight

    if not pd.api.types.is_numeric_dtype(df[target]):
        insight.evidence["validation_error"] = "target_not_numeric"
        return insight

    clean_cols = [c for c in interaction_cols if pd.api.types.is_numeric_dtype(df[c])]

    for c in interaction_cols:
        if pd.api.types.is_numeric_dtype(df[c]):
            continue
        clean_cols.append(c)
    
    if len(clean_cols) < 2 and column and pd.api.types.is_numeric_dtype(df[column]):
        numeric_cols = [c for c in df.select_dtypes(include=[np.number]).columns
                        if c != target and c != column][:5]
        if numeric_cols:
            clean_cols = [column, numeric_cols[0]]
        else:
            insight.evidence["validation_method"] = "skipped_no_numeric_partner"
            insight.evidence["n_samples"] = len(df)
            return insight

    if len(clean_cols) < 2:
        insight.evidence["validation_method"] = "insufficient_numeric_columns"
        insight.evidence["n_samples"] = len(df)
        return insight

    try:
        df_temp = df[clean_cols + [target]].dropna()
        if len(df_temp) < 20:
            return insight

        for col in clean_cols:
            median = df_temp[col].median()
            df_temp[f"{col}_group"] = (df_temp[col] >= median).astype(int)

        group_cols = [f"{c}_group" for c in clean_cols]
        grouped = df_temp.groupby(group_cols)[target].apply(list)
        groups = [g for g in grouped if len(g) >= 5]

        if len(groups) < 2:
            insight.evidence["validation_method"] = "insufficient_groups"
            insight.evidence["n_samples"] = len(df_temp)
            return insight

        anova_res = anova_test([pd.Series(g) for g in groups])
        f_statistic = anova_res.get("f_statistic")
        p_value = anova_res.get("p_value")
        p_val = _to_scalar(p_value) if p_value is not None else None
        f_stat = _to_scalar(f_statistic) if f_statistic is not None else None

        insight.evidence.update({
            "p_value": round(p_val, 4) if p_val is not None else None,
            "statistically_significant": bool(p_val < 0.05) if p_val is not None else False,
            "f_statistic": round(f_stat, 3) if f_stat is not None else None,
            "interaction_columns": clean_cols,
            "n_groups": len(groups),
            "n_samples": len(df_temp),
            "validation_method": "anova_interaction"
        })

    except Exception as e:
        insight.evidence.update({
            "p_value": None,
            "statistically_significant": False,
            "validation_error": str(e),
            "n_samples": len(df)
        })

    return insight


def validate_feature_importance(
    insight: InsightCandidate,
    df,
    target: str = None
):
    evidence = insight.evidence
    feature = evidence.get("feature") or evidence.get("column")

    if feature is None or feature not in df.columns:
        return insight

    if target is None:
        result = detect_target_variable(df)
        target = result.get("target_column")
    if target is None or target not in df.columns:
        return insight

    # Structural / definitional leakage guard.
    # Reject features whose presence (or absence) almost perfectly determines the target.
    try:
        feat_series = df[feature]
        missing_pct = feat_series.isna().mean()
        if missing_pct > 0.05:
            present_mask = feat_series.notna()
            if present_mask.sum() >= 10:
                present_mode_pct = (
                    df.loc[present_mask, target].value_counts(normalize=True).iloc[0]
                )
                if present_mode_pct > 0.95:
                    insight.evidence["validation_error"] = "structural_leakage_presence"
                    insight.evidence["leakage_mode_pct"] = round(float(present_mode_pct), 4)
                    print(
                        f"VALIDATION CHECK: feature_importance REJECTED "
                        f"(structural leakage: {feature} present → {present_mode_pct:.1%} one class)"
                    )
                    return insight
            missing_mask = ~present_mask
            if missing_mask.sum() >= 10:
                missing_mode_pct = (
                    df.loc[missing_mask, target].value_counts(normalize=True).iloc[0]
                )
                if missing_mode_pct > 0.85:
                    insight.evidence["validation_error"] = "structural_leakage_missingness"
                    insight.evidence["leakage_mode_pct"] = round(float(missing_mode_pct), 4)
                    print(
                        f"VALIDATION CHECK: feature_importance REJECTED "
                        f"(structural leakage: {feature} missing → {missing_mode_pct:.1%} one class)"
                    )
                    return insight
    except Exception:
        pass

    try:
        series = df[[feature, target]].dropna()
        if len(series) < 10:
            return insight

        feat_is_cat = not pd.api.types.is_numeric_dtype(df[feature])
        target_is_cat = not pd.api.types.is_numeric_dtype(df[target])

        if feat_is_cat and target_is_cat:
            contingency = pd.crosstab(series[feature], series[target])
            if contingency.shape[0] < 2 or contingency.shape[1] < 2:
                return insight
            # Chi-square / Cramér's V via the Statistical Engine.
            assoc = chi2_from_contingency(contingency)
            p_val = assoc.get("p_value")
            cramers_v = assoc.get("cramers_v") or 0

            insight.evidence.update({
                "p_value": round(float(p_val), 4) if p_val is not None else None,
                "statistically_significant": bool(p_val < 0.05) if p_val is not None else False,
                "cramers_v": round(float(cramers_v), 3),
                "n_samples": int(assoc.get("n") or len(series)),
                "validation_method": "chi_square"
            })
            return insight

        if feat_is_cat or target_is_cat:
            insight.evidence.update({
                "n_samples": int(len(series)),
                "feature_type": evidence.get("feature_type", "unknown")
            })
            return insight

        # Spearman correlation via the Statistical Engine.
        r = series_correlation(series[feature], series[target], method="spearman")
        n = len(series)

        if r is None or abs(r) >= 1:
            return insight

        # Correlation significance via the Statistical Engine primitive.
        p_value = correlation_p_value(r, n)

        insight.evidence.update({
            "p_value": round(float(p_value), 4) if p_value is not None else None,
            "statistically_significant": bool(p_value < 0.05) if p_value is not None else False,
            "correlation": round(float(r), 3),
            "n_samples": int(n),
        })
    except Exception:
        pass

    return insight


def validate_correlation(insight: InsightCandidate, df):
    evidence = insight.evidence
    r = evidence.get("correlation")

    if r is None:
        return insight

    n = len(df)
    try:
        r = float(r)
    except (TypeError, ValueError):
        return insight

    # Correlation significance via the Statistical Engine primitive.
    p_value = correlation_p_value(r, n)
    p_val = p_value if p_value is not None else 0.0

    insight.evidence.update({
        "p_value": round(float(p_val), 4),
        "statistically_significant": bool(p_val < 0.05),
        "n_samples": n
    })
    return insight


def validate_segment(insight: InsightCandidate, df, target: str = None):
    evidence = insight.evidence
    column = evidence.get("column")

    if column not in df.columns or target not in df.columns:
        return insight

    col_lower = str(column).lower()
    is_text_length = any(txt in col_lower for txt in TEXT_LENGTH_COLUMNS)

    if is_text_length:
        # Recompute accurate per-target mean lengths from the actual data
        # so the report never shows rounded/stale values (e.g. 114 vs 113.51).
        try:
            lengths = df[column].astype(str).str.len()
            means = (
                df.assign(_len=lengths)
                .groupby(target)["_len"]
                .mean()
                .round(1)
                .to_dict()
            )
            if means:
                insight.evidence["group_means"] = means
                # Prefer negative vs positive when both exist (common pattern)
                neg = means.get("negative")
                pos = means.get("positive")
                if neg is not None and pos is not None:
                    insight.evidence["negative_avg_len"] = neg
                    insight.evidence["positive_avg_len"] = pos
                    # Rebuild a precise finding string when the original was approximate
                    if insight.finding and ("avg" in insight.finding.lower() or "char" in insight.finding.lower()):
                        insight.finding = (
                            f"negative avg {neg:g} chars vs positive at {pos:g} chars."
                        )
                vals = list(means.values())
                if len(vals) >= 2:
                    mx, mn = max(vals), min(vals)
                    if mn > 0:
                        insight.evidence["difference_pct"] = round((mx - mn) / mn * 100, 1)
        except Exception:
            pass

        diff_pct = evidence.get("difference_pct", 0) or insight.evidence.get("difference_pct", 0)
        if diff_pct >= 10:
            insight.evidence["validation_method"] = "text_length_derived"
            insight.evidence["statistically_significant"] = True
            return insight
        else:
            insight.evidence["validation_error"] = "text_length_diff_too_small"
            return insight

    if not pd.api.types.is_numeric_dtype(df[column]) or not pd.api.types.is_numeric_dtype(df[target]):
        insight.evidence["validation_error"] = "non_numeric_segment"
        return insight

    try:
        df_temp = df[[column, target]].dropna()
        df_temp["_bin"] = pd.qcut(df_temp[column], q=4, duplicates="drop")
        groups = df_temp.groupby("_bin", observed=True)[target].apply(list)

        if len(groups) < 2:
            return insight

        top = groups.iloc[-1]
        bottom = groups.iloc[0]

        if len(top) >= 5 and len(bottom) >= 5:
            # Welch t-test via the Statistical Engine.
            stat, p_val = welch_ttest(pd.Series(top), pd.Series(bottom))
            insight.evidence.update({
                "p_value": round(float(p_val), 4) if p_val is not None else None,
                "statistically_significant": bool(p_val < 0.05) if p_val is not None else False,
                "n_top": len(top),
                "n_bottom": len(bottom),
                "n_samples": len(top) + len(bottom)
            })
    except Exception:
        pass

    return insight


def validate_distribution(insight: InsightCandidate, df, target: str = None):
    evidence = insight.evidence
    column = evidence.get("column")
    if column and column in df.columns:
        n = df[column].notna().sum()
        evidence["n_samples"] = int(n)
        if n < 10:
            evidence["validation_warning"] = "small_sample"
    return insight


def validate_data_quality(insight: InsightCandidate, df, target: str = None):
    evidence = insight.evidence
    column = evidence.get("column")
    if column and column in df.columns:
        missing_pct = df[column].isna().sum() / len(df) * 100
        evidence["computed_missing_pct"] = round(missing_pct, 2)
        evidence["n_total"] = len(df)
        evidence["n_samples"] = len(df)
    return insight


def _recalculate_confidence(insight: InsightCandidate, df) -> InsightCandidate:
    evidence = insight.evidence or {}
    n = len(df)

    n_samples = evidence.get("n_samples", n)
    sample_score = min(1.0, n_samples / 200) if isinstance(n_samples, (int, float)) else 0.5

    effect = 0.3
    corr = evidence.get("correlation")
    if corr is not None:
        effect = abs(float(corr))
    else:
        gap = (evidence.get("gap_percent") or evidence.get("difference_percent") 
               or evidence.get("difference_pct"))
        if gap is not None:
            effect = min(1.0, abs(float(gap)) / 100)
        cramers = evidence.get("cramers_v")
        if cramers is not None:
            effect = abs(float(cramers))
        lift = evidence.get("top_lift")
        if lift is not None:
            effect = min(1.0, max(0, (float(lift) - 1.0)) / 2.0)

    p_val = evidence.get("p_value")
    if p_val is not None:
        p_score = 1 - min(1.0, float(p_val))
    else:
        p_score = 0.6

    missing_pct = evidence.get("missing_pct", 0)
    missing_score = 1 - min(1.0, float(missing_pct) / 20) if isinstance(missing_pct, (int, float)) else 1.0

    new_confidence = round(
        sample_score * 0.25 + effect * 0.30 + p_score * 0.30 + missing_score * 0.15, 2
    )
    insight.confidence = min(0.95, new_confidence)
    return insight


def _to_scalar(value):
    if isinstance(value, (int, float)):
        return float(value)
    arr = np.asarray(value)
    if arr.size == 1:
        return float(arr.item())
    elif arr.size > 1:
        return float(arr.flat[0])
    raise ValueError("Empty array")


def _safe_float(val, default=0.0):
    """Safely convert value to float, handling None."""
    if val is None:
        return default
    try:
        f = float(val)
        if np.isfinite(f):
            return f
        return default
    except (TypeError, ValueError):
        return default


def _should_keep_insight(insight: InsightCandidate, total_rows: int = 1000) -> Tuple[bool, str]:
    evidence = insight.evidence or {}
    n_samples = evidence.get("n_samples", 0)
    has_large_sample = isinstance(n_samples, (int, float)) and n_samples >= 50

    p_threshold = P_VALUE_THRESHOLDS.get(insight.type, 0.05)

    if insight.type == "group_difference":
        p_value = evidence.get("p_value")
        diff = abs(_safe_float(evidence.get("difference_percent"), 0))
        cramers = _safe_float(evidence.get("cramers_v"), 0)

        if p_value is not None and p_value < 0.05 and diff >= MIN_GROUP_DIFF_KEEP:
            return True, "strong"
        # === FIX: More lenient borderline ===
        if p_value is not None and p_value < 0.15 and diff >= 5:  # was p<0.10
            return True, "borderline"
        if diff >= 20 and has_large_sample:
            if p_value is None or p_value < 0.15:
                return True, "large_effect"
            return False, f"large_effect_but_insignificant(p={p_value})"
        if evidence.get("validation_method") == "specific_groups_ttest" and diff >= 5:
            return True, "specific_comparison"
        return False, f"weak(p={p_value}, diff={diff}, threshold={p_threshold})"

    if insight.type == "correlation":
        corr = abs(_safe_float(evidence.get("correlation"), 0))
        if corr >= MIN_CORRELATION_KEEP:
            return True, f"corr={corr}"
        if corr >= 0.10 and has_large_sample:
            return True, "weak_but_large_n"
        return False, f"corr={corr}_too_weak"

    if insight.type == "feature_importance":
        # Reject structural / definitional leakage
        validation_error = evidence.get("validation_error", "")
        if validation_error in (
            "structural_leakage_presence",
            "structural_leakage_missingness",
        ):
            return False, f"leakage_rejected({validation_error})"

        importance = _safe_float(evidence.get("importance"), 0)
        if importance >= MIN_FEATURE_KEEP:
            return True, f"importance={importance}"
        if importance >= 0.10 and has_large_sample:
            return True, "moderate_large_n"
        return False, f"importance={importance}_too_weak"

    if insight.type == "risk_segment":
        p_value = evidence.get("p_value")
        lift = _safe_float(evidence.get("top_lift"), 0)
        
        if lift >= MIN_LIFT_KEEP:
            return True, f"lift={lift}"
        if p_value is not None and p_value < p_threshold:
            return True, "borderline_significant"
        if evidence.get("validation_method") == "text_descriptive" and has_large_sample:
            return True, "text_descriptive"
        return False, f"weak(p={p_value}, lift={lift}, threshold={p_threshold})"

    if insight.type == "interaction":
    # === FIX: Reject interactions that explicitly failed validation ===
        validation_method = evidence.get("validation_method", "")
        if validation_method in (
            "insufficient_numeric_columns",
            "skipped_no_numeric_partner",
            "insufficient_groups",
        ):
            return False, f"validation_failed({validation_method})"

        p_value = evidence.get("p_value")
        f_stat = _safe_float(evidence.get("f_statistic"), 0)

        if p_value is not None and p_value > 0.20:
            return False, f"not_significant(p={p_value})"
        if p_value is not None and p_value < 0.05:
            return True, "significant"
        if p_value is not None and p_value < p_threshold and f_stat >= 1.0:
            return True, "borderline"
        if f_stat >= MIN_F_STAT_KEEP:
            return True, "moderate_f"
        if evidence.get("interaction_columns") and has_large_sample:
            return True, "candidate_large_n"
        return False, f"weak(p={p_value}, f={f_stat}, threshold={p_threshold})"
    if insight.type == "distribution":
        return True, "informational"

    if insight.type == "data_quality":
        keep = evidence.get("max_missing_pct", 0) > 5 or evidence.get("computed_missing_pct", 0) > 5
        return keep, "data_quality"

    if insight.type == "segment":
        if evidence.get("validation_error"):
            return False, f"validation_error({evidence['validation_error']})"
        
        diff = _safe_float(evidence.get("difference_pct"), 0)

        if diff >= 10:
            return True, f"diff={diff}"
        if diff >= 5 and has_large_sample:
            return True, "small_diff_large_n"
        return False, f"diff={diff}_too_small"

    return True, "default"