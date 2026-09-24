"""Structural / input-integrity checks for the DataWise Cleaning Engine.

This layer runs BEFORE inspection-grade cleaning and is strictly READ-ONLY.

It detects downstream symptoms of upstream parse corruption:
    - text fragments / delimiters / stray quotes merged into identifier values
    - column-shift symptoms (delimiters inside numeric-like semantic columns)
    - fixed-width truncation patterns
    - quote/escape artifacts

It NEVER attempts speculative reconstruction. Corruption is reported as
BLOCK (dataset cannot be trusted for transformative cleaning) or FLAG
(suspicious but not provably fatal). The engine short-circuits to a
BLOCKED result when any BLOCK-level finding exists.
"""
import re
from typing import Any, Dict, List, Optional

import pandas as pd

from backend.cleaning.contracts import (
    ID_CORRUPTION_MIN_CELLS,
    ID_CORRUPTION_SHARE,
    SCHEMA_DUP_ROW_HIGH,
    SCHEMA_DUP_ROW_MEDIUM,
    SCHEMA_MIXED_TYPE_MAX_FINDINGS,
    SCHEMA_MIXED_TYPE_MINORITY_SHARE,
    SCHEMA_UNNAMED_BLOCK_SHARE,
    STRUCTURAL_DELIMITERS,
    TRUNCATION_MIN_VALUES,
    TRUNCATION_SAME_MAX_LENGTH_SHARE,
    ColumnProfile,
    InspectionResult,
)

_QUOTE_ARTIFACT_RE = re.compile(r"^[\"']|[\"']$")
_DELIMITER_RE = "|".join(map(re.escape, STRUCTURAL_DELIMITERS))


class StructuralFinding(dict):
    """Plain dict finding: {check, severity: 'block'|'flag', column,
    affected_count, details}."""


def check_structural_integrity(
    df: pd.DataFrame,
    profiles: Dict[str, ColumnProfile],
    inspection: InspectionResult,
) -> List[StructuralFinding]:
    """Run all read-only integrity checks and return findings."""
    if inspection.rows == 0 or inspection.column_count == 0:
        return []
    findings: List[StructuralFinding] = []
    findings.extend(_check_identifier_corruption(df, profiles))
    findings.extend(_check_delimiter_bleed(df, profiles))
    findings.extend(_check_truncation_pattern(df, profiles))
    return findings


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def _check_identifier_corruption(
    df: pd.DataFrame, profiles: Dict[str, ColumnProfile]
) -> List[StructuralFinding]:
    """IDs containing quotes/delimiters/double-spaces indicate mis-parsed
    source structure. Additionally, when >=95% of an identifier's values are
    pure tokens (e.g. digits) and others carry stray characters, those
    outliers are treated as text-merged corruption. Either way row alignment
    of the source cannot be trusted => BLOCK."""
    findings: List[StructuralFinding] = []
    delim_re = "|".join(map(re.escape, STRUCTURAL_DELIMITERS))
    token_re = r"[A-Za-z0-9_\-\.\/]+"

    for col in df.columns:
        profile = profiles.get(str(col))
        if profile is None or profile.semantic_type != "identifier":
            continue
        series = df[col].dropna()
        if series.empty:
            continue
        strings = series.astype(str)
        non_blank = strings[strings.str.strip() != ""]
        if non_blank.empty:
            continue

        corrupted = (
            non_blank.str.contains(delim_re, regex=True)
            | non_blank.str.match(_QUOTE_ARTIFACT_RE)
            | non_blank.str.contains(r"\s{2,}", regex=True)
        )

        sample = non_blank.head(5000)
        pure_digit_share = float(sample.str.fullmatch(r"[0-9]+").mean())
        if pure_digit_share >= 0.95:
            # Dominant format is numeric IDs; alphanumeric contamination in
            # ANY value signals merged text fragments.
            contaminated = ~non_blank.str.fullmatch(r"[0-9]+")
            corrupted = corrupted | contaminated

        count = int(corrupted.sum())
        share = count / max(len(non_blank), 1)
        if (
            count >= ID_CORRUPTION_MIN_CELLS
            or (count > 0 and share >= ID_CORRUPTION_SHARE)
        ):
            examples = [str(v)[:60] for v in non_blank[corrupted].head(5)]
            findings.append(StructuralFinding(
                check="identifier_corruption",
                severity="block",
                column=str(col),
                affected_count=count,
                details={
                    "corrupted_share": round(share, 6),
                    "examples": examples,
                    "reason": (
                        "Identifier values contain delimiters/quotes/"
                        "unexpected text - row alignment of the source "
                        "cannot be trusted."
                    ),
                },
            ))
    return findings


