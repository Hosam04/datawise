"""Evidence building for the Insights Agent."""
import pandas as pd
import numpy as np

from backend.statistics.bivariate import anova_test, chi2_association, series_correlation
from backend.statistics.univariate import categorical_summary, numeric_summary
from backend.tools.insight_tools import build_insight_evidence
from backend.utils.target_detection import detect_target_variable, is_identifier_column
from backend.core.constants import TARGET_KEYWORDS, NEGATIVE_KEYWORDS


def get_target_column(state, base_evidence, df):
    """Determine the target column from multiple sources."""
    target = None

    if state.target_detection and state.target_detection.get("target_column"):
        target = state.target_detection["target_column"]

    if target is None and base_evidence.get("target_detection", {}).get("target_column"):
        target = base_evidence["target_detection"]["target_column"]

    if target is None or target not in df.columns:
        result = detect_target_variable(df)
        target = result.get("target_column")

    return target


def compute_target_correlations(df, target, base_evidence):
    """Compute target correlations for numeric targets."""
    if base_evidence.get("target_correlations"):
        return base_evidence.get("target_correlations", {})

    computed_corr = {}
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    for col in numeric_cols:
        if col != target:
            c = series_correlation(df[col], df[target], method="spearman")
            if c is not None:
                computed_corr[col] = float(c)
    return computed_corr


def analyze_target(df, target_col):
    """Target overview via Statistical Engine summaries."""
    if not target_col or target_col not in df.columns:
        return {}
    series = df[target_col].dropna()
    if series.empty:
        return {}
    if pd.api.types.is_numeric_dtype(series):
        summary = numeric_summary(series)
        return {
            "column": target_col,
            "mean": float(summary.mean),
            "median": float(summary.median),
            "std": float(summary.std) if summary.std is not None else 0.0,
            "min": float(summary.min),
            "max": float(summary.max)
        }
    else:
        cat = categorical_summary(series)
        top_category = cat.top_values[0].value if cat.top_values else None
        top_pct = cat.top_values[0].percentage if cat.top_values else 0
        return {
            "column": target_col,
            "type": "categorical",
            "unique_values": int(cat.unique_count),
            "top_category": top_category,
            "top_category_pct": top_pct
        }


def build_feature_importance(df, target, base_evidence):
    """Build feature importance for numeric and categorical targets."""
    target_is_numeric = pd.api.types.is_numeric_dtype(df[target])

    if not target_is_numeric:
        base_evidence["feature_importance"] = {"target": target, "method": "categorical_target", "top_5": []}
        return base_evidence

    numeric_importance = _compute_numeric_feature_importance(df, target)
    categorical_importance = _compute_categorical_feature_importance(df, target)
    merged_top5 = numeric_importance + categorical_importance
    merged_top5.sort(key=lambda x: x["importance"], reverse=True)
    base_evidence["feature_importance"] = {
        "target": target,
        "method": "mixed_numeric_categorical",
        "top_5": merged_top5[:5]
    }
    base_evidence["categorical_importance"] = {
        "target": target,
        "method": "anova_f_test_or_chi2",
        "top_5": categorical_importance[:5]
    }
    return base_evidence


def _compute_numeric_feature_importance(df, target):
    importance = {}
    id_cols = {
        c for c in df.columns
        if any(kw in c.lower() for kw in NEGATIVE_KEYWORDS)
    }

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if target not in numeric_cols:
        return []

    for col in numeric_cols:
        if col == target or col in id_cols:
            continue
        missing_pct = df[col].isna().sum() / max(1, len(df))
        if missing_pct > 0.30:
            continue
        # Continuous numeric features routinely have high unique-ratio;
        # do not skip them when computing correlation-based importance.
        try:
            pair = df[[col, target]].dropna()
            if len(pair) < 10 or pair[target].nunique() <= 1:
                continue
            # Delegated to the Statistical Engine's correlation primitive.
            corr = series_correlation(pair[col], pair[target], method="spearman")
            if corr is not None:
                importance[col] = abs(float(corr))
        except Exception:
            pass

    return sorted(
        [{"feature": k, "importance": round(v, 3), "type": "numeric"} for k, v in importance.items()],
        key=lambda x: x["importance"],
        reverse=True
    )[:5]


