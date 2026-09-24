"""Typed contracts for the DataWise Cleaning Engine.

These models follow the project's existing pydantic-schema convention
(see backend/ml/schemas.py). They are pure data: nothing in this module
touches a DataFrame.
"""
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

SemanticType = Literal[
    "numeric",
    "categorical",
    "text",
    "identifier",
    "datetime",
    "boolean",
]

ProblemType = Literal[
    "missing_values",
    "duplicates",
    "outliers",
    "invalid_values",
    "type_anomaly",
    "categorical_consistency",
    "formatting",
    "constraint_violation",
    "derived_column",
    "missingness_pattern",
    "semantic_anomaly",
    "structural",
]

Verdict = Literal["apply", "skip", "flag", "block"]
Severity = Literal["low", "medium", "high"]

# ---------------------------------------------------------------------------
# Conservative defaults. Kept here (not in core/config.py) because they are
# cleaning-policy constants, not deployment configuration.
# ---------------------------------------------------------------------------

# Missing-value imputation is only approved below this missing ratio.
MAX_IMPUTE_MISSING_RATIO = 0.5
# A numeric column needs at least this many observed values before a median
# imputation can be considered statistically meaningful.
MIN_NON_NULL_FOR_IMPUTE = 10
# Categorical mode-fill requires either a clearly dominant category...
MODE_DOMINANCE_RATIO = 0.5
# ...or a low missing ratio where the few gaps are unlikely to distort data.
MAX_MODE_FILL_MISSING_RATIO = 0.2
# Exact duplicate removal is approved while duplicates stay a minority of the
# dataset. Above this ratio the rows may be legitimate repeated observations,
# so the issue is flagged instead of resolved.
MAX_DUPLICATE_RATIO_FOR_REMOVAL = 0.5

# Explicit label used to preserve missingness as information for categorical
# columns whose missing ratio is too high for any invented value.
UNKNOWN_CATEGORY_LABEL = "Unknown"

# ---------------------------------------------------------------------------
# Extension detectors (Phase 9): conservative evidence thresholds.
# ---------------------------------------------------------------------------

# A string column is considered "dominated" by a value class (numeric/date/
# boolean-like) when at least this share of its values belongs to one class.
TYPE_DOMINANCE_RATIO = 0.85
# Minimum minority size worth reporting as a type anomaly.
TYPE_ANOMALY_MIN_CONFLICTS = 1

# Semantic plausibility ranges applied ONLY when a column name explicitly
# carries the corresponding keyword (backend.core.constants). Rarity alone is
# never invalidity: these rules encode objective domain bounds.
AGE_MAX_PLAUSIBLE = 130

# Derived-column relationships are only repairable when the deterministic
# formula holds on at least this share of valid rows...
DERIVED_EXACT_COVERAGE = 0.98
# ...and merely *suspicious* (flag-only) above this share. Below it, no
# relationship is reported at all.
DERIVED_SUSPECT_COVERAGE = 0.90
# Minimum rows supporting any derived-relationship claim.
DERIVED_MIN_ROWS = 8
# Constant offsets searched when testing target == source_a + source_b + k.
DERIVED_OFFSET_SEARCH = (-2, -1, 0, 1, 2)

# Missingness-pattern analysis: minimum group support and the absolute rate
# gap (vs the column's overall missing rate) that indicates concentration.
MISSINGNESS_GROUP_SUPPORT = 10
MISSINGNESS_RATE_GAP = 0.30
# Joint-missing lift over the independence expectation that indicates a
# systematic co-missingness block.
CO_MISSING_LIFT = 3.0
CO_MISSING_MIN_SUPPORT = 10

# Semantic-anomaly analysis needs enough rows for correlations to mean
# anything, treats |rho| below this as "no relationship", and requires the
# components to be mutually related so the aggregate COULD have been derived.
SEMANTIC_MIN_ROWS = 15
SEMANTIC_NO_RELATIONSHIP_RHO = 0.05
COMPONENT_MUTUAL_CORR_FLOOR = 0.20

