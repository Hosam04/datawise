"""Constraint and temporal sanity detectors for the DataWise Cleaning Engine."""
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from backend.cleaning.contracts import (
    TEMPORAL_FUTURE_TOLERANCE_DAYS,
    TEMPORAL_MIN_YEAR,
)
from backend.core.constants import (
    AGE_KEYWORDS,
    CONSTRAINT_PAIR_VOCAB,
    COUNT_KEYWORDS,
    PLAUSIBILITY_AGE_MIN,
    PLAUSIBILITY_COUNT_HIGH,
)
from backend.cleaning.detectors.base import (
    BaseDetector,
    Evidence,
    ColumnProfile,
    InspectionResult,
    _sample_indices,
    _name_segments,
    _name_has_keyword,
    AGE_KEYWORDS,
    COUNT_KEYWORDS,
)


class ConstraintDetector(BaseDetector):
    """Cross-column logical constraints from ordered name vocabulary
    (start<=end, min<=max, ...). Violations are REPORTED, never repaired:
    which side of the pair is wrong cannot be determined deterministically."""

    name = "ConstraintDetector"
    problem_type = "constraint_violation"

    def __init__(self, extra_pairs: Optional[List[Tuple[str, str]]] = None):
        # Caller-declared ordered pairs (left_word, right_word) meaning
        # left <= right, from explicit dataset metadata.
        self.extra_pairs = [(str(a).lower(), str(b).lower())
                            for a, b in (extra_pairs or [])]

    def detect(self, df, profiles, inspection) -> List[Evidence]:
        evidence: List[Evidence] = []
        if inspection.rows == 0:
            return evidence

        segment_map = {str(c): _name_segments(c) for c in df.columns}
        dtype_map = {str(c): df[c] for c in df.columns}

        def comparable(series) -> Optional[str]:
            if pd.api.types.is_bool_dtype(series):
                return None
            if pd.api.types.is_numeric_dtype(series):
                return "numeric"
            if pd.api.types.is_datetime64_any_dtype(series):
                return "datetime"
            return None

        seen_pairs = set()
        pair_vocabulary = list(CONSTRAINT_PAIR_VOCAB) + [
            (a, b) for a, b in self.extra_pairs if (a, b) not in CONSTRAINT_PAIR_VOCAB
        ]
        for left_word, right_word in pair_vocabulary:
            left_cols = [
                c for c, segs in segment_map.items()
                if left_word in segs and comparable(dtype_map[c]) is not None
                and (profiles.get(c) is None or profiles[c].semantic_type != "identifier")
            ]
            right_cols = [
                c for c, segs in segment_map.items()
                if right_word in segs and c not in left_cols
                and comparable(dtype_map[c]) is not None
                and (profiles.get(c) is None or profiles[c].semantic_type != "identifier")
            ]
            for lc in left_cols:
                for rc in right_cols:
                    if comparable(dtype_map[lc]) != comparable(dtype_map[rc]):
                        continue
                    pair_key = (lc, rc)
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    if comparable(dtype_map[lc]) == "numeric":
                        lv = pd.to_numeric(dtype_map[lc], errors="coerce")
                        rv = pd.to_numeric(dtype_map[rc], errors="coerce")
                    else:
                        lv = pd.to_datetime(dtype_map[lc], errors="coerce")
                        rv = pd.to_datetime(dtype_map[rc], errors="coerce")

                    mask = lv.notna() & rv.notna() & (lv > rv)
                    count = int(mask.sum())
                    if count == 0:
                        continue
                    evidence.append(Evidence(
                        detector=self.name,
                        problem_type=self.problem_type,
                        column=f"{lc} > {rc}",
                        method="ordered_pair_violation",
                        affected_count=count,
                        affected_row_indices=_sample_indices(df.index[mask].tolist()),
                        statistics={
                            "left_column": lc,
                            "right_column": rc,
                            "expected_relationship": f"{lc} <= {rc}",
                            "actual_relationship": f"{lc} > {rc}",
                            "violation_share": round(count / max(inspection.rows, 1), 6),
                        },
                        confidence=1.0,
                        severity="high" if count > inspection.rows * 0.02 else "medium",
                        explanation=(
                            f"{count} row(s) violate '{lc} <= {rc}' "
                            f"({count}/{inspection.rows}). Repair direction is "
                            "ambiguous — flagged, not modified."
                        ),
                    ))

        # Soft plausibility rule: an age-like value below PLAUSIBILITY_AGE_MIN
        # combined with a count-like value >= PLAUSIBILITY_COUNT_HIGH is
        # SUSPICIOUS (e.g. very young parent with many children) — never
        # automatically invalid.
        age_cols = [
            c for c, segs in segment_map.items()
            if any(_name_has_keyword(segs, kw) for kw in AGE_KEYWORDS)
            and comparable(dtype_map[c]) == "numeric"
            and (profiles.get(c) is None or profiles[c].semantic_type != "identifier")
        ]
        count_cols = [
            c for c, segs in segment_map.items()
            if any(_name_has_keyword(segs, kw) for kw in COUNT_KEYWORDS)
            and comparable(dtype_map[c]) == "numeric"
            and (profiles.get(c) is None or profiles[c].semantic_type != "identifier")
        ]
        for ac in age_cols:
            for cc in count_cols:
                age_vals = pd.to_numeric(dtype_map[ac], errors="coerce")
                count_vals = pd.to_numeric(dtype_map[cc], errors="coerce")
                mask = (
                    age_vals.notna() & count_vals.notna()
                    & (age_vals < PLAUSIBILITY_AGE_MIN)
                    & (count_vals >= PLAUSIBILITY_COUNT_HIGH)
                )
                count = int(mask.sum())
                if count == 0:
                    continue
                evidence.append(Evidence(
                    detector=self.name,
                    problem_type=self.problem_type,
                    column=f"{ac} x {cc}",
                    method="age_count_plausibility",
                    affected_count=count,
                    affected_row_indices=_sample_indices(df.index[mask].tolist()),
                    statistics={
                        "age_column": ac,
                        "count_column": cc,
                        "age_threshold": PLAUSIBILITY_AGE_MIN,
                        "count_threshold": PLAUSIBILITY_COUNT_HIGH,
                        "note": "Rare but possible; suspicious, not invalid.",
                    },
                    confidence=0.5,
                    severity="low",
                    explanation=(
                        f"{count} row(s) combine {ac} < {PLAUSIBILITY_AGE_MIN} "
                        f"with {cc} >= {PLAUSIBILITY_COUNT_HIGH}. Rare but "
                        "possible — flagged, values preserved."
                    ),
                ))
        return evidence


