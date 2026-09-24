"""Typed contracts for the DataWise Statistical Engine.

Follows the project's existing pydantic-schema convention (see
backend/cleaning/contracts.py and backend/ml/schemas.py). These models are
pure data: nothing in this module touches a DataFrame.

HARD ARCHITECTURAL RULE: the Statistical Engine is READ-ONLY. It produces
structured evidence about a dataset. It never deletes, replaces, caps or
otherwise modifies values — that authority belongs exclusively to the
Cleaning Engine.

Principle: statistical analysis provides evidence; cleaning makes decisions
and modifies the dataset. A statistically unusual value is not automatically
an erroneous value.
"""
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

ColumnKind = Literal[
    "numeric",
    "categorical",
    "boolean",
    "datetime",
    "text",
    "identifier",
]

Severity = Literal["low", "medium", "high"]

# Default percentiles reported for numeric columns (matches the historical
# statistics tool contract: p5/p25/p50/p75/p95).
DEFAULT_PERCENTILES = (0.05, 0.25, 0.50, 0.75, 0.95)

# Distribution normality checks are skipped above this row count (Shapiro-Wilk
# is O(n^2)-ish in practice and meaningless at large n).
MAX_ROWS_FOR_SHAPIRO = 5000

# Correlation matrices larger than this many columns are capped (O(n^2) pairs).
MAX_CORRELATION_COLUMNS = 40

# Top categorical values retained per column.
DEFAULT_TOP_VALUES = 10

# Maximum outlier row indices retained per column in evidence (bounded logs).
MAX_OUTLIER_ROW_SAMPLES = 100


class DatasetOverview(BaseModel):
    """Read-only overview of the analyzed dataset."""

    rows: int = 0
    column_count: int = 0
    column_names: List[str] = Field(default_factory=list)
    dtypes: Dict[str, str] = Field(default_factory=dict)
    memory_usage_mb: float = 0.0
    total_missing_cells: int = 0
    duplicate_rows: int = 0
    duplicate_ratio: float = 0.0
    constant_columns: List[str] = Field(default_factory=list)
    numeric_columns: List[str] = Field(default_factory=list)
    categorical_columns: List[str] = Field(default_factory=list)
    boolean_columns: List[str] = Field(default_factory=list)
    datetime_columns: List[str] = Field(default_factory=list)
    text_columns: List[str] = Field(default_factory=list)
    identifier_columns: List[str] = Field(default_factory=list)


class NumericSummary(BaseModel):
    """Full descriptive summary of one numeric column."""

    kind: Literal["numeric"] = "numeric"
    count: int = 0
    null_count: int = 0
    null_pct: float = 0.0
    unique_count: int = 0
    sum: Optional[float] = None
    mean: Optional[float] = None
    median: Optional[float] = None
    std: Optional[float] = None
    variance: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    range: Optional[float] = None
    q1: Optional[float] = None
    q3: Optional[float] = None
    iqr: Optional[float] = None
    percentiles: Dict[str, Optional[float]] = Field(default_factory=dict)
    skewness: Optional[float] = None
    kurtosis: Optional[float] = None
    cv: Optional[float] = None
    sem: Optional[float] = None
    zeros_count: int = 0
    negative_count: int = 0
    constant: bool = False
    warnings: List[str] = Field(default_factory=list)


class TopValue(BaseModel):
    value: str
    count: int
    percentage: float


class CategoricalSummary(BaseModel):
    """Frequency summary of one categorical column."""

    kind: Literal["categorical"] = "categorical"
    count: int = 0
    null_count: int = 0
    null_pct: float = 0.0
    unique_count: int = 0
    top_values: List[TopValue] = Field(default_factory=list)
    entropy: Optional[float] = None
    constant: bool = False
    warnings: List[str] = Field(default_factory=list)
    mode: Optional[str] = None


class BooleanSummary(BaseModel):
    kind: Literal["boolean"] = "boolean"
    count: int = 0
    null_count: int = 0
    null_pct: float = 0.0
    true_count: int = 0
    false_count: int = 0
    true_pct: float = 0.0
    constant: bool = False
    warnings: List[str] = Field(default_factory=list)


class DatetimeSummary(BaseModel):
    kind: Literal["datetime"] = "datetime"
    count: int = 0
    null_count: int = 0
    null_pct: float = 0.0
    min: Optional[str] = None
    max: Optional[str] = None
    span_days: Optional[int] = None
    monthly_distribution: Dict[int, int] = Field(default_factory=dict)
    peak_month: Optional[int] = None
    constant: bool = False
    warnings: List[str] = Field(default_factory=list)


