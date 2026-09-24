"""Group statistics: conditional summaries and target associations.

All functions are read-only. Group aggregation answers "does the value of a
categorical feature separate a numeric target?" — evidence for insights, not
a cleaning instruction.
"""
from typing import List, Optional, Sequence

import numpy as np
import pandas as pd

from backend.statistics.bivariate import (
    anova_test,
    chi2_association,
    kruskal_wallis,
    mann_whitney_u,
    series_correlation,
)
from backend.statistics.contracts import (
    AssociationTest,
    GroupStatistics,
    GroupStatisticsEntry,
    GroupValueStats,
    TargetAssociations,
)
from backend.statistics.helpers import (
    is_identifier_like,
    json_safe_number,
)

# Association guards (analysis hygiene, mirroring the historical insight
# pipeline so results remain comparable):
MIN_PAIR_ROWS = 10              # minimum rows supporting any association
MAX_MISSING_RATIO = 0.30        # skip features missing more than this share
MAX_CARDINALITY_RATIO = 0.20    # skip high-cardinality pseudo-identifiers
MAX_CATEGORICAL_CARDINALITY = 100
MIN_GROUP_SIZE_FOR_ANOVA = 5


def group_statistics(
    df: pd.DataFrame,
    value_column: str,
    group_columns: Optional[Sequence[str]] = None,
    max_groups_per_column: int = 12,
) -> GroupStatistics:
    """Mean/median/count of a numeric value column per category group."""
    result = GroupStatistics()
    if df.empty or value_column not in df.columns:
        result.warnings.append("Value column missing or empty dataset")
        return result

    values = pd.to_numeric(df[value_column], errors="coerce")
    if values.notna().sum() == 0:
        result.warnings.append(f"Value column '{value_column}' has no numeric observations")
        return result

    if group_columns is None:
        group_columns = [
            c for c in df.columns
            if c != value_column
            and not is_identifier_like(df[c], c)
            and (
                df[c].dtype == object
                or pd.api.types.is_string_dtype(df[c])
                or pd.api.types.is_bool_dtype(df[c])
                or isinstance(df[c].dtype, pd.CategoricalDtype)
            )
        ]

    for group_col in group_columns:
        if group_col == value_column or group_col not in df.columns:
            continue
        try:
            grouped = pd.DataFrame({
                "group": df[group_col].astype("string"),
                "value": values,
            }).dropna()
            agg = (
                grouped.groupby("group")["value"]
                .agg(mean="mean", median="median", std="std", count="count")
                .sort_values("mean", ascending=False, na_position="last")
            )
            entry = GroupStatisticsEntry(
                group_column=str(group_col),
                value_column=str(value_column),
                groups=[
                    GroupValueStats(
                        group=str(name),
                        count=int(row["count"]),
                        mean=json_safe_number(row["mean"]),
                        median=json_safe_number(row["median"]),
                        std=json_safe_number(row["std"]),
                    )
                    for name, row in agg.head(max_groups_per_column).iterrows()
                ],
            )
            total_groups = int(agg.shape[0])
            if total_groups > max_groups_per_column:
                entry.note = (
                    f"{total_groups} groups present; showing top "
                    f"{max_groups_per_column} by mean."
                )
            result.entries.append(entry)
        except Exception as exc:
            result.warnings.append(
                f"group_statistics failed for '{group_col}': {exc}"
            )
    return result


def _feature_valid(
    series: pd.Series,
    col_name,
    n_rows: int,
    exclude: set,
) -> bool:
    """Shared hygiene filters for target associations."""
    if col_name in exclude:
        return False
    non_null_ratio_missing = series.isna().sum() / max(n_rows, 1)
    if non_null_ratio_missing > MAX_MISSING_RATIO:
        return False
    unique_count = int(series.nunique(dropna=True))
    # High unique-ratio filter applies only to non-numeric columns
    # (high-cardinality free text / pseudo-ids). Continuous numeric
    # measurements (price, area, sensor readings) legitimately have unique
    # ratios near 1.0 and must still participate in Spearman / Mann-Whitney.
    # Integer near-unique IDs are already rejected by is_identifier_like.
    if not pd.api.types.is_numeric_dtype(series) and unique_count > 20:
        unique_ratio = unique_count / max(n_rows, 1)
        if unique_ratio > MAX_CARDINALITY_RATIO:
            return False
    return True