class TemporalSanityDetector(BaseDetector):
    """Flags datetime columns containing implausible timestamps: dates too
    far in the future or before TEMPORAL_MIN_YEAR. Values are never altered;
    'future' may be legitimate (scheduled events) so this is FLAG-only."""

    name = "TemporalSanityDetector"
    problem_type = "constraint_violation"

    def detect(self, df, profiles, inspection) -> List[Evidence]:
        evidence: List[Evidence] = []
        now = pd.Timestamp.now(tz=None)

        for col in df.columns:
            series = df[col]
            if not pd.api.types.is_datetime64_any_dtype(series):
                continue
            values = pd.to_datetime(series, errors="coerce").dropna()
            if values.empty:
                continue

            future_cut = now + pd.Timedelta(days=TEMPORAL_FUTURE_TOLERANCE_DAYS)
            past_cut = pd.Timestamp(f"{TEMPORAL_MIN_YEAR}-01-01")

            future_mask = values > future_cut
            past_mask = values < past_cut
            future_n = int(future_mask.sum())
            past_n = int(past_mask.sum())
            if future_n == 0 and past_n == 0:
                continue

            offending = values[future_mask | past_mask]
            evidence.append(Evidence(
                detector=self.name,
                problem_type=self.problem_type,
                column=str(col),
                method="temporal_bounds",
                affected_count=int(len(offending)),
                affected_row_indices=_sample_indices(
                    df.index[series.notna()
                             & series.isin(list(offending))].tolist()
                ),
                statistics={
                    "future_count": future_n,
                    "past_count": past_n,
                    "min_observed": str(values.min()),
                    "max_observed": str(values.max()),
                    "future_cutoff": str(future_cut),
                    "past_cutoff": str(past_cut),
                },
                confidence=1.0,
                severity="medium",
                explanation=(
                    f"'{col}' holds {future_n} future and/or {past_n} "
                    f"pre-{TEMPORAL_MIN_YEAR} timestamp(s) outside plausible "
                    "bounds; values preserved for review."
                ),
            ))
        return evidence