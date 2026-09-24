"""Categorical consistency detectors for the DataWise Cleaning Engine."""
from typing import Dict, List, Any

import pandas as pd

from backend.cleaning.contracts import SEPARATOR_FOLD_DOMINANCE
from backend.cleaning.detectors.base import (
    BaseDetector,
    Evidence,
    ColumnProfile,
    InspectionResult,
    _sample_indices,
    _MAX_AFFECTED_ROW_SAMPLES,
)


class CategoricalConsistencyDetector(BaseDetector):
    """Detects likely-equivalent categorical representations.

    Only deterministic folds are proposed as APPLY candidates: variants that
    become identical after case-folding and whitespace stripping, with the
    canonical spelling chosen deterministically (most frequent, ties broken
    by first appearance). Lookalikes differing beyond case/whitespace
    (e.g. 'NewYork' vs 'New York') are FLAGGED, never merged.

    Identifiers and free-text columns are excluded entirely: merging their
    representations could destroy information.
    """

    name = "CategoricalConsistencyDetector"
    problem_type = "categorical_consistency"
    # Runs AFTER FormattingNormalizationAction trimmed stray whitespace, so
    # fold groups describe the final state.
    rerun_after_actions = True

    def detect(self, df, profiles, inspection) -> List[Evidence]:
        evidence: List[Evidence] = []
        if inspection.rows == 0:
            return evidence

        for col in df.columns:
            profile = profiles.get(str(col))
            if profile is None or profile.semantic_type != "categorical":
                continue
            if profile.is_possible_id:
                continue  # belt & braces: identifiers are never merged
            if profile.constant or profile.cardinality < 2:
                continue

            series = df[col]
            non_null = series.dropna()
            if non_null.empty:
                continue
            raw = non_null.astype(str)
            fold_key = raw.str.strip().str.lower()
            # Similarity key for lookalike detection: case-, whitespace-,
            # hyphen- and underscore-insensitive. Equal similarity keys with
            # DIFFERENT fold keys are flagged, never merged.
            sim_key = raw.str.replace(r"[\s_\-]+", "", regex=True).str.lower()

            proposals: List[Dict[str, Any]] = []
            affected_idx: List[int] = []
            separator_idx: List[int] = []

            # --- deterministic case/spelling folds -----------------------
            for key, label_idx in raw.groupby(fold_key).groups.items():
                group = raw.loc[label_idx]
                variants = sorted(group.unique())
                if len(variants) < 2:
                    continue
                canonical_counts = group.value_counts()
                top = int(canonical_counts.max())
                first_seen = list(dict.fromkeys(group.tolist()))
                canonical_value = next(
                    v for v in first_seen if int(canonical_counts[v]) == top
                )
                case_only = all(v.strip().lower() == key for v in variants)
                variants_to_fix = [v for v in variants if v != canonical_value]
                rows_here = df.index[
                    series.notna() & series.astype(str).isin(variants_to_fix)
                ].tolist()
                affected_idx.extend(rows_here)
                proposals.append({
                    "column": str(col),
                    "fold_key": str(key),
                    "canonical": canonical_value,
                    "variants": variants_to_fix,
                    "all_variants": variants,
                    "kind": "case_fold" if case_only else "lookalike_within_fold",
                    "affected_rows": len(rows_here),
                })

            # --- lookalikes / separator folds across different fold keys --
            # Variants equal after removing [_ - ] and case: if ONE spelling
            # dominates the group (>= SEPARATOR_FOLD_DOMINANCE), mapping the
            # minority spellings to it is a deterministic separator-fold
            # (e.g. 'A_4' -> 'A4'). Otherwise equivalence stays ambiguous.
            separator_proposals: List[Dict[str, Any]] = []
            lookalike_proposals: List[Dict[str, Any]] = []
            separator_rows_total = 0
            for key, label_idx in raw.groupby(sim_key).groups.items():
                group = raw.loc[label_idx]
                distinct_folds = set(fold_key.loc[label_idx])
                if len(distinct_folds) < 2:
                    continue  # already handled by the fold pass above
                variants = sorted(group.unique())
                counts = group.value_counts()
                total_rows = int(len(label_idx))
                top_count = int(counts.max())
                first_seen = list(dict.fromkeys(group.tolist()))
                dominant = next(
                    v for v in first_seen if int(counts[v]) == top_count
                )
                dominance = top_count / max(total_rows, 1)
                if dominance >= SEPARATOR_FOLD_DOMINANCE and len(variants) > 1:
                    variants_to_fix = [v for v in variants if v != dominant]
                    rows_here = df.index[
                        series.notna() & series.astype(str).isin(variants_to_fix)
                    ].tolist()
                    separator_idx.extend(rows_here)
                    separator_proposals.append({
                        "column": str(col),
                        "similarity_key": str(key),
                        "canonical": dominant,
                        "variants": variants_to_fix,
                        "all_variants": variants,
                        "dominance": round(dominance, 4),
                        "kind": "separator_fold",
                        "affected_rows": len(rows_here),
                    })
                else:
                    lookalike_proposals.append({
                        "column": str(col),
                        "similarity_key": str(key),
                        "all_variants": variants,
                        "fold_variants": sorted(distinct_folds),
                        "kind": "lookalike",
                        "affected_rows": total_rows,
                    })

            if proposals:
                case_fold = [p for p in proposals if p["kind"] == "case_fold"]
                within_fold = [p for p in proposals if p["kind"] == "lookalike_within_fold"]

                # FIX: case-fold and separator-fold proposals for the SAME
                # column are merged into ONE Evidence item. Emitting them
                # separately produced two independent 'apply' Decisions for
                # one column, and the per-column mutation budget (default 1)
                # silently withheld the second one — a fully deterministic,
                # safe normalization ended up flagged instead of applied,
                # purely due to emission order.
                deterministic_proposals = case_fold + separator_proposals
                if deterministic_proposals:
                    deterministic_idx = affected_idx + separator_idx
                    if case_fold and separator_proposals:
                        method = "deterministic_categorical_fold"
                        confidence = 0.90  # conservative: weaker signal dominates
                        explanation = (
                            f"{len(case_fold)} case/spelling and "
                            f"{len(separator_proposals)} separator-variant "
                            f"group(s) in '{col}' collapse deterministically "
                            "to canonical forms."
                        )
                    elif case_fold:
                        method = "deterministic_case_fold"
                        confidence = 0.99
                        explanation = (
                            f"{len(case_fold)} case/spelling variant group(s) "
                            f"in '{col}' collapse deterministically to a "
                            "canonical form."
                        )
                    else:
                        method = "deterministic_separator_fold"
                        confidence = 0.90
                        explanation = (
                            f"{len(separator_proposals)} separator-variant "
                            f"group(s) in '{col}' map deterministically to "
                            "their dominant spelling."
                        )
                    evidence.append(self._build_evidence(
                        df, str(col), method, deterministic_proposals,
                        deterministic_idx, confidence=confidence, severity="low",
                        explanation=explanation,
                    ))

                ambiguous_all = within_fold + lookalike_proposals
                if within_fold or (ambiguous_all and not separator_proposals):
                    evidence.append(self._build_evidence(
                        df, str(col), "ambiguous_lookalike_groups",
                        ambiguous_all,
                        [], confidence=0.60, severity="medium",
                        explanation=(
                            f"{len(ambiguous_all)} group(s) in '{col}' differ "
                            "beyond deterministic normalization — "
                            "equivalence is NOT established."
                        ),
                    ))
            elif separator_proposals:
                evidence.append(self._build_evidence(
                    df, str(col), "deterministic_separator_fold",
                    separator_proposals, separator_idx,
                    confidence=0.90, severity="low",
                    explanation=(
                        f"{len(separator_proposals)} separator-variant "
                        f"group(s) in '{col}' map deterministically to their "
                        "dominant spelling (e.g. 'A_4' vs 'A4')."
                    ),
                ))
            elif lookalike_proposals:
                evidence.append(self._build_evidence(
                    df, str(col), "ambiguous_lookalike_groups",
                    lookalike_proposals,
                    [], confidence=0.60, severity="medium",
                    explanation=(
                        f"{len(lookalike_proposals)} group(s) in '{col}' are "
                        "similar after removing punctuation/whitespace but "
                        "no spelling dominates; merging would be a guess."
                    ),
                ))
        return evidence

    @staticmethod
    def _build_evidence(df, column, method, proposals, affected_idx, confidence,
                        severity, explanation) -> Evidence:
        return Evidence(
            detector=CategoricalConsistencyDetector.name,
            problem_type=CategoricalConsistencyDetector.problem_type,
            column=column,
            method=method,
            affected_count=sum(p["affected_rows"] for p in proposals),
            affected_row_indices=_sample_indices(affected_idx),
            statistics={"proposals": proposals},
            confidence=confidence,
            severity=severity,
            explanation=explanation,
        )


