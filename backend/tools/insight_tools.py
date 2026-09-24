"""Defensive, dataset-agnostic evidence generation for the insights pipeline.

Statistical computations (descriptive summaries, distribution checks,
outlier counts, correlations, association tests) are delegated to the
read-only Statistical Engine; this module owns evidence SHAPING for the
insight extractors.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.feature_selection import f_classif, f_regression, mutual_info_classif, mutual_info_regression

from backend.core.constants import NEGATIVE_KEYWORDS, DATE_KEYWORDS
from backend.statistics.bivariate import (
    chi2_from_contingency,
    pearson_significance_pairs,
    series_correlation,
)
from backend.statistics.outliers import column_outlier_evidence
from backend.statistics.univariate import distribution_check, numeric_summary
from backend.utils.target_detection import detect_target_variable
from backend.tools.insight_constants import (
    BASE_MIN_GROUP_DIFF_PCT,
    BASE_MIN_CORRELATION,
    BASE_MIN_FEATURE_IMPORTANCE,
    BASE_MIN_SEGMENT_GAP,
    DIVERSITY_CAPS,
)

# Stable fallback shape used when target detection cannot be performed.
EMPTY_TARGET = {
    "target_column": None,
    "is_numeric": False,
    "confidence": 0,
    "reason": None,
}


def _number(val):
    if val is None or pd.isna(val) or not np.isfinite(val):
        return None
    return round(float(val), 4)


def _classify_distribution(series):
    skew = series.skew()
    if pd.isna(skew):
        return "unknown"
    if skew > 1.0:
        return "right_skewed"
    elif skew < -1.0:
        return "left_skewed"
    return "normal_like"


def _outlier_severity(count, rows):
    pct = (count / rows) * 100 if rows > 0 else 0
    if pct > 15:
        return "high"
    elif pct > 5:
        return "moderate"
    return "low"


def _missing_pattern(series):
    return "random"


def _entropy(series):
    prob = series.value_counts(normalize=True)
    return float(-np.sum(prob * np.log2(prob + 1e-9)))


def _correlation_strength(r_abs):
    if r_abs >= 0.8:
        return "very_strong"
    elif r_abs >= 0.6:
        return "strong"
    elif r_abs >= 0.4:
        return "moderate"
    elif r_abs >= 0.2:
        return "weak"
    return "negligible"


def _token_recommendations(estimated, max_budget):
    if estimated <= max_budget:
        return ["Within acceptable token budget."]
    return ["Truncate high-cardinality categorical values.", "Sample continuous variables summary."]


def _optimize_for_token_budget(evidence, token_budget):
    return {"status": "optimized", "applied_reductions": []}


# ---------------------------------------------------------------------------
# NEW: Unified feature-filtering helpers
# ---------------------------------------------------------------------------

def _is_meta_feature(col_name, target_name):
    """Detect columns that are derived from or leak information about the target."""
    if not target_name:
        return False
    c = str(col_name).lower()
    t = str(target_name).lower()

    # Exact match or obvious prefix/suffix
    if c == t or c.startswith(t + "_") or c.endswith("_" + t):
        return True

    # Contains target name + meta-keyword anywhere
    meta_suffixes = {
        "confidence", "prob", "probability", "score", "likelihood",
        "prediction", "predicted", "flag", "label", "class",
        "rank", "pct", "percentile", "bin", "bucket", "tier",
        "expected", "forecast", "error", "residual", "diff",
    }
    if t in c and any(s in c for s in meta_suffixes):
        return True

    # Standalone meta columns (no target name but clearly model outputs)
    standalone_meta = {
        "prediction", "predicted", "forecast", "expected",
        "confidence", "probability", "score", "class", "proba",
    }
    if any(s in c for s in standalone_meta):
        return True

    return False


def _is_high_cardinality_identifier(df, col, column_semantics=None):
    """Detect identifier-like columns by cardinality ratio or explicit semantics."""
    if column_semantics:
        semantic = column_semantics.get(col, {}).get("inferred_type", "")
        if semantic == "identifier":
            return True

    n_unique = df[col].nunique(dropna=True)
    ratio = n_unique / max(1, len(df))

    if ratio > 0.95:
        return True
    if ratio > 0.80 and any(kw in col.lower() for kw in {"id", "uuid", "serial", "index", "key"}):
        return True
    return False


def _should_skip_feature(col, target, df, column_semantics=None, id_cols=None):
    """Unified filter for feature analysis functions."""
    if col == target:
        return True
    if id_cols and col in id_cols:
        return True
    if df[col].nunique(dropna=True) <= 1:
        return True
    if _is_meta_feature(col, target):
        return True
    if _is_high_cardinality_identifier(df, col, column_semantics):
        return True
    return False


def _empty_evidence(df=None, token_budget=4000):
    columns = list(df.columns) if isinstance(df, pd.DataFrame) else []
    return {
        "dataset": {"rows": len(df) if isinstance(df, pd.DataFrame) else 0, "columns": len(columns),
                    "column_names": columns, "memory_usage_mb": 0, "numeric_columns": [],
                    "categorical_columns": [], "datetime_columns": [], "duplicate_rows": 0,
                    "duplicate_pct": 0},
        "token_budget": _calculate_token_budget(df, {}, token_budget),
        "column_types": {}, "column_semantics": {}, "target_detection": dict(EMPTY_TARGET),
        "descriptive_stats": {}, "distributions": {}, "outliers": {}, "missing_values": {},
        "missing_values_summary": {"total_missing_cells": 0, "total_missing_pct": 0,
                                   "columns_with_missing": 0, "columns_fully_missing": 0,
                                   "rows_with_any_missing": 0, "rows_with_any_missing_pct": 0},
        "correlations": {"significant_pairs": [], "total_significant_pairs": 0},
        "correlation_matrix": {}, "feature_importance": {"target": None, "features": {}, "top_5": []},
        "grouped_analysis": {}, "contribution_analysis": {}, "time_analysis": {},
        "categorical_analysis": {}, "data_quality": {}, "insight_triggers": [],
        "categorical_target_analysis": {},
    }


def build_insight_evidence(df: pd.DataFrame, data_summary: dict = None, token_budget: int = 4000, filename: str = None):
    """Return serializable evidence for any DataFrame; malformed/empty inputs produce valid evidence."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        evidence = _empty_evidence(df if isinstance(df, pd.DataFrame) else None, token_budget)
        evidence["data_quality"] = _compute_quality_score(df, evidence)
        evidence["token_budget"]["optimization"] = _optimize_for_token_budget(evidence, token_budget)
        return evidence

    rows, columns = len(df), list(df.columns)
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    datetime_cols = [c for c in columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    categorical_cols = [c for c in columns if c not in numeric_cols and c not in datetime_cols]
    evidence = _empty_evidence(df, token_budget)
    evidence["dataset"].update({
        "memory_usage_mb": round(float(df.memory_usage(deep=True).sum()) / 1024 ** 2, 2),
        "numeric_columns": numeric_cols, "categorical_columns": categorical_cols,
        "datetime_columns": datetime_cols, "duplicate_rows": int(df.duplicated().sum()),
        "duplicate_pct": round(int(df.duplicated().sum()) / rows * 100, 2),
    })
    evidence["token_budget"] = _calculate_token_budget(df, evidence["dataset"], token_budget)

    for col in columns:
        series, unique = df[col], int(df[col].nunique(dropna=True))
        ratio = unique / rows if rows > 0 else 0
        name = str(col).lower()
        is_identifier = name in {"id", "user_id", "employee_id", "customer_id", "order_id", "transaction_id", "product_id"} or (pd.api.types.is_numeric_dtype(series) and ratio > .95)
        if is_identifier: semantic = "identifier"
        elif pd.api.types.is_datetime64_any_dtype(series): semantic = "datetime"
        elif unique == 2: semantic = "binary"
        elif pd.api.types.is_numeric_dtype(series): semantic = "ordinal_numeric" if unique <= 10 and ratio < .05 else "continuous"
        else: semantic = "categorical" if ratio < .05 else "text"
        evidence["column_types"][col] = str(series.dtype)
        evidence["column_semantics"][col] = {"inferred_type": semantic, "unique_values": unique,
                                               "unique_pct": round(ratio * 100, 2), "id_detected_by": "name" if name.endswith("id") else "none"}

    # Use unified target detection
    target_result = detect_target_variable(df, filename=filename)
    evidence["target_detection"] = target_result
    target = target_result.get("target_column")
    target_is_numeric = target_result.get("is_numeric", False)

    for col in numeric_cols:
        values = df[col].dropna()
        if values.empty: continue
        # Descriptive statistics via the Statistical Engine (single
        # authoritative implementation); shaped into evidence keys below.
        summary = numeric_summary(values)
        mean, std = values.mean(), values.std()
        evidence["descriptive_stats"][col] = {
            "count": int(summary.count), "mean": _number(mean), "median": _number(values.median()),
            "std": _number(std), "var": _number(values.var()), "min": _number(values.min()), "max": _number(values.max()),
            "range": _number(values.max() - values.min()),
            "q25": _number(values.quantile(.25)), "q75": _number(values.quantile(.75)),
            "iqr": _number(values.quantile(.75) - values.quantile(.25)),
            "skewness": _number(summary.skewness), "kurtosis": _number(summary.kurtosis),
            "cv": _number(std / mean) if (mean is not None and std is not None and pd.notna(mean) and pd.notna(std) and mean != 0) else None,
            "zeros_count": int(summary.zeros_count),
            "zeros_pct": round(summary.zeros_count / len(values) * 100, 2),
        }
        if len(values) >= 3 and values.nunique() > 1:
            try:
                check = distribution_check(values, str(col))
                shapiro_stat = check.shapiro_statistic if check else None
                shapiro_p = check.shapiro_p_value if check else None
                shape = (check.shape if check and check.shape != "unknown"
                         else _classify_distribution(values))
                evidence["distributions"][col] = {"shapiro_wilk": {"statistic": _number(shapiro_stat), "p_value": _number(shapiro_p)}, "distribution_shape": shape}
            except (ValueError, FloatingPointError): pass
        if len(values) >= 10 and values.nunique() > 1:
            precomputed = (data_summary or {}).get("outliers", {}).get(col)
            precomputed_iqr = (
                precomputed.get("iqr_method")
                if isinstance(precomputed, dict)
                and isinstance(precomputed.get("iqr_method"), dict)
                else {}
            )
            precomputed_count = (
                precomputed.get("count") if isinstance(precomputed, dict) else None
            )
            if precomputed_count is None:
                precomputed_count = precomputed_iqr.get("count")
            if isinstance(precomputed_count, (int, float)):
                count = int(precomputed_count)
                pct = float(
                    precomputed.get(
                        "pct",
                        precomputed.get(
                            "percentage",
                            precomputed_iqr.get(
                                "pct", precomputed.get("outlier_pct", 0)
                            ),
                        ),
                    )
                    or 0
                )
                severity = precomputed.get("severity") or _outlier_severity(count, rows)
                evidence["outliers"][col] = {
                    "iqr_method": {"count": count, "pct": pct},
                    "severity": severity,
                }
            else:
                # IQR outlier counts via the Statistical Engine (evidence
                # only; no treatment decision happens here).
                item = column_outlier_evidence(df[col], col, method="iqr", threshold=1.5)
                count = item.count if item.analyzed else 0
                evidence["outliers"][col] = {
                    "iqr_method": {"count": int(count), "pct": round(count / rows * 100, 2)},
                    "severity": _outlier_severity(int(count), rows),
                }

    missing = df.isna().sum(); total_cells = rows * len(columns)
    evidence["missing_values"] = {c: {"count": int(n), "pct": round(n / rows * 100, 2), "pattern": _missing_pattern(df[c])} for c, n in missing.items() if n}
    evidence["missing_values_summary"] = {"total_missing_cells": int(missing.sum()), "total_missing_pct": round(missing.sum() / total_cells * 100, 2) if total_cells else 0, "columns_with_missing": int((missing > 0).sum()), "columns_fully_missing": int((missing == rows).sum()), "rows_with_any_missing": int(df.isna().any(axis=1).sum()), "rows_with_any_missing_pct": round(df.isna().any(axis=1).sum() / rows * 100, 2)}

    _add_correlations(df, evidence, numeric_cols)
    evidence["target_correlations"] = target_correlations(df, target, evidence["column_semantics"])

    # FIX: Use the full ensemble-based importance instead of the simple proxy.
    evidence["feature_importance"] = _calculate_feature_importance(
        df, target, evidence["column_semantics"], numeric_cols
    )

    if target and target in df.columns and not target_is_numeric:
        evidence["categorical_target_analysis"] = _categorical_target_analysis(df, target, evidence["column_semantics"])

    evidence["deep_segmented_analysis"] = _deep_segmented_analysis(df, target, evidence["column_semantics"])
    evidence["target_analysis"] = _target_analysis(df, target, evidence["column_semantics"])
    evidence["group_analysis"] = group_analysis(df, target)
    evidence["grouped_analysis"] = group_analysis(df, target)
    evidence["time_analysis"] = _time_analysis(df)
    for col in categorical_cols:
        counts = df[col].dropna().value_counts()
        if not counts.empty:
            evidence["categorical_analysis"][col] = {"unique_values": int(counts.size), "top_values": {str(k): int(v) for k, v in counts.head(10).items()}, "top_value_pct": round(counts.iloc[0] / rows * 100, 2), "entropy": _number(_entropy(df[col]))}
    evidence["data_quality"] = _compute_quality_score(df, evidence)
    evidence["insight_triggers"] = _generate_insight_triggers(evidence)
    evidence["token_budget"]["optimization"] = _optimize_for_token_budget(evidence, token_budget)
    return evidence


def _categorical_target_analysis(df, target, semantics):
    """Generate rich evidence when target is categorical."""
    results = {}
    if not target or target not in df.columns:
        return results

    target_series = df[target].dropna()
    if target_series.empty:
        return results

    vc = target_series.value_counts()
    results["distribution"] = {
        "unique_values": int(vc.size),
        "top_values": {str(k): int(v) for k, v in vc.head(10).items()},
        "entropy": _number(_entropy(target_series)),
        "balance": "balanced" if vc.size > 1 and vc.min() / vc.max() > 0.5 else "imbalanced"
    }

    cat_cols = [c for c in df.columns
                if c != target
                and semantics.get(c, {}).get("inferred_type") in {"binary", "categorical"}
                and df[c].nunique() <= 20]

    results["associations"] = {}
    for col in cat_cols:
        try:
            pair = df[[target, col]].dropna()
            if len(pair) < 20:
                continue
            contingency = pd.crosstab(pair[target], pair[col])
            if contingency.shape[0] < 2 or contingency.shape[1] < 2:
                continue

            # FIX: Reordered — check perfect association (single row) BEFORE the generic <2 check
            if contingency.shape[0] == 1:
                target_val = str(contingency.index[0])
                results["associations"][col] = {
                    "chi2": None, "p_value": 0.0, "cramers_v": 1.0,
                    "significant": True,
                    "perfect_association": True,
                    "target_value": target_val,
                    "strongest_association": {
                        "target_value": target_val,
                        "column_value": "any",
                        "lift": 999.0,
                    }
                }
                continue

            # Chi-square / Cramér's V via the Statistical Engine.
            assoc = chi2_from_contingency(contingency)
            chi2 = assoc.get("chi2")
            p_val = assoc.get("p_value")
            n = assoc.get("n") or contingency.sum().sum()
            cramers_v = assoc.get("cramers_v") or 0

            target_marginal = pair[target].value_counts(normalize=True)
            col_marginal = pair[col].value_counts(normalize=True)
            max_lift = 0
            max_cell = None

            for t_val in contingency.index:
                for c_val in contingency.columns:
                    observed = contingency.loc[t_val, c_val] / n
                    expected_prob = target_marginal.get(t_val, 0) * col_marginal.get(c_val, 0)
                    if expected_prob > 0:
                        lift = observed / expected_prob
                        if lift > max_lift:
                            max_lift = lift
                            max_cell = (t_val, c_val, lift)

            results["associations"][col] = {
                "chi2": round(float(chi2), 3),
                "p_value": round(float(p_val), 4),
                "cramers_v": round(float(cramers_v), 3),
                "significant": bool(p_val < 0.05),
                "strongest_association": {
                    "target_value": str(max_cell[0]) if max_cell else None,
                    "column_value": str(max_cell[1]) if max_cell else None,
                    "lift": round(float(max_cell[2]), 2) if max_cell else None
                }
            }
        except Exception:
            continue

    text_cols = [c for c in df.columns
                 if semantics.get(c, {}).get("inferred_type") == "text"
                 and df[c].nunique(dropna=True) > 50
                 and c.lower() not in {"link", "url", "source", "name", "href"}]

    results["text_by_category"] = {}
    for text_col in text_cols:
        try:
            text_stats = {}
            for t_val in target_series.unique():
                subset = df[df[target] == t_val][text_col].dropna()
                if len(subset) == 0:
                    continue
                lengths = subset.astype(str).str.len()
                word_counts = subset.astype(str).str.split().str.len()
                text_stats[str(t_val)] = {
                    "count": int(len(subset)),
                    "avg_length": round(float(lengths.mean()), 1),
                    "median_length": round(float(lengths.median()), 1),
                    "max_length": int(lengths.max()),
                    "avg_word_count": round(float(word_counts.mean()), 1)
                }
            if text_stats:
                results["text_by_category"][text_col] = text_stats
        except Exception:
            continue

    results["missing_by_category"] = {}
    for col in df.columns:
        if col == target:
            continue
        try:
            missing_by_target = df.groupby(target)[col].apply(lambda x: x.isna().sum() / len(x) * 100).round(2)
            if missing_by_target.max() > 5:
                results["missing_by_category"][col] = {
                    str(k): float(v) for k, v in missing_by_target.items()
                }
        except Exception:
            continue

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    results["numeric_by_category"] = {}
    for col in numeric_cols:
        if col == target:
            continue
        try:
            grouped = df.groupby(target)[col].agg(["mean", "median", "std", "count"]).round(2)
            if len(grouped) < 2:
                continue
            baseline = grouped["mean"].mean()
            grouped["diff_pct"] = ((grouped["mean"] - baseline) / max(abs(baseline), 0.001) * 100).round(1)

            max_group = grouped["mean"].idxmax()
            min_group = grouped["mean"].idxmin()
            gap = ((grouped.loc[max_group, "mean"] - grouped.loc[min_group, "mean"]) / max(grouped.loc[min_group, "mean"], 0.001) * 100)

            results["numeric_by_category"][col] = {
                "baseline_mean": round(baseline, 2),
                "groups": {str(k): {"mean": v["mean"], "diff_pct": v["diff_pct"], "count": int(v["count"])} for k, v in grouped.iterrows()},
                "max_group": str(max_group),
                "min_group": str(min_group),
                "gap_pct": round(gap, 1)
            }
        except Exception:
            continue

    return results


def _calculate_feature_importance(df, target, column_semantics, numeric_cols):
    """Ensemble feature importance using correlation, MI, F-value and Random Forest."""
    empty = {"target": None, "features": {}, "top_5": []}
    if target is None or target not in df.columns or len(df) < 10:
        return empty
    y_raw = df[target]
    if not pd.api.types.is_numeric_dtype(y_raw):
        return empty

    task_type = "classification" if y_raw.nunique(dropna=True) <= 20 else "regression"
    importance = {}

    id_cols = {
        c for c in df.columns
        if any(kw in c.lower() for kw in NEGATIVE_KEYWORDS)
    }

    for col in numeric_cols:
        # FIX: unified skip logic (meta-features + high-cardinality identifiers)
        if _should_skip_feature(col, target, df, column_semantics, id_cols):
            continue

        pair = df[[col, target]].dropna()
        if len(pair) < 10 or pair[target].nunique() <= 1:
            continue

        X, y = pair[[col]].values, pair[target].values

        # FIX: Guard against zero-variance before correlation
        if pair[col].std() == 0 or pd.Series(y).std() == 0:
            continue

        scores = {
            "correlation": abs(float(np.corrcoef(pair[col], y)[0, 1]))
        }

        for key, fn in (
            ("mutual_information",
             mutual_info_classif if task_type == "classification" else mutual_info_regression),
            ("f_value",
             f_classif if task_type == "classification" else f_regression),
        ):
            try:
                value = fn(X, y, random_state=42)[0] if key == "mutual_information" else fn(X, y)[0][0]
                scores[key] = float(value) if np.isfinite(value) else 0
            except (ValueError, TypeError):
                scores[key] = 0

        try:
            model = (
                RandomForestClassifier(n_estimators=30, max_depth=5, random_state=42)
                if task_type == "classification"
                else RandomForestRegressor(n_estimators=30, max_depth=5, random_state=42)
            )
            model.fit(X, y)
            scores["random_forest"] = float(model.feature_importances_[0])
        except (ValueError, TypeError):
            scores["random_forest"] = 0

        normalized = {k: min(1.0, v) if np.isfinite(v) else 0 for k, v in scores.items()}
        importance[col] = {
            "scores": {k: round(v, 4) for k, v in normalized.items()},
            "ensemble_score": round(sum(normalized.values()) / len(normalized), 4),
            "rank": 0,
            "method": "ensemble",
        }

    ranked = sorted(importance, key=lambda c: importance[c]["ensemble_score"], reverse=True)
    for rank, col in enumerate(ranked, 1):
        importance[col]["rank"] = rank

    return {
        "target": target,
        "task_type": task_type,
        "method": "ensemble",
        "features": importance,
        "top_5": ranked[:5],
    }


def _calculate_token_budget(df, dataset_info, max_budget):
    df = df if isinstance(df, pd.DataFrame) else pd.DataFrame(); max_budget = int(max_budget or 4000); max_budget = max(1, max_budget)
    sample_size = min(1000, len(df)); avg_chars = len(df.head(sample_size).to_string()) / sample_size if sample_size else 0
    numeric = dataset_info.get("numeric_columns", []) if isinstance(dataset_info, dict) else []
    categorical = dataset_info.get("categorical_columns", []) if isinstance(dataset_info, dict) else []
    cat_tokens = sum(min(int(df[c].nunique(dropna=True)), 20) * 10 for c in categorical if c in df.columns)
    estimated = 500 + len(df.columns) * 50 + avg_chars * len(df) / 40 + len(numeric) * 100 + cat_tokens
    return {"max_budget": max_budget, "estimated_needed": int(estimated), "budget_status": "within_budget" if estimated <= max_budget else "exceeds_budget", "overflow_pct": round(max(0, estimated - max_budget) / max_budget * 100, 2), "breakdown": {"base_structure": 500, "column_descriptions": len(df.columns) * 50, "data_sample": int(avg_chars * len(df) / 40), "statistics": len(numeric) * 100, "categorical_values": cat_tokens}, "recommendations": _token_recommendations(estimated, max_budget)}


def _add_correlations(df, evidence, numeric_cols):
    # Pearson pairs + t-distribution p-values via the Statistical Engine.
    usable = [c for c in numeric_cols if df[c].dropna().nunique() > 1]
    engine_pairs = pearson_significance_pairs(df, columns=usable)
    pairs = [
        {
            "column1": p.column_a,
            "column2": p.column_b,
            "pearson_r": _number(p.correlation),
            "p_value": _number(p.p_value),
            "n": p.n,
            "significant": bool(p.significant),
            "strength": p.strength,
            "direction": p.direction,
        }
        for p in engine_pairs
        if p.n >= 4 and abs(p.correlation) < 1
    ]
    evidence["correlations"] = {"significant_pairs": pairs[:10], "total_significant_pairs": sum(p["significant"] for p in pairs)}
    evidence["correlation_matrix"] = {"method": "pearson", "columns": usable, "top_10": pairs[:10]} if pairs else {}


def target_correlations(df, target, column_semantics=None):
    """SAFE: only computes correlations when target is numeric.
    FIX: skips meta-features and high-cardinality identifiers.
    Correlation values are computed via the Statistical Engine primitive.
    """
    correlations = {}
    if target is None or target not in df.columns:
        return correlations
    if not pd.api.types.is_numeric_dtype(df[target]):
        return correlations

    numeric = df.select_dtypes(include=[np.number])
    id_cols = {
        c for c in df.columns
        if any(kw in c.lower() for kw in NEGATIVE_KEYWORDS)
    }

    for col in numeric.columns:
        if _should_skip_feature(col, target, df, column_semantics, id_cols):
            continue
        try:
            corr = series_correlation(df[col], df[target], method="spearman")
            if corr is not None:
                correlations[col] = round(float(corr), 3)
        except Exception:
            pass
    return dict(sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True))