# ---------------------------------------------------------------------------
# Structural / input integrity (read-only pre-pipeline layer)
# ---------------------------------------------------------------------------

# A semantic-identifier column whose non-null values deviate from the
# column's dominant format on more than this share is treated as parse
# corruption (text merged into IDs, embedded delimiters, stray quotes).
ID_CORRUPTION_SHARE = 0.02
# Minimum absolute corrupted cells before a BLOCK is issued.
ID_CORRUPTION_MIN_CELLS = 3
# Share of values sharing EXACTLY the maximal string length that suggests
# fixed-width truncation.
TRUNCATION_SAME_MAX_LENGTH_SHARE = 0.15
TRUNCATION_MIN_VALUES = 20
# Delimiter characters whose appearance inside numeric/categorical semantic
# columns indicates column-shift style parsing damage.
STRUCTURAL_DELIMITERS = [",", ";", "|", "\t"]

# Separator-fold tier: categorical variants equal after removing [_ - ] and
# case may be merged ONLY when the canonical spelling holds at least this
# share of the fold group (e.g. dominant "A4" vs stray "A_4").
SEPARATOR_FOLD_DOMINANCE = 0.80

# Lossless numeric-string conversion candidacy: every non-null value must
# parse cleanly; anything less is FLAG-only (casting would destroy data).
NUMERIC_STRING_PARSE_SHARE = 1.0

# Information-loss audit: after an approved imputation, if the filled value
# pushes one value's share above this level, record a warning. Calibrated to
# catch real-world patterns such as ~25% of a column becoming one imputed
# constant (e.g. many missing ages collapsing to the median).
INFO_LOSS_MODE_SHARE = 0.20

# Overall dataset assessment thresholds (share of findings by severity).
ASSESSMENT_CRITICAL_SHARE = 0.0  # any critical finding caps assessment

# ---------------------------------------------------------------------------
# Pre-parse FILE integrity (raw CSV/text, before DataFrame creation)
# ---------------------------------------------------------------------------

# Maximum records scanned during pre-parse integrity checking (scale cap).
FILE_INTEGRITY_MAX_SCAN_ROWS = 50_000
# Share of records whose field count deviates from the dominant count.
FILE_INTEGRITY_RAGGED_FLAG_SHARE = 0.02
FILE_INTEGRITY_RAGGED_BLOCK_SHARE = 0.10
# A record holding >= this multiple of the dominant field count while also
# containing quote characters indicates concatenated/merged records.
FILE_INTEGRITY_CONCAT_FIELD_MULTIPLE = 2
FILE_INTEGRITY_CONCAT_MIN_ROWS = 3
# Share of U+FFFD replacement characters in decoded text that indicates
# broken encoding rather than exotic-but-valid content.
FILE_INTEGRITY_REPLACEMENT_CHAR_SHARE = 0.01

# ---------------------------------------------------------------------------
# Post-parse SCHEMA integrity (DataFrame level, after parsing, before
# semantic column understanding)
# ---------------------------------------------------------------------------

# Share of columns named "Unnamed: N" that indicates a missing/misaligned
# header row rather than a cosmetic quirk.
SCHEMA_UNNAMED_BLOCK_SHARE = 0.25
# Mixed-type object columns: a value-type holding at least this share of
# non-null cells (besides the dominant type) suggests parser coercion
# fallback (numeric column degraded to text mid-file).
SCHEMA_MIXED_TYPE_MINORITY_SHARE = 0.05
SCHEMA_MIXED_TYPE_MAX_FINDINGS = 10
# Duplicate-row-ratio visibility thresholds (FLAG only: repetition may be
# perfectly legitimate).
SCHEMA_DUP_ROW_MEDIUM = 0.50
SCHEMA_DUP_ROW_HIGH = 0.90

