"""The DataWise Statistical Engine.

READ-ONLY by contract: this engine analyzes datasets and produces
structured, JSON-serializable evidence. It never deletes, replaces, caps,
winsorizes or otherwise modifies any value. All modification authority —
including every outlier decision — belongs exclusively to the Cleaning
Engine (backend.cleaning).

Pipeline position:

    Dataset ──┬── Cleaning Engine   -> Cleaned Dataset  (modifications)
              └── Statistical Engine -> Statistical Results (evidence only)

                        |
                        v
        Insights / Visualization / Report / ML analysis

Design principles:
  - Dataset-agnostic: numeric, categorical, boolean, datetime and text
    columns each receive only the analyses that are meaningful for them.
  - Graceful degradation: empty frames, single rows, constant columns,
    all-missing columns and mixed types produce structured warnings, never
    crashes.
  - One authoritative implementation: agents and tools delegate here instead
    of reimplementing pandas/scipy statistics.
"""
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from backend.statistics.bivariate import (
    correlation_matrix,
    pearson_significance_pairs,
    series_correlation,
)
from backend.statistics.contracts import (
    DEFAULT_PERCENTILES,
    DEFAULT_TOP_VALUES,
    MAX_ROWS_FOR_SHAPIRO,
    ColumnSummary,
    CorrelationAnalysis,
    DatasetOverview,
    DistributionCheck,
    GroupStatistics,
    StatisticalResults,
    TargetAssociations,
)
from backend.statistics.groups import group_statistics, target_associations
from backend.statistics.helpers import (
    classify_column_kind,
    is_identifier_like,
    json_safe_number,
)
from backend.statistics.outliers import (
    column_outlier_evidence,
    five_number_summary as _five_number_summary,
    outlier_evidence,
)
from backend.utils.logger import setup_logger

from backend.statistics.univariate import (
    boolean_summary,
    categorical_summary,
    datetime_summary,
    distribution_check as _distribution_check,
    numeric_summary,
    text_summary,
)

ENGINE_VERSION = "1.1.0"