def feature_importance_proxy(df, target, column_semantics=None):
    """SAFE: only numeric target supported.
    FIX: applies the same unified skip filters; math delegated to engine.
    """
    importance = {}
    if target is None or target not in df.columns:
        return []
    if not pd.api.types.is_numeric_dtype(df[target]):
        return []

    id_cols = {
        c for c in df.columns
        if any(kw in c.lower() for kw in NEGATIVE_KEYWORDS)
    }

    for col in df.select_dtypes(include=[np.number]).columns:
        if _should_skip_feature(col, target, df, column_semantics, id_cols):
            continue
        try:
            pair = df[[col, target]].dropna()
            if len(pair) < 10:
                continue
            corr = series_correlation(pair[col], pair[target], method="spearman")
            if corr is not None:
                importance[col] = abs(float(corr))
        except Exception:
            pass
    return sorted(
        [{"feature": k, "importance": round(v, 3)} for k, v in importance.items()],
        key=lambda x: x["importance"],
        reverse=True
    )[:5]


def group_analysis(df, target):
    """SAFE group analysis: skips if target is not numeric."""
    results = {}
    if target is None or target not in df.columns:
        return results
    if not pd.api.types.is_numeric_dtype(df[target]):
        return results

    categorical = [
        c for c in df.columns
        if c != target
        and (df[c].nunique() < 20 or df[c].dtype == "object")
        and not pd.api.types.is_datetime64_any_dtype(df[c])
        and (
            not any(kw in c.lower() for kw in DATE_KEYWORDS)
            or (pd.api.types.is_numeric_dtype(df[c]) and df[c].nunique() < 20)
        )
    ]
    for col in categorical:
        if col not in df.columns or col == target:
            continue
        try:
            results[col] = (
                df.groupby(col)[target]
                .agg(mean="mean", median="median", count="count")
                .sort_values("mean", ascending=False)
                .head(5)
                .round(2)
                .to_dict("index")
            )
        except Exception:
            continue
    return results