def _check_delimiter_bleed(
    df: pd.DataFrame, profiles: Dict[str, ColumnProfile]
) -> List[StructuralFinding]:
    """Delimiters inside numeric-semantic columns indicate column-shift
    parsing damage. A string column whose clean values are overwhelmingly
    parseable numbers counts as numeric-semantic here. Categorical prose
    legitimately contains commas and is never auto-BLOCKED."""
    findings: List[StructuralFinding] = []
    delim_re = re.compile(_DELIMITER_RE)
    for col in df.columns:
        profile = profiles.get(str(col))
        if profile is None:
            continue
        if profile.semantic_type not in ("numeric", "categorical", "boolean"):
            continue
        series = df[col]
        if not (pd.api.types.is_object_dtype(series)
                or pd.api.types.is_string_dtype(series)):
            continue
        strings = series.dropna().astype(str)
        if strings.empty:
            continue
        bleed = strings.str.contains(delim_re, regex=True)
        count = int(bleed.sum())
        if count == 0:
            continue
        share = count / len(strings)

        if profile.semantic_type in ("numeric", "boolean"):
            severity = "block" if share >= ID_CORRUPTION_SHARE else "flag"
        else:
            # String columns: only numeric-looking content escalates.
            clean = strings[~bleed]
            parseable = (
                clean.str.fullmatch(r"[+-]?\d+(\.\d+)?").mean()
                if len(clean) else 0.0
            )
            looks_numeric = float(parseable) >= 0.90
            if looks_numeric:
                severity = "block" if share >= ID_CORRUPTION_SHARE else "flag"
            else:
                severity = "flag"

        findings.append(StructuralFinding(
            check="delimiter_bleed",
            severity=severity,
            column=str(col),
            affected_count=count,
            details={
                "share": round(share, 6),
                "examples": [str(v)[:60] for v in strings[bleed].head(5)],
                "reason": (
                    "Field delimiters found inside a "
                    f"{profile.semantic_type} column; possible column shift."
                ),
            },
        ))
    return findings


def _check_truncation_pattern(
    df: pd.DataFrame, profiles: Dict[str, ColumnProfile]
) -> List[StructuralFinding]:
    """Many string values sharing EXACTLY the maximal length suggests
    fixed-width truncation (e.g. school-name columns cut at N chars)."""
    findings: List[StructuralFinding] = []
    for col in df.columns:
        profile = profiles.get(str(col))
        if profile is None or profile.semantic_type not in ("text", "categorical"):
            continue
        if profile.cardinality < TRUNCATION_MIN_VALUES // 2:
            continue  # small closed category sets are naturally uniform
        strings = df[col].dropna().astype(str)
        if len(strings) < TRUNCATION_MIN_VALUES:
            continue
        max_len = int(strings.str.len().max())
        if max_len < 8:
            continue
        at_max = int((strings.str.len() == max_len).sum())
        share = at_max / len(strings)
        if share >= TRUNCATION_SAME_MAX_LENGTH_SHARE:
            findings.append(StructuralFinding(
                check="fixed_width_truncation",
                severity="flag",
                column=str(col),
                affected_count=at_max,
                details={
                    "max_length": max_len,
                    "share_at_max_length": round(share, 4),
                    "reason": (
                        "A large share of values has exactly the maximal "
                        "length; text may have been truncated at source."
                    ),
                },
            ))
    return findings


# ===========================================================================
# Post-parse SCHEMA integrity (DataFrame level)
#
# Complements the raw-text layer: validates the PARSED artifact itself
# (also covers pickled inputs that never went through CSV parsing).
# Read-only. Findings use severities: block | flag | info.
# ===========================================================================