# ---------------------------------------------------------------------------
# Phase 5: additional evidence-driven detectors
# ---------------------------------------------------------------------------

# Rows identical after case/space normalization are reported when they form
# at least this share of the dataset (they may be legitimate repeats).
NEAR_DUPLICATE_FLAG_SHARE = 0.02
NEAR_DUPLICATE_HIGH_SHARE = 0.20
NEAR_DUPLICATE_MIN_GROUP = 2

# Temporal sanity: datetimes beyond these bounds are flagged, never fixed.
TEMPORAL_FUTURE_TOLERANCE_DAYS = 1
TEMPORAL_MIN_YEAR = 1900

# Unit-inconsistency: two magnitude modes separated by at least this many
# orders of magnitude, each holding >= UNIT_MODE_MIN_SHARE of values,
# suggest mixed measurement units in one column.
UNIT_MODE_GAP_ORDERS = 2.0
UNIT_MODE_MIN_SHARE = 0.15
UNIT_MODE_MIN_PER_MODE = 8


class InspectionResult(BaseModel):
    """Read-only overview of the dataset before any cleaning."""

    rows: int = 0
    column_count: int = 0
    column_names: List[str] = Field(default_factory=list)
    dtypes: Dict[str, str] = Field(default_factory=dict)
    total_missing: int = 0
    total_cells: int = 0
    duplicate_row_count: int = 0
    duplicate_ratio: float = 0.0
    constant_columns: List[str] = Field(default_factory=list)
    near_constant_columns: List[str] = Field(default_factory=list)
    memory_usage_mb: float = 0.0


class ColumnProfile(BaseModel):
    """Semantic understanding of a single column.

    Deliberately does NOT trust the pandas dtype alone: `semantic_type`
    combines dtype evidence with cardinality/name/content signals.
    """

    name: str
    physical_dtype: str
    semantic_type: SemanticType = "categorical"
    cardinality: int = 0
    unique_ratio: float = 0.0
    missing_count: int = 0
    missing_ratio: float = 0.0
    constant: bool = False
    near_constant: bool = False
    dominant_share: float = 0.0
    is_possible_id: bool = False
    is_possible_date: bool = False
    numeric_stats: Optional[Dict[str, float]] = None
    top_values: List[Dict[str, Any]] = Field(default_factory=list)

    # Explicit metadata (Phase 1): populated from caller-declared rules by
    # the engine before detection. Detectors read these instead of guessing.
    valid_min: Optional[float] = None
    valid_max: Optional[float] = None
    allowed_values: Optional[List[str]] = None
    suppression_tokens: List[str] = Field(default_factory=list)
    declared_formula: Optional[Dict[str, Any]] = None

    # Semantic understanding (Phase 4): richer, evidence-derived context.
    # e.g. "email", "phone", "uuid", "zip_code", "ip_address", "url",
    # "currency_amount", "geo_coordinate". Protected subtypes are mirrored
    # into semantic_type="identifier".
    semantic_subtype: Optional[str] = None
    quasi_identifier: bool = False
    # Dominant character-class fingerprint for string columns:
    # {"signature": "dddd-dddd", "share": 0.97}
    pattern_signature: Optional[Dict[str, Any]] = None
    # Histogram of scalar value classes for string columns
    # ({numeric, date, boolean, text} -> count).
    value_class_histogram: Optional[Dict[str, int]] = None
    # Numeric/datetime extras: {"integer_like":bool,"negative_count":int,
    # "zero_share":float,"sequential":bool} / {"granularity":str,
    # "span_days":float}.
    value_profile: Optional[Dict[str, Any]] = None


class Evidence(BaseModel):
    """Structured, deterministic findings produced by a Detector.

    Detectors never modify DataFrames; they only report what they observed.
    """

    detector: str
    problem_type: ProblemType
    column: Optional[str] = None  # None for dataframe-level problems (duplicates)
    method: str
    affected_count: int = 0
    affected_row_indices: List[int] = Field(default_factory=list)
    statistics: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    severity: Severity = "low"
    explanation: str = ""

    @property
    def key(self) -> str:
        return f"{self.detector}:{self.column or '<dataset>'}:{self.method}"


