"""Missingness pattern detector for the DataWise Cleaning Engine."""
from typing import Dict, List

import numpy as np
import pandas as pd

from backend.cleaning.contracts import (
    CO_MISSING_LIFT,
    CO_MISSING_MIN_SUPPORT,
    MISSINGNESS_GROUP_SUPPORT,
    MISSINGNESS_RATE_GAP,
)
from backend.cleaning.detectors.base import (
    BaseDetector,
    Evidence,
    ColumnProfile,
    InspectionResult,
    _sample_indices,
    _jsonable,
)


class MissingnessPatternDetector(BaseDetector):
    """Goes beyond per-column counts: reports missingness that concentrates
    inside specific categories of other columns and systematic co-missingness
    blocks. Purely evidential — never triggers imputation by correlation."""

    name = "MissingnessPatternDetector"
    problem_type = "missingness_pattern"

    def detect(self, df, profiles, inspection) -> List[Evidence]:
        evidence: List[Evidence] = []
        if inspection.rows == 0:
            return evidence

        rows = inspection.rows
        missing_cols = [str(c) for c in df.columns if int(df[c].isna().sum()) > 0]
        cat_cols = [
            str(c) for c in df.columns
            if profiles.get(str(c)) is not None
            and profiles[str(c)].semantic_type in ("categorical", "boolean")
            and 1 < profiles[str(c)].cardinality <= 20
        ]

        # Category-dependent missingness
        findings_count = 0
        for mc in missing_cols:
            if findings_count >= 10:
                break
            miss = df[mc].isna()
            overall_rate = float(miss.mean())
            for gc in cat_cols:
                if gc == mc:
                    continue
                groups = df[gc]
                for value, sub in groups.groupby(groups):
                    support = int(len(sub))
                    if support < MISSINGNESS_GROUP_SUPPORT:
                        continue
                    rate = float(miss.loc[sub.index].mean())
                    gap = abs(rate - overall_rate)
                    # Concentration = large absolute deviation from the
                    # column's overall missing rate (group support already
                    # guards against noise).
                    if gap < MISSINGNESS_RATE_GAP:
                        continue
                    idx = sub.index[miss.loc[sub.index].to_numpy(dtype=bool)].tolist()
                    evidence.append(Evidence(
                        detector=self.name,
                        problem_type=self.problem_type,
                        column=mc,
                        method="category_dependent_missingness",
                        affected_count=len(idx),
                        affected_row_indices=_sample_indices(idx),
                        statistics={
                            "conditioning_column": gc,
                            "category_value": _jsonable(value),
                            "group_support": support,
                            "group_missing_rate": round(rate, 4),
                            "overall_missing_rate": round(overall_rate, 4),
                        },
                        confidence=round(min(gap / max(overall_rate, 1e-9), 1.0), 4),
                        severity="medium",
                        explanation=(
                            f"Missingness in '{mc}' concentrates in "
                            f"'{gc}'=={value!r}: {rate:.0%} vs {overall_rate:.0%} "
                            "overall. Systematic, not random — flagged."
                        ),
                    ))
                    findings_count += 1
                    if findings_count >= 10:
                        break

        # Co-missingness blocks (joint missing far above independence)
        pair_budget = 5
        for i, a in enumerate(missing_cols):
            for b in missing_cols[i + 1:]:
                if pair_budget <= 0:
                    break
                ma, mb = df[a].isna(), df[b].isna()
                joint = int((ma & mb).sum())
                expected = float(ma.mean() * mb.mean() * rows)
                if joint < CO_MISSING_MIN_SUPPORT or expected <= 0:
                    continue
                lift = joint / expected
                if lift < CO_MISSING_LIFT:
                    continue
                evidence.append(Evidence(
                    detector=self.name,
                    problem_type=self.problem_type,
                    column=None,
                    method="co_missingness_block",
                    affected_count=joint,
                    affected_row_indices=_sample_indices(
                        df.index[ma & mb].tolist()
                    ),
                    statistics={
                        "columns": [a, b],
                        "joint_missing_rows": joint,
                        "expected_if_independent": round(expected, 2),
                        "lift": round(lift, 3),
                    },
                    confidence=round(min(lift / (CO_MISSING_LIFT * 2), 1.0), 4),
                    severity="medium",
                    explanation=(
                        f"'{a}' and '{b}' go missing together {joint} times "
                        f"(lift {lift:.1f}x over independence) — systematic "
                        "pattern worth review."
                    ),
                ))
                pair_budget -= 1
        return evidence