def _compute_categorical_feature_importance(df, target):
    importance = []
    id_cols = {
        c for c in df.columns
        if any(kw in c.lower() for kw in NEGATIVE_KEYWORDS)
    }

    target_is_numeric = pd.api.types.is_numeric_dtype(df[target])
    categorical_cols = [
        c for c in df.columns
        if c != target
        and c not in id_cols
        and (df[c].dtype == object or df[c].nunique() <= 20)
        and not pd.api.types.is_datetime64_any_dtype(df[c])
    ]

    for col in categorical_cols:
        missing_pct = df[col].isna().sum() / len(df)
        if missing_pct > 0.30:
            continue
        # FIX: Skip high-cardinality categorical
        ratio = df[col].nunique(dropna=True) / max(1, len(df))
        if ratio > 0.2:
            continue
        try:
            pair = df[[col, target]].dropna()
            if len(pair) < 20 or pair[col].nunique() < 2:
                continue

            if target_is_numeric:
                groups = [group[target].values for name, group in pair.groupby(col) if len(group) >= 5]
                if len(groups) < 2:
                    continue
                # One-way ANOVA via the Statistical Engine.
                anova_res = anova_test([pd.Series(g) for g in groups])
                f_stat = anova_res.get("f_statistic")
                p_val = anova_res.get("p_value")
                if f_stat is not None and np.isfinite(f_stat) and f_stat > 0:
                    score = min(1.0, float(f_stat) / (float(f_stat) + len(pair) - len(groups)))
                    importance.append({
                        "feature": col,
                        "importance": round(score, 3),
                        "type": "categorical",
                        "method": "anova_eta2",
                        "p_value": round(p_val, 4) if p_val is not None else None
                    })
            else:
                # Chi-square / Cramér's V via the Statistical Engine.
                assoc = chi2_association(pair[col], pair[target])
                chi2 = assoc.get("chi2")
                cramers_v = assoc.get("cramers_v")
                p_value = assoc.get("p_value")
                if chi2 is not None and chi2 > 0:
                    importance.append({
                        "feature": col,
                        "importance": round(min(1.0, float(cramers_v or 0)), 3),
                        "type": "categorical",
                        "method": "chi2_cramers_v",
                        "p_value": round(float(p_value), 4) if p_value is not None else None
                    })
        except Exception:
            continue

    importance.sort(key=lambda x: x["importance"], reverse=True)
    return importance[:5]


def build_evidence(state, df):
    """Build the complete evidence dictionary for insight generation."""
    # Build base evidence
    try:
        base_evidence = build_insight_evidence(df, state.data_summary, token_budget=4000)
    except Exception as evidence_error:
        # Return fallback evidence structure
        base_evidence = {
            "dataset": {}, "data_quality": {}, "target_detection": {},
            "feature_importance": {"top_5": []}, "correlations": {},
            "grouped_analysis": {}, "insight_triggers": [],
            "deep_segmented_analysis": {}, "target_analysis": {},
            "target_correlations": {}, "group_analysis": {},
            "categorical_importance": {"top_5": []},
            "categorical_target_analysis": {}
        }

    # Get target column
    target = get_target_column(state, base_evidence, df)
    if target is None or target not in df.columns:
        return None, base_evidence

    # Compute target correlations
    target_is_numeric = pd.api.types.is_numeric_dtype(df[target])
    if target_is_numeric:
        base_evidence["target_correlations"] = compute_target_correlations(df, target, base_evidence)

    # Build feature importance
    base_evidence = build_feature_importance(df, target, base_evidence)

    # Build quality evidence
    quality = base_evidence.get("data_quality", {})

    # Build target analysis
    target_analysis = analyze_target(df, target)

    # Build evidence dictionary
    evidence = {
        "target_analysis": target_analysis,
        "target_correlations": base_evidence.get("target_correlations", {}),
        "group_analysis": base_evidence.get("group_analysis", {}),
        "data_quality": quality,
        "feature_importance": base_evidence.get("feature_importance", {}),
        "categorical_importance": base_evidence.get("categorical_importance", {}),
        "target_detection": base_evidence.get("target_detection", {"target_column": target}),
        "categorical_target_analysis": base_evidence.get("categorical_target_analysis", {})
    }

    # Add dataset profile
    evidence["dataset_profile"] = getattr(state, "dataset_profile", {})

    return target, evidence