class StatisticalEngine:
    """Read-only statistical analysis of arbitrary DataFrames."""

    def __init__(
        self,
        correlation_method: str = "spearman",
        outlier_method: str = "iqr",
        outlier_threshold: float = 1.5,
        top_values: int = DEFAULT_TOP_VALUES,
        percentiles: Sequence[float] = DEFAULT_PERCENTILES,
        include_distributions: bool = True,
        include_correlations: bool = True,
        include_outlier_evidence: bool = True,
    ):
        self.logger = setup_logger("StatisticalEngine")
        if correlation_method not in {"pearson", "spearman", "kendall"}:
            raise ValueError(f"Invalid correlation method '{correlation_method}'.")
        if outlier_method not in {"iqr", "zscore"}:
            raise ValueError(f"Invalid outlier method '{outlier_method}'.")
        self.correlation_method = correlation_method
        self.outlier_method = outlier_method
        self.outlier_threshold = float(outlier_threshold)
        self.top_values = int(top_values)
        self.percentiles = tuple(percentiles or DEFAULT_PERCENTILES)
        self.include_distributions = include_distributions
        self.include_correlations = include_correlations
        self.include_outlier_evidence = include_outlier_evidence

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        df: pd.DataFrame,
        target: Optional[str] = None,
        group_by: Optional[Sequence[str]] = None,
    ) -> StatisticalResults:
        """Full read-only analysis. The input DataFrame is NEVER modified."""
        if not isinstance(df, pd.DataFrame):
            raise TypeError("StatisticalEngine.analyze expects a pandas DataFrame.")

        results = StatisticalResults()
        results.metadata = {
            "engine": "StatisticalEngine",
            "version": ENGINE_VERSION,
            "correlation_method": self.correlation_method,
            "outlier_method": self.outlier_method,
            "outlier_threshold": self.outlier_threshold,
            "read_only": True,
        }

        if df.empty or len(df.columns) == 0:
            results.dataset = self.overview(df)
            results.warnings.append("Dataset is empty; nothing to analyze.")
            return results

        results.dataset = self.overview(df)
        self.logger.info(
            "Analysis started | rows=%s columns=%s numeric=%s categorical=%s "
            "boolean=%s datetime=%s text=%s identifiers=%s",
            results.dataset.rows,
            results.dataset.column_count,
            len(results.dataset.numeric_columns),
            len(results.dataset.categorical_columns),
            len(results.dataset.boolean_columns),
            len(results.dataset.datetime_columns),
            len(results.dataset.text_columns),
            len(results.dataset.identifier_columns),
        )

        # 1. Per-column statistics (only meaningful analyses per kind).
        for col in df.columns:
            kind = results.dataset and self._kind_of(df, col)
            summary = self.describe_column(df[col], str(col), kind=kind)
            results.column_statistics[str(col)] = summary
            for warning in getattr(summary, "warnings", []) or []:
                results.warnings.append(f"{col}: {warning}")

        # 2. Correlation analysis (numeric-only, identifiers excluded).
        if self.include_correlations:
            try:
                results.correlations = self.correlations(df)
            except Exception as exc:
                results.warnings.append(f"Correlation analysis failed: {exc}")

        # 3. Distribution checks for eligible numeric columns.
        if self.include_distributions:
            for col in results.dataset.numeric_columns:
                try:
                    check = self.distribution_check(df[col], col)
                    if check is not None:
                        results.distributions[col] = check
                except Exception as exc:
                    results.warnings.append(
                        f"Distribution check failed for '{col}': {exc}"
                    )

        # 4. Statistical outlier EVIDENCE (no treatment decisions here).
        if self.include_outlier_evidence:
            try:
                results.outlier_evidence = self.outlier_evidence(df)
            except Exception as exc:
                results.warnings.append(f"Outlier evidence failed: {exc}")

        # 5. Optional conditional analyses.
        if target and target in df.columns:
            try:
                results.target_associations = self.target_associations(df, target)
            except Exception as exc:
                results.warnings.append(f"Target associations failed: {exc}")
        if group_by:
            value_col = target if (target and target in df.columns) else \
                next(iter(results.dataset.numeric_columns), None)
            if value_col:
                try:
                    results.group_statistics = self.group_statistics(
                        df, value_col, group_by
                    )
                except Exception as exc:
                    results.warnings.append(f"Group statistics failed: {exc}")

        self.logger.info(
            "Analysis completed | column_statistics=%s correlations=%s "
            "distributions=%s outlier_columns=%s target_associations=%s "
            "group_entries=%s warnings=%s",
            len(results.column_statistics),
            len(results.correlations.top_pairs) if results.correlations else 0,
            len(results.distributions),
            len(results.outlier_evidence.columns) if results.outlier_evidence else 0,
            (len(results.target_associations.numeric) + len(results.target_associations.categorical))
            if results.target_associations else 0,
            len(results.group_statistics.entries),
            len(results.warnings),
        )
        return results

    def overview(self, df: pd.DataFrame) -> DatasetOverview:
        """Dataset-level structural overview (read-only)."""
        overview = DatasetOverview(
            rows=int(len(df)),
            column_count=int(len(df.columns)),
            column_names=[str(c) for c in df.columns],
            dtypes={str(c): str(t) for c, t in df.dtypes.items()},
            memory_usage_mb=round(
                float(df.memory_usage(deep=True).sum()) / (1024 ** 2), 2
            ) if len(df.columns) else 0.0,
            total_missing_cells=int(df.isna().sum().sum()),
            duplicate_rows=int(df.duplicated().sum()),
            duplicate_ratio=round(
                float(df.duplicated().sum() / len(df)), 6
            ) if len(df) else 0.0,
        )
        for col in df.columns:
            series = df[col]
            if int(series.isna().sum()) == 0 and int(series.nunique(dropna=True)) <= 1 \
                    and len(series) > 0:
                overview.constant_columns.append(str(col))
            kind = self._kind_of(df, col)
            if kind == "numeric":
                overview.numeric_columns.append(str(col))
            elif kind == "categorical":
                overview.categorical_columns.append(str(col))
            elif kind == "boolean":
                overview.boolean_columns.append(str(col))
            elif kind == "datetime":
                overview.datetime_columns.append(str(col))
            elif kind == "text":
                overview.text_columns.append(str(col))
            else:
                overview.identifier_columns.append(str(col))
        return overview

    def describe_column(
        self,
        series: pd.Series,
        name: Optional[str] = None,
        kind: Optional[str] = None,
    ) -> ColumnSummary:
        """The one meaningful statistical summary for a single column."""
        label = str(name) if name is not None else str(series.name)
        kind = kind or self._kind_of_series(series, label)

        if kind == "identifier":
            # Identifiers get categorical-style counts but are explicitly
            # excluded from distribution/correlation/outlier statistics.
            return categorical_summary(series, top_n=self.top_values)
        if kind == "numeric":
            return numeric_summary(series, percentiles=self.percentiles)
        if kind == "boolean":
            return boolean_summary(series)
        if kind == "datetime":
            return datetime_summary(series)
        if kind == "text":
            return text_summary(series)
        return categorical_summary(series, top_n=self.top_values)

    def correlations(
        self,
        df: pd.DataFrame,
        method: Optional[str] = None,
        min_variance: float = 0.0,
    ) -> CorrelationAnalysis:
        """Numeric correlation matrix with ranked pairs (identifiers excluded)."""
        return correlation_matrix(
            df,
            method=method or self.correlation_method,
            min_variance=min_variance,
        )

    def pairwise_significance(
        self,
        df: pd.DataFrame,
        columns: Optional[Sequence[str]] = None,
    ) -> list:
        """Pearson pairs with p-values (used for insight evidence)."""
        return pearson_significance_pairs(df, columns=columns)

    def distribution_check(self, series: pd.Series, name: Optional[str] = None) -> Optional[DistributionCheck]:
        """Skewness + Shapiro-Wilk normality evidence where appropriate."""
        return _distribution_check(series, name)

    def outlier_evidence(
        self,
        df: pd.DataFrame,
        method: Optional[str] = None,
        threshold: Optional[float] = None,
        columns: Optional[Sequence[str]] = None,
    ):
        """Statistical outlier evidence (read-only; decisions live elsewhere)."""
        return outlier_evidence(
            df,
            method=method or self.outlier_method,
            threshold=self.outlier_threshold if threshold is None else threshold,
            columns=list(columns) if columns else None,
        )

    def describe_single_outlier_column(
        self,
        series: pd.Series,
        name: str,
        method: Optional[str] = None,
        threshold: Optional[float] = None,
    ):
        """Evidence for one column, including explicit skip reasons."""
        return column_outlier_evidence(
            series,
            name,
            method=method or self.outlier_method,
            threshold=self.outlier_threshold if threshold is None else threshold,
        )

    def group_statistics(
        self,
        df: pd.DataFrame,
        value_column: str,
        group_columns: Optional[Sequence[str]] = None,
    ) -> GroupStatistics:
        """Conditional summaries of a numeric value column per group."""
        return group_statistics(df, value_column, group_columns)

    def target_associations(
        self,
        df: pd.DataFrame,
        target: str,
        exclude_columns: Optional[Sequence[str]] = None,
    ) -> TargetAssociations:
        """Ranked feature→target associations using the appropriate tests."""
        return target_associations(df, target, exclude_columns=exclude_columns)

    # ------------------------------------------------------------------
    # Small primitives reused across the backend (agents/tools delegate)
    # ------------------------------------------------------------------

    @staticmethod
    def series_correlation(a: pd.Series, b: pd.Series, method: str = "spearman"):
        return series_correlation(a, b, method=method)

    @staticmethod
    def five_number_summary(values) -> dict:
        return _five_number_summary(values)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _kind_of(self, df: pd.DataFrame, col) -> str:
        return self._kind_of_series(df[col], str(col))

    @staticmethod
    def _kind_of_series(series: pd.Series, label: str) -> str:
        return classify_column_kind(series, label)
