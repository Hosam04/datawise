"""Univariate summaries: per-column statistical descriptions (read-only).

Every function takes a pandas Series and returns a structured contract model.
No function ever mutates the input series: computations operate on coerced
copies where conversion is required.
"""
from typing import List, Optional, Sequence

import numpy as np
import pandas as pd

from backend.statistics.contracts import (
    BooleanSummary,
    CategoricalSummary,
    DatetimeSummary,
    DistributionCheck,
    NumericSummary,
    TextSummary,
    TopValue,
    MAX_ROWS_FOR_SHAPIRO,
)
from backend.statistics.helpers import entropy, json_safe_number


def distribution_check(
    series: pd.Series, name: Optional[str] = None
) -> Optional[DistributionCheck]:
    """Skewness + Shapiro-Wilk normality evidence for a numeric series.

    Shapiro-Wilk is skipped above MAX_ROWS_FOR_SHAPIRO rows (meaningless and
    expensive there); constant/short series return an explicit note instead.
    """
    label = str(name) if name is not None else str(series.name)
    values = pd.to_numeric(series, errors="coerce").dropna()

    check = DistributionCheck(column=label, n=int(len(values)))
    if len(values) < 3 or values.nunique() <= 1:
        check.note = "Not enough variance/rows for distribution analysis"
        check.shape = "unknown"
        return check

    skew = values.skew()
    check.skewness = json_safe_number(skew)
    if pd.isna(skew):
        check.shape = "unknown"
    elif skew > 1.0:
        check.shape = "right_skewed"
    elif skew < -1.0:
        check.shape = "left_skewed"
    else:
        check.shape = "normal_like"

    if len(values) <= MAX_ROWS_FOR_SHAPIRO:
        try:
            from scipy import stats as scipy_stats

            statistic, p_value = scipy_stats.shapiro(values)
            check.shapiro_statistic = json_safe_number(statistic)
            check.shapiro_p_value = json_safe_number(p_value)
        except Exception:
            check.note = check.note or "Shapiro-Wilk could not be computed"
    else:
        check.note = (
            f"Shapiro-Wilk skipped for n={len(values)} > {MAX_ROWS_FOR_SHAPIRO}"
        )
    return check


def numeric_summary(
    series: pd.Series,
    percentiles: Sequence[float] = (0.05, 0.25, 0.50, 0.75, 0.95),
) -> NumericSummary:
    """Descriptive statistics for one numeric column.

    Graceful degradation rules:
      - empty / all-missing  -> counts only + warning
      - single observation   -> no dispersion statistics (std/var/sem/cv)
      - constant column      -> dispersion is zero; flagged via `constant`
      - n <= 2               -> skewness None; n <= 3 -> kurtosis None
    """
    values = pd.to_numeric(series, errors="coerce")
    non_null = values.dropna()
    total = int(len(values))
    null_count = int(values.isna().sum())

    summary = NumericSummary(
        count=int(non_null.count()),
        null_count=null_count,
        null_pct=round(float(null_count / total * 100), 2) if total else 0.0,
        unique_count=int(non_null.nunique()),
        zeros_count=int((non_null == 0).sum()),
        negative_count=int((non_null < 0).sum()),
    )

    if len(non_null) == 0:
        summary.warnings.append("All values are null")
        return summary

    constant = bool(non_null.nunique() <= 1)
    summary.constant = constant
    if constant:
        summary.warnings.append("Constant column: dispersion statistics are zero by definition")

    summary.sum = json_safe_number(non_null.sum())
    summary.mean = json_safe_number(non_null.mean())
    summary.median = json_safe_number(non_null.median())
    summary.min = json_safe_number(non_null.min())
    summary.max = json_safe_number(non_null.max())
    if summary.min is not None and summary.max is not None:
        summary.range = round(summary.max - summary.min, 6)

    q1 = non_null.quantile(0.25)
    q3 = non_null.quantile(0.75)
    summary.q1 = json_safe_number(q1)
    summary.q3 = json_safe_number(q3)
    summary.iqr = json_safe_number(q3 - q1)

    try:
        for p in percentiles:
            key = f"p{int(round(p * 100))}"
            summary.percentiles[key] = json_safe_number(non_null.quantile(p))
    except Exception:
        summary.percentiles = {}

    std = non_null.std()
    variance = non_null.var()
    summary.std = json_safe_number(std)
    summary.variance = json_safe_number(variance)

    if len(non_null) > 2:
        summary.skewness = json_safe_number(non_null.skew())
    if len(non_null) > 3:
        summary.kurtosis = json_safe_number(non_null.kurtosis())

    mean_val = non_null.mean()
    if len(non_null) > 1 and mean_val is not None and not pd.isna(mean_val):
        summary.cv = (
            json_safe_number(non_null.std() / abs(mean_val))
            if mean_val != 0 and np.isfinite(mean_val)
            else None
        )
        try:
            summary.sem = json_safe_number(non_null.sem())
        except Exception:
            summary.sem = None

    if summary.iqr is not None and not np.isfinite(summary.iqr):
        summary.iqr = None
    return summary