class Decision(BaseModel):
    """The Decision Engine's verdict for one piece of Evidence.

    The Decision Engine never touches the DataFrame; it only approves,
    skips or flags a proposed action with explicit parameters.
    """

    evidence: Evidence
    verdict: Verdict
    action: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    reasons: List[str] = Field(default_factory=list)
    # Machine-readable rule evaluations supporting the verdict:
    # [{"rule": str, "passed": bool, "detail": str}, ...]
    policy_checks: List[Dict[str, Any]] = Field(default_factory=list)


class ActionKind:
    """Mutation classification used by policy/budget logic."""

    CONTENT = "content"          # rewrites existing cell values
    ANNOTATION = "annotation"    # adds columns, never alters cells
    ROW_REMOVAL = "row_removal"  # removes rows
    SCHEMA = "schema"            # drops/renames columns; row count unchanged


class CleaningPolicy(BaseModel):
    """Unified decision policy for one CleaningEngine run.

    Defaults reproduce historical behaviour exactly. New knobs only ever
    make the engine MORE conservative.
    """

    enable_imputation: bool = True
    enable_duplicate_removal: bool = True
    add_outlier_flags: bool = True
    enable_formatting_normalization: bool = True
    enable_categorical_normalization: bool = True
    enable_derived_repair: bool = True
    enable_type_normalization: bool = True
    # APPLY requires evidence confidence >= this bar.
    min_apply_confidence: float = 0.0
    # When True, every APPLY is downgraded to FLAG with an explanatory
    # reason and NO data modification happens anywhere in the run.
    dry_run: bool = False
    # Maximum approved content-mutating actions per column per run
    # (annotation-only actions such as outlier flags do not count).
    max_mutations_per_column: int = 1
    # Optional global cap across the whole run (None = unlimited).
    max_total_mutations: Optional[int] = None


class ValidationResult(BaseModel):
    """Outcome of real before/after comparison for one applied action."""

    passed: bool = False
    checks: Dict[str, bool] = Field(default_factory=dict)
    failures: List[str] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)

    def record(self, check_name: str, passed: bool, failure_message: str = "") -> None:
        self.checks[check_name] = bool(passed)
        if not passed:
            self.failures.append(failure_message or check_name)
        self.passed = all(self.checks.values())


class CleaningLogEntry(BaseModel):
    """Structured log for every executed action attempt.

    Records WHAT changed, WHY, on WHICH evidence, HOW MANY rows were
    affected and WHETHER validation passed or rollback happened.
    Entries are chained cryptographically (entry_id / prev_hash /
    entry_hash) making the trail tamper-evident.
    """

    action: str
    decision_verdict: Verdict
    problem_type: ProblemType
    column: Optional[str] = None
    detector: str
    method: str
    confidence: float = 0.0
    reasons: List[str] = Field(default_factory=list)
    applied: bool = False
    rolled_back: bool = False
    rollback_verified: Optional[bool] = None
    rows_affected: int = 0
    cells_changed: int = 0
    columns_touched: List[str] = Field(default_factory=list)
    before_state: Dict[str, Any] = Field(default_factory=dict)
    after_state: Dict[str, Any] = Field(default_factory=dict)
    validation: Optional[ValidationResult] = None
    error: Optional[str] = None
    # Cell-level change ledger from content-mutating actions (bounded):
    # [{"column": str, "row": int, "before": Any, "after": Any}, ...]
    changes: List[Dict[str, Any]] = Field(default_factory=list)
    # Logical inverse records sufficient to hand-revert the edit
    # (rollback itself always uses the pre-action snapshot).
    inverse: List[Dict[str, Any]] = Field(default_factory=list)
    # Provenance chain (Phase 8).
    entry_id: int = -1
    prev_hash: str = ""
    entry_hash: str = ""


