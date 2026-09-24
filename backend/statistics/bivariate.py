"""Bivariate analysis: correlations and association tests (read-only).

Numeric correlation is only computed on genuine numeric columns — raw text
and identifiers never participate. Categorical↔categorical relationships are
measured with chi-square/Cramér's V; numeric-target vs categorical-feature
relationships use one-way ANOVA.
"""
import scipy.stats as stats

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from backend.statistics.contracts import (
    MAX_CORRELATION_COLUMNS,
    AssociationTest,
    CorrelationAnalysis,
    CorrelationPair,
)
from backend.statistics.helpers import (
    correlation_p_value,
    correlation_strength_label,
    is_identifier_like,
    is_ordinal_categorical,
    json_safe_number,
    strength_label,
)

VALID_METHODS = {"pearson", "spearman", "kendall"}


def series_correlation(a: pd.Series, b: pd.Series, method: str = "spearman") -> Optional[float]:
    """Pairwise correlation between two series (None when undefined)."""
    method = method.lower().strip()
    if method not in VALID_METHODS:
        raise ValueError(f"Invalid correlation method '{method}'. Use {sorted(VALID_METHODS)}.")
    pair = pd.concat([pd.to_numeric(a, errors="coerce"),
                      pd.to_numeric(b, errors="coerce")], axis=1).dropna()
    if len(pair) < 2:
        return None
    try:
        r = pair.iloc[:, 0].corr(pair.iloc[:, 1], method=method)
        if pd.isna(r) or not np.isfinite(r):
            return None
        return round(float(r), 6)
    except Exception:
        return None


def _eligible_numeric_columns(
    df: pd.DataFrame,
    respect_identifiers: bool = True,
) -> Tuple[List[str], Dict[str, str]]:
    """Numeric columns that may participate in correlation analysis.

    Boolean and identifier-like numeric columns are excluded (with reasons):
    correlating row IDs or 0/1 flags produces statistically meaningless
    output.
    """
    eligible: List[str] = []
    excluded: Dict[str, str] = {}
    for col in df.select_dtypes(include=[np.number]).columns:
        series = df[col]
        if pd.api.types.is_bool_dtype(series):
            excluded[str(col)] = "boolean column"
            continue
        if respect_identifiers and is_identifier_like(series, col):
            excluded[str(col)] = "identifier-like column"
            continue
        # Zero-variance check FIRST: a constant column's most precise reason
        # is its lack of variance (an ordinal-categorical reading would be
        # misleading for e.g. [3.14] * n).
        std = pd.to_numeric(series, errors="coerce").std()
        if std is None or pd.isna(std) or float(std) <= 0:
            excluded[str(col)] = "constant column (zero variance)"
            continue
        if is_ordinal_categorical(series, col):
            excluded[str(col)] = "ordinal categorical variable"
            continue
        eligible.append(str(col))
    return eligible, excluded


def correlation_matrix(
    df: pd.DataFrame,
    method: str = "spearman",
    min_variance: float = 0.0,
    max_columns: Optional[int] = None,
    respect_identifiers: bool = True,
) -> CorrelationAnalysis:
    """Full numeric correlation matrix plus ranked top pairs.

    Constant / zero-variance columns are excluded. The matrix keeps full
    float precision; callers may round for display.
    """
    method = method.lower().strip()
    if method not in VALID_METHODS:
        raise ValueError(
            f"Invalid correlation method '{method}'. Use {sorted(VALID_METHODS)}."
        )

    eligible, excluded = _eligible_numeric_columns(
        df, respect_identifiers=respect_identifiers
    )

    variance_filter = min_variance if min_variance > 0 else 0.0
    usable: List[str] = []
    for col in eligible:
        std = pd.to_numeric(df[col], errors="coerce").std()
        if std is None or pd.isna(std) or float(std) <= variance_filter:
            excluded[col] = (
                "insufficient variance for correlation"
                if variance_filter > 0
                else "constant column (zero variance)"
            )
            continue
        usable.append(col)

    cap = max_columns or MAX_CORRELATION_COLUMNS
    warnings: List[str] = []
    if len(usable) > cap:
        warnings.append(
            f"{len(usable)} numeric columns exceed the {cap}-column "
            "correlation cap; analyzing the first "
            f"{cap} columns in dataset order."
        )
        usable = usable[:cap]

    result = CorrelationAnalysis(method=method, note=(
        "Categorical/text/identifier columns are intentionally excluded from "
        "numeric correlation; use categorical summaries or association tests."
    ))
    result.excluded_columns = excluded

    if len(usable) < 2:
        result.note = (
            "Insufficient numeric columns with variance for a correlation "
            f"matrix ({len(usable)} eligible)."
        )
        return result

    work = df[usable].apply(pd.to_numeric, errors="coerce")
    corr = work.corr(method=method)
    result.columns_used = usable

    matrix: Dict[str, Dict[str, Optional[float]]] = {}
    pairs: List[CorrelationPair] = []
    cols = list(corr.columns)
    values = corr.to_numpy()
    for i, outer in enumerate(cols):
        matrix[str(outer)] = {}
        for j, inner in enumerate(cols):
            v = values[i][j]
            matrix[str(outer)][str(inner)] = json_safe_number(v)

    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            v = values[i][j]
            if v is None or pd.isna(v) or not np.isfinite(v):
                continue
            value = float(v)
            pairs.append(CorrelationPair(
                column_a=str(cols[i]),
                column_b=str(cols[j]),
                correlation=round(value, 6),
                strength=strength_label(value),
                direction="positive" if value >= 0 else "negative",
            ))

    pairs.sort(key=lambda p: abs(p.correlation), reverse=True)
    result.top_pairs = pairs
    result.matrix = matrix
    return result