def _time_analysis(df):
    result = {}
    for col in df.columns:
        series = df[col] if pd.api.types.is_datetime64_any_dtype(df[col]) else (pd.to_datetime(df[col], errors="coerce") if df[col].dtype == object else pd.Series(dtype="datetime64[ns]"))
        valid = series.dropna()
        if valid.empty or len(valid) / max(1, len(df)) < .5: continue
        monthly = valid.dt.month.value_counts().sort_index()
        result[col] = {"date_range": {"start": str(valid.min()), "end": str(valid.max()), "days": int((valid.max() - valid.min()).days) + 1}, "monthly_distribution": {int(k): int(v) for k, v in monthly.items()}, "peak_month": int(monthly.idxmax()) if not monthly.empty else None}
    return result


def _compute_quality_score(df, evidence):
    missing = float(evidence.get("missing_values_summary", {}).get("total_missing_pct", 0) or 0); duplicate = float(evidence.get("dataset", {}).get("duplicate_pct", 0) or 0)
    outliers = [float(v.get("iqr_method", {}).get("pct", 0) or 0) for v in evidence.get("outliers", {}).values()]
    scores = [max(0, 100 - missing * 2), max(0, 100 - duplicate * 5), max(0, 100 - (float(np.mean(outliers)) if outliers else 0) * 3)]
    overall = float(np.mean(scores)); return {"overall_score": round(overall, 1), "completeness": round(scores[0], 1), "uniqueness": round(scores[1], 1), "consistency": round(scores[2], 1), "rating": "excellent" if overall >= 90 else "good" if overall >= 75 else "fair" if overall >= 60 else "poor"}