_UNNAMED_RE = re.compile(r"^Unnamed: \d+")
# Stringified sentinels that only appear when a frame was round-tripped
# through lossy text coercion (e.g. to_csv of a frame with NaNs then read
# back with keep_default_na=False).
_STRINGIFIED_SENTINELS = {"nan", "<na>", "nat", "none", "null"}


def check_schema_integrity(
    df: pd.DataFrame,
    profiles: Dict[str, ColumnProfile],
    inspection: InspectionResult,
) -> List[Dict[str, Any]]:
    """Schema/column integrity checks on the parsed DataFrame."""
    findings: List[Dict[str, Any]] = []
    if inspection.rows == 0 or inspection.column_count == 0:
        return findings

    # Duplicate labels first: every other check addresses columns by name,
    # which is ambiguous under duplication - so stop immediately.
    dupe_findings = _check_duplicate_column_names(df)
    if dupe_findings:
        findings.extend(dupe_findings)
        return findings

    findings.extend(_check_unnamed_columns(df))
    findings.extend(_check_empty_columns(df, inspection))
    _append_constant_column_summary(findings, df, inspection)
    findings.extend(_check_duplicate_row_ratio(inspection))
    findings.extend(_check_mixed_type_object_columns(df))
    findings.extend(_check_stringified_sentinels(df))
    return findings