def raw_numeric_matrix(df: pd.DataFrame, method: str = "pearson"):
    """UNFILTERED numeric correlation for rendering consumers (heatmap).

    Rendering-parity mode: includes every numeric-dtype column (booleans,
    identifiers, constants included) exactly as chart renderers historically
    computed their matrices. Analytical consumers must prefer
    `correlation_matrix`, which applies statistical eligibility filters.
    Returns (column_labels, matrix_as_lists) or ([], []) when <2 columns.
    """
    method = method.lower().strip()
    if method not in VALID_METHODS:
        raise ValueError(
            f"Invalid correlation method '{method}'. Use {sorted(VALID_METHODS)}."
        )
    numeric_df = df.select_dtypes(include=[np.number])
    if numeric_df.shape[1] < 2:
        return [], []
    corr = numeric_df.corr(method=method)
    cols = [str(c) for c in corr.columns]
    grid = [[(None if pd.isna(v) else float(v)) for v in row] for row in corr.to_numpy()]
    return cols, grid


def pearson_significance_pairs(
    df: pd.DataFrame,
    columns: Optional[Sequence[str]] = None,
    min_n: int = 4,
) -> List[CorrelationPair]:
    """Pearson pairwise correlations with t-distribution p-values.

    Used by insight evidence where statistical significance per pair is
    required. Pairs with |r| >= 1 or insufficient overlap are skipped.
    """
    if columns is None:
        columns, _ = _eligible_numeric_columns(df, respect_identifiers=True)
    else:
        columns = [str(c) for c in columns if c in df.columns]

    pairs: List[CorrelationPair] = []
    for i, left in enumerate(columns):
        for right in columns[i + 1:]:
            pair = df[[left, right]].apply(pd.to_numeric, errors="coerce").dropna()
            n = int(len(pair))
            if n < min_n:
                continue
            r = series_correlation(pair[left], pair[right], method="pearson")
            if r is None or abs(r) >= 1:
                continue
            p = correlation_p_value(r, n)
            pairs.append(CorrelationPair(
                column_a=left,
                column_b=right,
                correlation=r,
                strength=correlation_strength_label(r),
                direction="positive" if r >= 0 else "negative",
                p_value=round(p, 6) if p is not None else None,
                n=n,
                significant=bool(p < 0.05) if p is not None else None,
            ))
    pairs.sort(key=lambda p: abs(p.correlation), reverse=True)
    return pairs


def anova_test(*args) -> Dict[str, Optional[float]]:
    """One-way ANOVA F-test.

    Accepts either:
      - anova_test(group_col, target_col)  — two Series
      - anova_test(list_of_group_arrays)   — pre-split numeric groups

    Returns dict with f_statistic and p_value. Callers that need a tuple can
    unpack via result.get("f_statistic"), result.get("p_value").
    """
    

    if len(args) == 1 and isinstance(args[0], (list, tuple)):
        clean = []
        for g in args[0]:
            s = pd.to_numeric(pd.Series(g), errors="coerce").dropna()
            if len(s) > 0:
                clean.append(s)
    elif len(args) == 2:
        group_col, target_col = args
        clean = [
            pd.to_numeric(target_col[group_col == val], errors="coerce").dropna()
            for val in pd.Series(group_col).unique()
        ]
        clean = [g for g in clean if len(g) > 0]
    else:
        raise TypeError(
            "anova_test expects (group_col, target_col) or a list of group arrays"
        )

    if len(clean) < 2:
        return {"f_statistic": None, "p_value": None}

    try:
        stat, p = stats.f_oneway(*clean)
        return {
            "f_statistic": float(stat) if np.isfinite(stat) else None,
            "p_value": float(p) if p is not None and np.isfinite(p) else None,
        }
    except Exception:
        return {"f_statistic": None, "p_value": None}