def _generate_insight_triggers(evidence):
    triggers = []
    for col, dist in evidence.get("distributions", {}).items():
        stat = dist.get("shapiro_wilk", {}).get("statistic"); shape = dist.get("distribution_shape")
        if shape in {"right_skewed", "left_skewed"}: triggers.append({"type": "skewed_distribution", "column": col, "severity": "high" if stat is not None and abs(stat - 1) > .3 else "moderate", "confidence": "high"})
    for corr in evidence.get("correlations", {}).get("significant_pairs", []):
        if corr.get("significant") and corr.get("strength") in {"moderate", "strong", "very_strong"}: triggers.append({"type": "significant_correlation", "column": corr.get("column1"), "related_column": corr.get("column2"), "severity": "high" if corr.get("strength") in {"strong", "very_strong"} else "moderate", "confidence": "high"})
    summary = evidence.get("missing_values_summary", {})
    if summary.get("columns_with_missing", 0): triggers.append({"type": "missing_values_present", "column": "multiple", "severity": "moderate" if summary.get("total_missing_pct", 0) > 5 else "low", "confidence": "high", "columns_affected": summary.get("columns_with_missing", 0)})

    cat_target = evidence.get("categorical_target_analysis", {})
    if cat_target.get("distribution", {}).get("balance") == "imbalanced":
        triggers.append({"type": "imbalanced_target", "column": evidence.get("target_detection", {}).get("target_column"), "severity": "moderate", "confidence": "high"})

    return triggers