def categorical_summary(
    series: pd.Series,
    top_n: int = 10,
    missing_label: Optional[str] = None,
) -> CategoricalSummary:
    """Frequency summary for one categorical column.

    When `missing_label` is provided (e.g. "Missing"), missing cells are
    reported as an explicit value inside top_values, mirroring the historical
    statistics-tool contract. Otherwise missingness is reported only through
    null_count/null_pct.
    """
    total = int(len(series))
    null_count = int(series.isna().sum())

    values = series.astype("string")
    if missing_label is not None:
        counts = values.value_counts(dropna=False)
    else:
        counts = values.value_counts(dropna=True)

    top: List[TopValue] = []
    denominator = total if total else 1
    shown = 0
    for value, count in counts.items():
        if shown >= top_n:
            break
        if missing_label is None and pd.isna(value):
            continue
        label = str(missing_label) if (missing_label is not None and pd.isna(value)) else str(value)
        top.append(TopValue(
            value=label,
            count=int(count),
            percentage=round(float(count / denominator * 100), 2),
        ))
        shown += 1

    observed = values.dropna()
    unique_count = int(observed.nunique()) if missing_label is None \
        else int(values.nunique(dropna=False))

    summary = CategoricalSummary(
        count=int(observed.count()) if missing_label is None else int(total - null_count + null_count),
        null_count=null_count,
        null_pct=round(float(null_count / total * 100), 2) if total else 0.0,
        unique_count=unique_count,
        top_values=top,
    )
    # Legacy parity: count = number of non-null observations when missingness
    # is reported separately.
    if missing_label is None:
        summary.count = int(observed.count())

    if total > 0 and observed.empty:
        summary.warnings.append("All values are null")

    try:
        summary.entropy = round(entropy(series.dropna().value_counts()), 4) \
            if len(series.dropna()) else None
    except Exception:
        summary.entropy = None

    summary.constant = bool(unique_count <= 1)
    if summary.constant and total > 0:
        summary.warnings.append("Constant column")
    return summary


def boolean_summary(series: pd.Series) -> BooleanSummary:
    """True/false distribution for one boolean column."""
    total = int(len(series))
    null_count = int(series.isna().sum())
    non_null = series.dropna()
    true_count = int((non_null == True).sum())  # noqa: E712 - boolean semantics
    false_count = int(len(non_null)) - true_count
    return BooleanSummary(
        count=int(len(non_null)),
        null_count=null_count,
        null_pct=round(float(null_count / total * 100), 2) if total else 0.0,
        true_count=true_count,
        false_count=false_count,
        true_pct=round(float(true_count / len(non_null) * 100), 2) if len(non_null) else 0.0,
        constant=bool(non_null.nunique() <= 1),
    )


def datetime_summary(series: pd.Series) -> DatetimeSummary:
    """Range/granularity evidence for one datetime column."""
    total = int(len(series))
    null_count = int(series.isna().sum())
    valid = pd.to_datetime(series, errors="coerce").dropna()

    summary = DatetimeSummary(
        count=int(valid.count()),
        null_count=null_count,
        null_pct=round(float(null_count / total * 100), 2) if total else 0.0,
    )
    if valid.empty:
        summary.warnings.append("No parseable datetime values")
        return summary

    summary.min = str(valid.min())
    summary.max = str(valid.max())
    try:
        summary.span_days = int((valid.max() - valid.min()).days) + 1
    except Exception:
        summary.span_days = None

    monthly = valid.dt.month.value_counts().sort_index()
    summary.monthly_distribution = {int(k): int(v) for k, v in monthly.items()}
    if not monthly.empty:
        summary.peak_month = int(monthly.idxmax())
    summary.constant = bool(valid.nunique() <= 1)
    return summary


def text_summary(series: pd.Series) -> TextSummary:
    """Lightweight structural summary for free-text columns."""
    total = int(len(series))
    null_count = int(series.isna().sum())
    strings = series.dropna().astype(str)

    lengths = strings.str.len() if not strings.empty else pd.Series(dtype="int64")
    stripped = strings.str.strip()
    return TextSummary(
        count=int(strings.count()),
        null_count=null_count,
        null_pct=round(float(null_count / total * 100), 2) if total else 0.0,
        unique_count=int(strings.nunique()),
        avg_length=round(float(lengths.mean()), 2) if len(lengths) else None,
        min_length=int(lengths.min()) if len(lengths) else None,
        max_length=int(lengths.max()) if len(lengths) else None,
        empty_string_count=int((stripped == "").sum()),
        constant=bool(strings.nunique() <= 1 and len(strings) > 0),
    )