def chi2_association(x: pd.Series, y: pd.Series) -> Dict[str, Optional[float]]:
    """Chi-square test of independence between two categorical series.

    Returns {chi2, p_value, cramers_v, n}. Perfect single-row contingencies
    are reported as a perfect association (cramers_v = 1.0) instead of NaN.
    """

    # Drop true missing values BEFORE string conversion so NaN/None are not
    # turned into the literal category "nan" (version-dependent with astype).
    pair = pd.concat([x, y], axis=1).dropna()
    n = int(len(pair))
    if n == 0:
        return {"chi2": None, "p_value": None, "cramers_v": None, "n": 0}
    contingency = pd.crosstab(
        pair.iloc[:, 0].astype(str),
        pair.iloc[:, 1].astype(str),
    )
    return chi2_from_contingency(contingency)


def chi2_from_contingency(contingency: pd.DataFrame) -> Dict[str, Optional[float]]:
    """Chi-square/Cramér's V from a prebuilt contingency table."""

    n = int(contingency.sum().sum()) if contingency.size else 0
    if contingency.shape[0] == 1 and contingency.shape[1] == 1:
        return {"chi2": None, "p_value": 0.0, "cramers_v": 1.0, "n": n}
    if contingency.shape[0] < 2 or contingency.shape[1] < 2 or n == 0:
        return {"chi2": None, "p_value": None, "cramers_v": None, "n": n}
    try:
        chi2, p_val, _dof, _expected = stats.chi2_contingency(contingency)
        cramers_v = (
            float(np.sqrt(chi2 / (n * (min(contingency.shape) - 1))))
            if min(contingency.shape) > 1 and n else 0.0
        )
        finite = bool(np.isfinite(chi2))
        return {
            "chi2": round(float(chi2), 4) if finite else None,
            "p_value": round(float(p_val), 6) if p_val is not None and np.isfinite(p_val) else None,
            "cramers_v": round(cramers_v, 6),
            "n": n,
        }
    except Exception:
        return {"chi2": None, "p_value": None, "cramers_v": None, "n": n}


def welch_ttest(a: pd.Series, b: pd.Series) -> Tuple[Optional[float], Optional[float]]:
    """Welch's two-sample t-test (unequal variances). Returns (t, p)."""

    x = pd.to_numeric(a, errors="coerce").dropna()
    y = pd.to_numeric(b, errors="coerce").dropna()
    if len(x) < 2 or len(y) < 2:
        return None, None
    try:
        stat, p = stats.ttest_ind(x, y, equal_var=False)
        return (
            float(stat) if np.isfinite(stat) else None,
            float(p) if p is not None and np.isfinite(p) else None,
        )
    except Exception:
        return None, None


def mann_whitney_u(a: pd.Series, b: pd.Series) -> Tuple[Optional[float], Optional[float]]:
    """Mann-Whitney U rank test. Returns (u, p)."""

    x = pd.to_numeric(a, errors="coerce").dropna()
    y = pd.to_numeric(b, errors="coerce").dropna()
    if len(x) < 1 or len(y) < 1:
        return None, None
    try:
        stat, p = stats.mannwhitneyu(x, y, alternative="two-sided")
        return (
            float(stat) if np.isfinite(stat) else None,
            float(p) if p is not None and np.isfinite(p) else None,
        )
    except Exception:
        return None, None


def kruskal_wallis(*groups):
    """Kruskal-Wallis H-test across 2+ numeric groups. Returns (H, p)."""
    cleaned = []
    for g in groups:
        arr = pd.to_numeric(pd.Series(g), errors="coerce").dropna()
        if len(arr) >= 1:
            cleaned.append(arr)
    if len(cleaned) < 2:
        return None, None
    try:
        stat, p = stats.kruskal(*cleaned)
        return (
            float(stat) if np.isfinite(stat) else None,
            float(p) if p is not None and np.isfinite(p) else None,
        )
    except Exception:
        return None, None