class MultiValueCategoryDetector(BaseDetector):
    """Detects categorical columns where individual cells contain multiple
    values separated by a consistent delimiter (e.g. 'Red|Green|Blue').
    Evidence only; splitting changes cardinality dramatically so it is
    FLAG-only by default.
    """

    name = "MultiValueCategoryDetector"
    problem_type = "categorical_consistency"

    _DELIMITERS = [",", ";", "|", "/", "&&"]

    def detect(self, df, profiles, inspection) -> List[Evidence]:
        evidence: List[Evidence] = []
        if inspection.rows == 0:
            return evidence

        import re
        for col in df.columns:
            profile = profiles.get(str(col))
            if profile is None or profile.semantic_type not in ("categorical", "text"):
                continue
            if profile.is_possible_id or profile.constant:
                continue
            if profile.cardinality < 2:
                continue

            series = df[col].dropna().astype(str)
            if series.empty:
                continue

            best_delim = None
            best_rate = 0.0
            for delim in self._DELIMITERS:
                pattern = re.escape(delim)
                contains = series.str.contains(pattern, regex=True, na=False)
                rate = float(contains.mean())
                if rate > best_rate:
                    best_rate = rate
                    best_delim = delim

            if best_rate < 0.10 or best_delim is None:
                continue

            split_counts = series.str.split(best_delim).str.len()
            multi_rate = float((split_counts > 1).mean())
            if multi_rate < 0.10:
                continue

            all_values = set()
            for cell in series.head(100):
                all_values.update(v.strip() for v in str(cell).split(best_delim))
            all_values.discard("")

            evidence.append(Evidence(
                detector=self.name,
                problem_type=self.problem_type,
                column=str(col),
                method="multi_value_delimiter",
                affected_count=int(series.str.contains(re.escape(best_delim), regex=True, na=False).sum()),
                affected_row_indices=[],
                statistics={
                    "delimiter": best_delim,
                    "cells_with_delimiter_share": round(best_rate, 4),
                    "cells_with_multiple_values_share": round(multi_rate, 4),
                    "distinct_atomic_values": len(all_values),
                    "sample_atomic_values": sorted(all_values)[:10],
                },
                confidence=round(min(best_rate, 1.0), 4),
                severity="medium",
                explanation=(
                    f"'{col}' contains {best_rate:.0%} of cells with "
                    f"'{best_delim}'-separated multiple values; "
                    f"splitting would create ~{len(all_values)} atomic categories."
                ),
            ))
        return evidence