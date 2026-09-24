"""Missing value detectors for the DataWise Cleaning Engine."""
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from backend.cleaning.detectors.base import (
    BaseDetector,
    Evidence,
    ColumnProfile,
    InspectionResult,
    _sample_indices,
    MISSING_STRING_TOKENS,
    SUPPRESSION_TOKEN_CANDIDATES,
)


class MissingValueDetector(BaseDetector):
    """Reports per-column missing values with enough context to decide
    whether imputation is justified — never fills anything itself.

    Composition-aware: distinguishes real NaN/None from empty strings,
    whitespace-only strings and common missing tokens, and classifies
    SUPPRESSION-style tokens ('s', 'Suppressed', 'Not Available', ...) as
    semantic values that must be preserved, never converted to numbers.
    """

    name = "MissingValueDetector"
    problem_type = "missing_values"

    def __init__(self, extra_suppression_tokens: Optional[List[str]] = None):
        # Dataset-global suppression tokens supplied via explicit metadata.
        self.extra_suppression_tokens = list(extra_suppression_tokens or [])

    def detect(self, df, profiles, inspection) -> List[Evidence]:
        evidence: List[Evidence] = []
        if inspection.rows == 0:
            return evidence

        missing = df.isna().sum()
        for col in df.columns:
            count = int(missing[col])
            profile = profiles.get(str(col))
            semantic = profile.semantic_type if profile else "categorical"

            composition = self._composition(df[col])
            # Keep whitespace-only explicit for evidence/reporting while
            # preserving the existing effective-missing `empty` count.
            composition["whitespace_only"] = int(composition.get("whitespace_only", 0))
            composition["missing_token"] = int(composition.get("missing_token", 0))
            # empty = truly empty OR whitespace-only (both are missing-equivalent)
            # missing_token = ?, NA, null, unknown, ... (also missing-equivalent)
            # padded = non-empty values that only differ by leading/trailing spaces
            #         (NOT counted as missing)
            effective_missing = (
                count + composition["empty"] + composition["missing_token"]
            )
            if effective_missing == 0:
                # Still check for suppression-token dominance below.
                self._maybe_suppression_evidence(df, col, semantic, composition, profile, evidence)
                continue

            # Ratio must match affected_count (NaN + empty + missing tokens)
            ratio = round(effective_missing / max(inspection.rows, 1), 6)

            severity = self._severity(ratio)
            token_part = (
                f", {composition['missing_token']} missing-token(s)"
                if composition["missing_token"]
                else ""
            )
            explanation = (
                f"Column '{col}' ({semantic}) has {effective_missing} "
                f"missing-equivalent value(s): {count} NaN, "
                f"{composition['empty']} empty/whitespace-only"
                f"{token_part} "
                f"({ratio:.1%} of rows)"
                + (
                    f"; {composition['padded']} value(s) have padding spaces"
                    if composition.get("padded", 0)
                    else ""
                )
                + "."
            )

            # Row indices: NaN + empty/whitespace-only + missing-string tokens
            missing_idx = set(df.index[df[col].isna()].tolist())
            if (
                pd.api.types.is_object_dtype(df[col])
                or pd.api.types.is_string_dtype(df[col])
            ):
                strings = df[col].dropna().astype("string")
                stripped = strings.str.strip()
                empty_mask = stripped == ""
                token_set = {t.lower() for t in MISSING_STRING_TOKENS}
                token_mask = stripped.str.lower().isin(token_set)
                if composition["empty"] > 0:
                    missing_idx.update(strings.index[empty_mask].tolist())
                if composition["missing_token"] > 0:
                    missing_idx.update(strings.index[token_mask].tolist())

            evidence.append(
                Evidence(
                    detector=self.name,
                    problem_type=self.problem_type,
                    column=str(col),
                    method="column_missing_profile",
                    affected_count=effective_missing,
                    affected_row_indices=_sample_indices(sorted(missing_idx)),
                    statistics={
                        "nan_count": count,
                        "empty_string_count": composition["empty"],
                        "whitespace_only_count": int(composition.get("whitespace_only", 0)),
                        "missing_token_count": composition["missing_token"],
                        "padded_count": composition.get("padded", 0),
                        "effective_missing": effective_missing,
                        "missing_ratio": ratio,
                        "semantic_type": semantic,
                        "non_null_count": max(
                            0,
                            int(df[col].notna().sum())
                            - composition["empty"]
                            - composition["missing_token"],
                        ),
                        "constant": bool(profile.constant) if profile else False,
                    },
                    confidence=0.99,  # deterministic counting
                    severity=severity,
                    explanation=explanation,
                )
            )
            self._maybe_suppression_evidence(df, col, semantic, composition, profile, evidence)
        return evidence

    # ------------------------------------------------------------------

    @staticmethod
    def _composition(series: pd.Series) -> Dict[str, int]:
        """Count NaN vs empty/whitespace-only vs missing-string tokens vs padded.

        - empty: values that are '' or whitespace-only after strip (missing-equivalent)
        - whitespace_only: non-empty original values that become '' after strip
        - missing_token: non-empty values matching MISSING_STRING_TOKENS (?, NA, null, ...)
        - padded: non-empty values that change after strip (have side spaces; NOT missing)
        """
        nan_count = int(series.isna().sum())
        empty = 0
        whitespace_only = 0
        missing_token = 0
        padded = 0
        if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
            strings = series.dropna().astype("string")
            stripped = strings.str.strip()
            empty = int((stripped == "").sum())
            # Original had content (spaces) but strip left nothing → whitespace-only
            whitespace_only = int(
                ((stripped == "") & (strings.str.len() > 0)).sum()
            )
            # Classic missing-string tokens (?, NA, null, unknown, ...)
            token_set = {t.lower() for t in MISSING_STRING_TOKENS}
            missing_token = int(
                stripped.str.lower().isin(token_set).sum()
            )
            # Non-empty after strip but different from original → has padding only
            # (exclude pure missing tokens from the padded count)
            padded = int(
                (
                    (stripped != "")
                    & (stripped != strings)
                    & (~stripped.str.lower().isin(token_set))
                ).sum()
            )
        return {
            "nan": nan_count,
            "empty": empty,
            "whitespace_only": whitespace_only,
            "missing_token": missing_token,
            "padded": padded,
            "whitespace": whitespace_only,
        }

    def _maybe_suppression_evidence(
        self, df, col, semantic, composition, profile, evidence
    ):
        """Flag columns containing suppression-style tokens.

        Caller-DECLARED tokens (explicit metadata) are reported on ANY
        occurrence; built-in candidate tokens require a minimal presence
        before they are worth reporting. Evidence ONLY either way.
        """
        if not (pd.api.types.is_object_dtype(df[col])
                or pd.api.types.is_string_dtype(df[col])):
            return
        lowered = df[col].dropna().astype(str).str.strip().str.lower()
        if lowered.empty:
            return

        builtin = set(SUPPRESSION_TOKEN_CANDIDATES) | set(
            self.extra_suppression_tokens
        )
        declared: set = set()
        if profile is not None:
            declared = {
                t.strip().lower() for t in (profile.suppression_tokens or [])
            }

        present_builtin = set(lowered.unique()) & builtin
        present_declared = set(lowered.unique()) & declared
        token_rows = int(lowered.isin(present_builtin | present_declared).sum())
        total = int(len(lowered))
        if total == 0 or not (present_builtin or present_declared):
            return

        # Built-in candidates need a minimum presence, but must NOT dominate
        # the column. A token that already occupies a large share of a
        # low-cardinality column is almost always a legitimate category
        # code (e.g. Embarked='S'), not a suppression marker.
        share = token_rows / max(total, 1)
        builtin_share_ok = (
            not present_builtin
            or (0.02 <= share <= 0.35)
        )
        if not builtin_share_ok and not present_declared:
            return
        all_tokens = sorted(present_builtin | present_declared)
        suppressed_rows = lowered.index[
            lowered.isin(present_builtin | present_declared)
        ].tolist()
        evidence.append(Evidence(
            detector=self.name,
            problem_type=self.problem_type,
            column=str(col),
            method="suppression_token_classification",
            affected_count=token_rows,
            affected_row_indices=_sample_indices(suppressed_rows),
            statistics={
                "token_rows": token_rows,
                "total_non_null_rows": total,
                "builtin_tokens_found": sorted(present_builtin),
                "declared_tokens_found": sorted(present_declared),
                "semantic_type": semantic,
                "constant": bool(profile.constant) if profile else False,
            },
            confidence=0.95 if present_declared else 0.80,
            severity="medium",
            explanation=(
                f"'{col}' contains suppression-style token(s) "
                f"{all_tokens} ({token_rows}/{total} rows); preserved "
                "as semantic values."
            ),
        ))

    @staticmethod
    def _severity(ratio: float) -> str:
        if ratio >= 0.5:
            return "high"
        if ratio >= 0.05:
            return "medium"
        return "low"