def _deep_segmented_analysis(df, target, semantics):
    """SAFE: only runs when target is numeric.
    FIX: skips meta-features and identifier-like columns from segmentation.
    """
    results = {}
    if not target or target not in df.columns:
        return results
    if not pd.api.types.is_numeric_dtype(df[target]):
        return results

    id_cols = {
        c for c in df.columns
        if any(kw in c.lower() for kw in NEGATIVE_KEYWORDS)
    }

    cat_cols = [
        c for c in df.columns
        if c != target
        and not _should_skip_feature(c, target, df, semantics, id_cols)
        and (
            semantics.get(c, {}).get("inferred_type") in {"binary", "categorical", "ordinal_numeric"}
            or (
                pd.api.types.is_numeric_dtype(df[c])
                and df[c].nunique() < 20
                and semantics.get(c, {}).get("inferred_type") == "continuous"
                and any(kw in c.lower() for kw in DATE_KEYWORDS)
            )
        )
    ]

    for col in cat_cols:
        grouped = df.groupby(col)[target].agg(["mean", "median", "std", "count"])
        if len(grouped) < 2 or grouped["count"].min() < 5:
            continue

        baseline = grouped["mean"].mean()
        grouped["diff_pct"] = ((grouped["mean"] - baseline) / max(abs(baseline), 0.001) * 100).round(2)
        grouped["effect_size"] = (grouped["mean"] - baseline) / grouped["std"].clip(lower=0.01)

        max_group = grouped["mean"].idxmax()
        min_group = grouped["mean"].idxmin()

        lowest_mean = grouped.loc[min_group, "mean"]
        highest_mean = grouped.loc[max_group, "mean"]

        key_insight = {
            "highest_group": str(max_group),
            "highest_mean": round(highest_mean, 3),
            "lowest_group": str(min_group),
            "lowest_mean": round(lowest_mean, 3),
        }

        # FIX: percent gap unreliable on near-zero baseline/lowest_mean — use baseline as fallback denominator
        if abs(lowest_mean) < 1e-9 or abs(lowest_mean) < 0.05 * abs(baseline):
            gap = ((highest_mean - lowest_mean) / max(abs(baseline), 0.01)) * 100
            key_insight["gap_reliability"] = "low_baseline"
        else:
            gap = ((highest_mean - lowest_mean) / max(abs(lowest_mean), 0.01)) * 100

        key_insight["gap_pct"] = round(min(gap, 200.0), 2)  # Cap at 200.0

        results[col] = {
            "baseline_mean": round(baseline, 3),
            "groups": {
                str(k): {
                    "mean": round(v["mean"], 3),
                    "count": int(v["count"]),
                    "diff_from_baseline_pct": v["diff_pct"],
                    "effect_size": round(v["effect_size"], 3),
                }
                for k, v in grouped.iterrows()
            },
            "key_insight": key_insight,
        }

    return results