# ---------------------------------------------------------------------------
# Phase 9: cleaning strategy orchestration
# ---------------------------------------------------------------------------

StrategyName = Literal["standard", "structure_only", "scale_guarded"]

# Auto-promotion threshold: datasets above this row count run under the
# scale_guarded strategy unless a strategy is requested explicitly.
SCALE_AUTO_PROMOTE_ROWS = 100_000


class CleaningStrategy(BaseModel):
    """How a run should be orchestrated.

    Strategies change COVERAGE and COST, never safety: every strategy keeps
    the integrity gates, decision gate, validation and rollback machinery.
    """

    name: StrategyName = "standard"
    # structure_only runs integrity gates + profiling and stops: ideal for
    # fast trust/triage passes ("can this dataset be cleaned safely?").
    enable_detection: bool = True
    # Bound on how many numeric columns participate in O(n^2) pair scans
    # (derived-column consistency). None = unlimited.
    max_numeric_pair_cols: Optional[int] = None
    # Row cap for correlation-based analysis (semantic anomaly detector).
    max_corr_rows: Optional[int] = None


def resolve_strategy(
    requested: Optional[Union[str, "CleaningStrategy"]],
    rows: int,
    columns: int,
) -> "CleaningStrategy":
    """Resolve a requested strategy against the actual dataset size.

    Auto-promotion to scale_guarded happens ONLY when no strategy was
    explicitly requested. An explicit request always wins.
    """
    if requested is None:
        name = (
            "scale_guarded"
            if rows >= SCALE_AUTO_PROMOTE_ROWS
            else "standard"
        )
    elif isinstance(requested, CleaningStrategy):
        return requested.model_copy()
    else:
        name = str(requested)

    known = {"standard", "structure_only", "scale_guarded"}
    if name not in known:
        raise ValueError(
            f"Unknown cleaning strategy '{name}'. Valid: {sorted(known)}"
        )

    if name == "structure_only":
        return CleaningStrategy(
            name="structure_only", enable_detection=False,
            max_numeric_pair_cols=0, max_corr_rows=0,
        )
    if name == "scale_guarded":
        # Deterministic bounds: enough columns to stay useful, few enough
        # to keep pair scans linear-ish.
        cap = max(8, min(24, columns))
        return CleaningStrategy(
            name="scale_guarded",
            enable_detection=True,
            max_numeric_pair_cols=cap,
            max_corr_rows=min(rows, 5000),
        )
    return CleaningStrategy(name="standard")


class CleaningResult(BaseModel):
    """Full structured result of one CleaningEngine run."""

    success: bool = True
    blocked: bool = False
    assessment: str = ""  # CLEAN / MOSTLY CLEAN / NEEDS REVIEW / NEEDS CLEANING / BLOCKED
    inspection: InspectionResult = Field(default_factory=InspectionResult)
    column_profiles: List[ColumnProfile] = Field(default_factory=list)
    structural_findings: List[Dict[str, Any]] = Field(default_factory=list)
    decisions: List[Decision] = Field(default_factory=list)
    log: List[CleaningLogEntry] = Field(default_factory=list)
    flagged_issues: List[Evidence] = Field(default_factory=list)
    information_loss_warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    # Whole-run accounting validation (Phase 7): row/column/dtype deltas.
    run_validation: Dict[str, Any] = Field(default_factory=dict)
    # Provenance & audit trail (Phase 8).
    input_digest: str = ""
    output_digest: str = ""
    policy_snapshot: Dict[str, Any] = Field(default_factory=dict)
    rules_snapshot: Dict[str, Any] = Field(default_factory=dict)
    chain_root: str = ""
    # Strategy orchestration (Phase 9).
    strategy: str = ""
    strategy_plan: Dict[str, Any] = Field(default_factory=dict)
