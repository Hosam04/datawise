"""Duplicate detectors for the DataWise Cleaning Engine."""
from typing import Dict, List

import numpy as np
import pandas as pd

from backend.cleaning.contracts import (
    NEAR_DUPLICATE_FLAG_SHARE,
    NEAR_DUPLICATE_HIGH_SHARE,
)
from backend.cleaning.detectors.base import (
    BaseDetector,
    Evidence,
    ColumnProfile,
    InspectionResult,
    _sample_indices,
    _jsonable,
)


class DuplicateDetector(BaseDetector):
    """Reports exact duplicate rows, EXCLUDING identifier columns."""

    name = "DuplicateDetector"
    problem_type = "duplicates"
    # Duplicate counts may change after content mutations such as imputation.
    # Detect the final state before deciding whether to remove duplicates.
    rerun_after_actions = True

    def detect(self, df, profiles, inspection) -> List[Evidence]:
        if inspection.rows == 0:
            return []

        id_cols = [
            c for c in df.columns
            if profiles.get(str(c)) is not None
            and profiles[str(c)].semantic_type == "identifier"
        ]
        cols_for_dup = [c for c in df.columns if c not in id_cols]

        if not cols_for_dup:
            return []

        dup_mask = df[cols_for_dup].duplicated(keep="first")
        count = int(dup_mask.sum())
        if count == 0:
            return []

        ratio = round(count / max(inspection.rows, 1), 6)
        severity = "high" if ratio > 0.5 else ("medium" if ratio >= 0.01 else "low")

        return [
            Evidence(
                detector=self.name,
                problem_type=self.problem_type,
                column=None,
                method="exact_row_match",
                affected_count=count,
                affected_row_indices=_sample_indices(df.index[dup_mask].tolist()),
                statistics={
                    "duplicate_rows": count,
                    "duplicate_ratio": ratio,
                    "total_rows": inspection.rows,
                    "excluded_identifier_columns": [str(c) for c in id_cols],
                    "largest_duplicate_group": int(df.groupby(list(cols_for_dup), dropna=False).size().max())
                    if cols_for_dup else 0,
                },
                confidence=1.0,
                severity=severity,
                explanation=(
                    f"{count} exact duplicate row(s) detected "
                    f"({ratio:.1%} of dataset)."
                    + (f" Identifier columns excluded: {id_cols}." if id_cols else "")
                ),
            )
        ]


class NearDuplicateDetector(BaseDetector):
    """Detects rows that become exact duplicates only AFTER light text
    normalization (case/whitespace/punctuation-of-separators). These are the
    duplicates blind exact-match checks miss and blind deletion destroys
    context on - reported as evidence groups, never removed."""

    name = "NearDuplicateDetector"
    problem_type = "duplicates"

    def detect(self, df, profiles, inspection) -> List[Evidence]:
        evidence: List[Evidence] = []
        if inspection.rows == 0:
            return evidence

        normalized = df.copy()
        for col in df.columns:
            series = df[col]
            if pd.api.types.is_object_dtype(series) \
                    or pd.api.types.is_string_dtype(series):
                normalized[col] = (
                    series.astype("string").str.strip().str.lower()
                    .str.replace(r"\s+", " ", regex=True)
                )

        raw_dupes = int(df.duplicated().sum())
        norm_mask = normalized.duplicated(keep="first")
        norm_dupes = int(norm_mask.sum())
        extra = norm_dupes - raw_dupes

        if extra <= 0:
            return evidence

        share = extra / max(inspection.rows, 1)
        if share < NEAR_DUPLICATE_FLAG_SHARE:
            return evidence

        severity = "high" if share >= NEAR_DUPLICATE_HIGH_SHARE else "medium"
        example_labels = df.index[norm_mask][:5].tolist()
        examples = [
            {str(c): _jsonable(df.at[label, c]) for c in list(df.columns)[:5]}
            for label in example_labels
        ]
        evidence.append(Evidence(
            detector=self.name,
            problem_type=self.problem_type,
            column=None,
            method="normalized_row_duplicates",
            affected_count=extra,
            affected_row_indices=_sample_indices(df.index[norm_mask].tolist()),
            statistics={
                "exact_duplicate_rows": raw_dupes,
                "normalized_duplicate_rows": norm_dupes,
                "extra_after_normalization": extra,
                "share": round(share, 6),
                "examples": examples,
                "note": (
                    "Distinct after case/whitespace normalization only; "
                    "removal is a caller decision, not automatic."
                ),
            },
            confidence=0.85,
            severity=severity,
            explanation=(
                f"{extra} row(s) duplicate others once case/whitespace "
                f"differences are ignored ({share:.2%} of dataset)."
            ),
        ))
        return evidence