def target_associations(
    df: pd.DataFrame,
    target: str,
    exclude_columns: Optional[Sequence[str]] = None,
) -> TargetAssociations:
    """Rank feature→target associations with appropriate statistical tests.

    - numeric target vs numeric feature      : |Spearman rho|
    - numeric target vs categorical feature  : one-way ANOVA eta²-like score
    - categorical target vs categorical feat : chi² / Cramér's V
    - categorical (binary) target vs numeric : Mann-Whitney U + |rank-biserial|
    - categorical (multi-class) vs numeric   : Kruskal-Wallis H + eta²_H

    Identifier-like columns and meta-leakage columns supplied via
    `exclude_columns` never participate.
    """
    result = TargetAssociations(target=str(target), target_kind="numeric")
    if df is None or df.empty or target not in df.columns:
        return result

    target_series = df[target]
    exclude = set(exclude_columns or [])
    exclude.add(str(target))
    n_rows = int(len(df))

    if pd.api.types.is_numeric_dtype(target_series):
        result.target_kind = "numeric"
    else:
        result.target_kind = "categorical"

    for col in df.columns:
        col_str = str(col)
        if col_str in exclude or is_identifier_like(df[col], col):
            continue
        series = df[col]
        if not _feature_valid(series, col_str, n_rows, exclude):
            continue

        unique_count = int(series.nunique(dropna=True))
        # Numeric dtype with very few distinct values (e.g. SeniorCitizen 0/1,
        # Pclass 1/2/3) is semantically categorical for association tests.
        # Keep a pure-numeric path for continuous measures only.
        is_low_card_numeric = (
            pd.api.types.is_numeric_dtype(series)
            and not pd.api.types.is_bool_dtype(series)
            and 2 <= unique_count <= 15
        )
        feature_is_numeric = (
            pd.api.types.is_numeric_dtype(series)
            and not pd.api.types.is_bool_dtype(series)
            and not is_low_card_numeric
        )
        feature_is_categorical = (
            (not feature_is_numeric or is_low_card_numeric)
            and unique_count <= MAX_CATEGORICAL_CARDINALITY
            and unique_count >= 2
            and (
                not feature_is_numeric  # pure object/string/bool cats
                or is_low_card_numeric  # 0/1 flags, small ordinals
            )
        )

        if result.target_kind == "numeric":
            pair = df[[col_str, str(target)]].dropna()
            if len(pair) < MIN_PAIR_ROWS or pair[target].nunique() <= 1:
                continue
            if feature_is_numeric:
                r = series_correlation(pair[col_str], pair[target], method="spearman")
                if r is None:
                    continue
                result.numeric.append(AssociationTest(
                    feature=col_str, target=str(target),
                    kind="numeric_spearman", score=abs(r), n=int(len(pair)),
                    method="spearman",
                ))
            elif feature_is_categorical:
                groups = [
                    g[target].dropna()
                    for _, g in pair.groupby(col_str)
                    if len(g) >= MIN_GROUP_SIZE_FOR_ANOVA
                ]
                if len(groups) < 2:
                    continue
                anova_res = anova_test(groups)
                f_stat = anova_res.get("f_statistic")
                p_val = anova_res.get("p_value")
                if f_stat is None or not np.isfinite(f_stat) or f_stat <= 0:
                    continue
                n_total = sum(len(g) for g in groups)
                score = min(1.0, float(f_stat) / (float(f_stat) + n_total - len(groups)))
                result.categorical.append(AssociationTest(
                    feature=col_str, target=str(target),
                    kind="anova_eta2", score=round(score, 4),
                    statistic=round(float(f_stat), 4),
                    p_value=round(p_val, 6) if p_val is not None else None,
                    n=n_total, method="anova_eta2",
                ))
        else:
            # Categorical target
            pair = df[[col_str, str(target)]].dropna()
            if len(pair) < MIN_PAIR_ROWS * 2:
                continue

            if feature_is_numeric:
                # Categorical target × numeric feature.
                target_levels = list(pair[target].dropna().unique())
                if len(target_levels) < 2:
                    continue
                groups = [
                    pair.loc[pair[target] == lvl, col_str]
                    for lvl in target_levels
                ]
                groups = [g for g in groups if len(g) >= 1]
                if len(groups) < 2:
                    continue

                if len(groups) == 2:
                    # Binary → Mann-Whitney U + |rank-biserial|
                    u_stat, p_val = mann_whitney_u(groups[0], groups[1])
                    if u_stat is None:
                        continue
                    n1, n2 = int(len(groups[0])), int(len(groups[1]))
                    denom = float(n1) * float(n2)
                    r_rb = abs(1.0 - (2.0 * float(u_stat)) / denom) if denom > 0 else 0.0
                    r_rb = float(min(1.0, max(0.0, r_rb)))
                    result.numeric.append(AssociationTest(
                        feature=col_str,
                        target=str(target),
                        kind="mann_whitney",
                        score=round(r_rb, 4),
                        statistic=round(float(u_stat), 4),
                        p_value=round(float(p_val), 6) if p_val is not None else None,
                        n=n1 + n2,
                        method="mann_whitney",
                    ))
                else:
                    # Multi-class → Kruskal-Wallis H; score = eta²_H = H/(n-1)
                    h_stat, p_val = kruskal_wallis(*groups)
                    if h_stat is None or not np.isfinite(h_stat) or h_stat < 0:
                        continue
                    n_total = sum(len(g) for g in groups)
                    score = min(1.0, float(h_stat) / max(n_total - 1, 1))
                    result.numeric.append(AssociationTest(
                        feature=col_str,
                        target=str(target),
                        kind="kruskal_wallis",
                        score=round(score, 4),
                        statistic=round(float(h_stat), 4),
                        p_value=round(float(p_val), 6) if p_val is not None else None,
                        n=n_total,
                        method="kruskal_wallis",
                    ))
            elif feature_is_categorical:
                assoc = chi2_association(pair[col_str], pair[target])
                if assoc.get("cramers_v") is None:
                    continue
                result.categorical.append(AssociationTest(
                    feature=col_str, target=str(target),
                    kind="chi2_cramers_v",
                    score=float(assoc["cramers_v"]),
                    statistic=assoc.get("chi2"),
                    p_value=assoc.get("p_value"),
                    n=int(assoc["n"]),
                    method="chi2_cramers_v",
                ))

    result.numeric.sort(key=lambda t: t.score, reverse=True)
    result.categorical.sort(key=lambda t: t.score, reverse=True)
    return result