class TextSummary(BaseModel):
    """Lightweight structural summary for free-text columns.

    Deliberately minimal: word frequencies / embeddings are NOT statistics of
    general interest and high-cardinality text is excluded from categorical
    frequency tables to avoid meaningless output.
    """

    kind: Literal["text"] = "text"
    count: int = 0
    null_count: int = 0
    null_pct: float = 0.0
    unique_count: int = 0
    avg_length: Optional[float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    empty_string_count: int = 0
    constant: bool = False
    warnings: List[str] = Field(default_factory=list)


ColumnSummary = Union[
    NumericSummary,
    CategoricalSummary,
    BooleanSummary,
    DatetimeSummary,
    TextSummary,
]


class ColumnOutlierEvidence(BaseModel):
    """Statistical outlier evidence for ONE column.

    This is EVIDENCE ONLY. It does not imply that any value is wrong and it
    must never be used to modify the dataset directly.
    """

    column: str
    analyzed: bool = True
    method: str = "iqr"
    threshold: float = 1.5
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    mean: Optional[float] = None
    std: Optional[float] = None
    mad_extreme_share: Optional[float] = None
    count: int = 0
    percentage: float = 0.0
    severity: Severity = "low"
    note: Optional[str] = None
    sample_row_indices: List[int] = Field(default_factory=list)
    min_outlier_value: Optional[float] = None
    max_outlier_value: Optional[float] = None
    action: Literal["evidence_only"] = "evidence_only"


class OutlierEvidence(BaseModel):
    """Dataset-level statistical outlier evidence.

    action is always evidence-only: deciding whether outliers represent
    errors, suspicious values or legitimate observations is the Cleaning
    Engine's responsibility.
    """

    method: str = "iqr"
    threshold: float = 1.5
    total_rows: int = 0
    columns_analyzed: List[str] = Field(default_factory=list)
    columns: List[ColumnOutlierEvidence] = Field(default_factory=list)
    action: Literal["evidence_only"] = "evidence_only"
    note: str = (
        "Statistical outliers are unusual values, not proven errors. "
        "Treatment decisions belong to the Cleaning Engine."
    )


class CorrelationPair(BaseModel):
    column_a: str
    column_b: str
    correlation: float
    strength: str = "weak"
    direction: Literal["positive", "negative"] = "positive"
    p_value: Optional[float] = None
    n: Optional[int] = None
    significant: Optional[bool] = None


class CorrelationAnalysis(BaseModel):
    method: str = "pearson"
    columns_used: List[str] = Field(default_factory=list)
    excluded_columns: Dict[str, str] = Field(default_factory=dict)
    matrix: Dict[str, Dict[str, Optional[float]]] = Field(default_factory=dict)
    top_pairs: List[CorrelationPair] = Field(default_factory=list)
    note: str = (
        "Categorical/text columns are intentionally excluded from numeric "
        "correlation; use categorical summaries or association tests instead."
    )


class DistributionCheck(BaseModel):
    """Distribution-shape evidence for one numeric column."""

    column: str
    n: int = 0
    skewness: Optional[float] = None
    shapiro_statistic: Optional[float] = None
    shapiro_p_value: Optional[float] = None
    shape: str = "unknown"
    note: Optional[str] = None


class GroupValueStats(BaseModel):
    group: str
    count: int
    mean: Optional[float] = None
    median: Optional[float] = None
    std: Optional[float] = None


class GroupStatisticsEntry(BaseModel):
    group_column: str
    value_column: str
    groups: List[GroupValueStats] = Field(default_factory=list)
    note: Optional[str] = None


class GroupStatistics(BaseModel):
    entries: List[GroupStatisticsEntry] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class AssociationTest(BaseModel):
    """Association between one feature and a target variable.

    kind numeric_spearman -> score is |spearman rho|
    kind anova_eta2       -> score is eta-squared-like ratio in [0, 1]
    kind chi2_cramers_v   -> score is Cramer's V in [0, 1]
    """

    feature: str
    target: str
    kind: Literal[
        "numeric_spearman",
        "anova_eta2",
        "chi2_cramers_v",
        "mann_whitney",
        "kruskal_wallis",
    ]
    score: float
    statistic: Optional[float] = None
    p_value: Optional[float] = None
    n: int = 0
    method: str = ""


class TargetAssociations(BaseModel):
    target: str
    target_kind: Literal["numeric", "categorical", "boolean", "datetime", "text", "identifier"]
    numeric: List[AssociationTest] = Field(default_factory=list)
    categorical: List[AssociationTest] = Field(default_factory=list)


class StatisticalResults(BaseModel):
    """Full structured result of one StatisticalEngine run.

    Everything in this model is JSON-serializable via model_dump(mode="json")
    and safe to store in AgentState, serve from APIs, and consume by the
    Insights / Visualization / Report components.
    """

    dataset: DatasetOverview = Field(default_factory=DatasetOverview)
    column_statistics: Dict[str, ColumnSummary] = Field(default_factory=dict)
    correlations: Optional[CorrelationAnalysis] = None
    distributions: Dict[str, DistributionCheck] = Field(default_factory=dict)
    outlier_evidence: Optional[OutlierEvidence] = None
    group_statistics: GroupStatistics = Field(default_factory=GroupStatistics)
    target_associations: Optional[TargetAssociations] = None
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