def quick_duplicate_column_check(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """Label-free pre-inspection guard: safe to call before profiles exist.

    Returns the blocking finding when duplicate labels are present, else
    None. Inspection/profile building iterate columns by label and would
    themselves crash under duplication, so this must run first.
    """
    if len(df.columns) == 0:
        return None
    dupes = df.columns[df.columns.duplicated()].tolist()
    if not dupes:
        return None
    return _check_duplicate_column_names(df)[0]


def _check_duplicate_column_names(df: pd.DataFrame) -> List[Dict[str, Any]]:
    dupes = df.columns[df.columns.duplicated()].tolist()
    if not dupes:
        return []
    return [{
        "check": "duplicate_column_names",
        "severity": "block",
        "column": ", ".join(sorted({str(d) for d in dupes})),
        "affected_count": len(dupes),
        "details": {
            "reason": (
                "Duplicate column labels make column addressing ambiguous; "
                "mutations could silently hit the wrong column."
            ),
            "duplicates": sorted({str(d) for d in dupes}),
        },
    }]


def _check_unnamed_columns(df: pd.DataFrame) -> List[Dict[str, Any]]:
    unnamed = [
        str(c) for c in df.columns
        if _UNNAMED_RE.match(str(c)) or not str(c).strip()
    ]
    if not unnamed:
        return []
    share = len(unnamed) / max(len(df.columns), 1)
    severity = "block" if share >= SCHEMA_UNNAMED_BLOCK_SHARE else "flag"
    return [{
        "check": "unnamed_columns",
        "severity": severity,
        "column": ", ".join(unnamed[:8]),
        "affected_count": len(unnamed),
        "details": {
            "share": round(share, 4),
            "reason": (
                "A majority of columns is unnamed - the header row is "
                "missing or misaligned (classic column-shift symptom)."
                if severity == "block" else
                "Some columns carry auto-generated names; parsing may have "
                "produced stray columns."
            ),
        },
    }]


def _check_empty_columns(
    df: pd.DataFrame, inspection: InspectionResult
) -> List[Dict[str, Any]]:
    empty = [str(c) for c in df.columns if int(df[c].isna().sum()) == inspection.rows]
    if not empty:
        return []
    return [{
        "check": "empty_columns",
        "severity": "flag",
        "column": ", ".join(empty[:8]),
        "affected_count": len(empty),
        "details": {
            "reason": "Columns contain no values at all.",
            "columns": empty[:20],
        },
    }]


def _append_constant_column_summary(
    findings: List[Dict[str, Any]],
    df: pd.DataFrame,
    inspection: InspectionResult,
) -> None:
    if inspection.constant_columns:
        findings.append({
            "check": "constant_columns",
            "severity": "info",
            "column": ", ".join(inspection.constant_columns[:8]),
            "affected_count": len(inspection.constant_columns),
            "details": {
                "columns": inspection.constant_columns[:20],
                "reason": (
                    "Constant columns carry no discriminative information; "
                    "reported for awareness, never dropped automatically."
                ),
            },
        })


def _check_duplicate_row_ratio(inspection: InspectionResult) -> List[Dict[str, Any]]:
    ratio = inspection.duplicate_ratio
    if ratio < SCHEMA_DUP_ROW_MEDIUM:
        return []
    return [{
        "check": "high_duplicate_row_ratio",
        "severity": "flag",
        "column": None,
        "affected_count": inspection.duplicate_row_count,
        "details": {
            "level": "medium" if ratio < SCHEMA_DUP_ROW_HIGH else "high",
            "duplicate_ratio": ratio,
            "reason": (
                "A large share of this dataset consists of exact duplicate "
                "rows; repetition may be legitimate, but it warrants review."
            ),
        },
    }]


def _check_mixed_type_object_columns(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Object columns mixing Python value types are the classic symptom of
    parser coercion fallback: a numeric column degrades to text the moment
    one non-numeric cell appears mid-file."""
    findings: List[Dict[str, Any]] = []
    emitted = 0
    for col in df.columns:
        if emitted >= SCHEMA_MIXED_TYPE_MAX_FINDINGS:
            break
        series = df[col]
        if not (pd.api.types.is_object_dtype(series)
                or pd.api.types.is_string_dtype(series)):
            continue
        non_null = series.dropna()
        if non_null.empty:
            continue
        type_hist: Dict[str, int] = {}
        for value in non_null.head(5000):
            name = type(value).__name__
            type_hist[name] = type_hist.get(name, 0) + 1
        if len(type_hist) < 2:
            continue
        total = sum(type_hist.values())
        ordered = sorted(type_hist.items(), key=lambda kv: kv[1], reverse=True)
        minority_share = 1.0 - ordered[0][1] / total
        if minority_share < SCHEMA_MIXED_TYPE_MINORITY_SHARE:
            continue
        emitted += 1
        findings.append({
            "check": "mixed_type_column",
            "severity": "flag",
            "column": str(col),
            "affected_count": total - ordered[0][1],
            "details": {
                "type_histogram": dict(ordered),
                "minority_share": round(minority_share, 4),
                "reason": (
                    "Object column mixes Python value types - typical "
                    "parser coercion fallback when a numeric column meets "
                    "a non-numeric cell mid-file."
                ),
            },
        })
    return findings


def _check_stringified_sentinels(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Literal 'nan'/'None'-style strings indicate the frame was round-tripped
    through text with missing values flattened into words."""
    findings: List[Dict[str, Any]] = []
    emitted = 0
    for col in df.columns:
        if emitted >= SCHEMA_MIXED_TYPE_MAX_FINDINGS:
            break
        series = df[col]
        if not (pd.api.types.is_object_dtype(series)
                or pd.api.types.is_string_dtype(series)):
            continue
        strings = series.dropna().astype(str).str.strip().str.lower()
        if strings.empty:
            continue
        distinct = set(strings.unique())
        sentinel_hits = distinct & _STRINGIFIED_SENTINELS
        # Tiny closed sets may legitimately contain such words as categories.
        if not sentinel_hits or len(distinct) <= 5:
            continue
        sentinel_rows = int(strings.isin(sentinel_hits).sum())
        share = sentinel_rows / len(strings)
        if share < SCHEMA_MIXED_TYPE_MINORITY_SHARE:
            continue
        emitted += 1
        findings.append({
            "check": "stringified_missing_sentinels",
            "severity": "flag",
            "column": str(col),
            "affected_count": sentinel_rows,
            "details": {
                "share": round(share, 4),
                "sentinels_seen": sorted(sentinel_hits),
                "reason": (
                    "Literal 'nan'/'None'-style strings suggest the frame "
                    "was round-tripped through text with missing values "
                    "flattened into words."
                ),
            },
        })
    return findings