def _target_analysis(df, target, semantics):
    if not target or target not in df.columns:
        return {"error": "No target variable detected"}

    target_series = df[target].dropna()
    if target_series.empty:
        return {"error": "Target variable is empty"}

    result = {
        "target_variable": target,
        "target_type": str(target_series.dtype),
        "total_records": len(target_series),
        "overall_stats": {},
        "thresholds": {},
        "top_segments": {},
        "risk_groups": {},
    }

    if pd.api.types.is_numeric_dtype(target_series):
        result["overall_stats"] = {
            "mean": _number(target_series.mean()),
            "median": _number(target_series.median()),
            "std": _number(target_series.std()),
            "min": _number(target_series.min()),
            "max": _number(target_series.max()),
            "q25": _number(target_series.quantile(0.25)),
            "q75": _number(target_series.quantile(0.75)),
            "skewness": _number(target_series.skew()),
            "zeros_count": int((target_series == 0).sum()),
            "zeros_pct": round((target_series == 0).sum() / len(target_series) * 100, 2),
        }
        result["thresholds"] = {
            "high": _number(target_series.quantile(0.75)),
            "very_high": _number(target_series.quantile(0.90)),
            "extreme": _number(target_series.quantile(0.95)),
        }

        high_threshold = target_series.quantile(0.90)
        high_risk_mask = target_series >= high_threshold
        high_risk_df = df[high_risk_mask]
        normal_df = df[~high_risk_mask]

        id_cols = {
            c for c in df.columns
            if any(kw in c.lower() for kw in NEGATIVE_KEYWORDS)
        }

        cat_cols = [
            c for c in df.columns
            if c != target
            and not _should_skip_feature(c, target, df, semantics, id_cols)
            and semantics.get(c, {}).get("inferred_type") in
            {"binary", "categorical", "ordinal_numeric"}
        ]

        for col in cat_cols:
            if df[col].isna().all():
                continue

            risk_dist = high_risk_df[col].value_counts(normalize=True).to_dict()
            normal_dist = normal_df[col].value_counts(normalize=True).to_dict()

            over_represented = {}
            for k, risk_pct in risk_dist.items():
                norm_pct = normal_dist.get(k, 0)
                if norm_pct > 0:
                    ratio = risk_pct / norm_pct
                    if ratio > 1.25:
                        over_represented[str(k)] = round(ratio, 2)

            if over_represented:
                result["risk_groups"][col] = over_represented

    return result