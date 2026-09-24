"""Outlier detector for the DataWise Cleaning Engine."""
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from backend.cleaning.detectors.base import (
    BaseDetector,
    Evidence,
    ColumnProfile,
    InspectionResult,
    _sample_indices,
    _finite_or_none,
    _MIN_VALUES_FOR_OUTLIERS,
    _is_ordinal_categorical,
)


class OutlierDetector(BaseDetector):
    """IQR-based outlier evidence on eligible numeric columns.

    Statistical unusualness is NOT proof of an error: this detector reports
    candidates; the Decision Engine keeps outlier handling flag-only unless a
    caller explicitly enables a destructive policy.
    """

    name = "OutlierDetector"
    problem_type = "outliers"
    rerun_after_actions = True

    def __init__(self, threshold: float = 1.5):
        self.threshold = float(threshold)

    # ------------------------------------------------------------------
    # Helper — skip columns that are naturally bounded (ratings,
    # probabilities, grades, etc.) where IQR produces false positives.
    # ------------------------------------------------------------------
    @staticmethod
    def _is_semantically_bounded(profile: Optional[ColumnProfile], series: pd.Series) -> bool:
        """Return True when the column is a bounded domain where IQR is
        inappropriate (e.g. 0-5 star ratings, 0-1 probabilities)."""
        if profile is None:
            return False

        # Explicit tight bounds from caller-declared rules
        if profile.valid_min is not None and profile.valid_max is not None:
            if (profile.valid_max - profile.valid_min) <= 10:
                return True

        # Name-based heuristic for bounded scales
        name_lower = str(profile.name).lower()
        bounded_keywords = {
            "rating", "score", "grade", "level", "tier", "rank",
            "class", "pclass", "star", "probability", "pct", "percent",
            "completion", "satisfaction", "likert", "sentiment",
            "confidence", "education",
        }
        if any(kw in name_lower for kw in bounded_keywords):
            non_null = pd.to_numeric(series, errors="coerce").dropna()
            if len(non_null) and (non_null.max() - non_null.min()) <= 10:
                return True
        return False

    # ------------------------------------------------------------------
    # Helper — mask of values that violate explicit semantic bounds.
    # These should be reported by InvalidValueDetector, not here.
    # ------------------------------------------------------------------
    @staticmethod
    def _semantic_invalid_mask(values: pd.Series, profile: ColumnProfile):
        """Return a boolean mask of values outside valid_min/valid_max."""
        if profile.valid_min is None and profile.valid_max is None:
            return None
        invalid = pd.Series(False, index=values.index)
        if profile.valid_min is not None:
            invalid |= values < profile.valid_min
        if profile.valid_max is not None:
            invalid |= values > profile.valid_max
        return invalid.fillna(False)

    def detect(self, df, profiles, inspection) -> List[Evidence]:
        evidence: List[Evidence] = []

        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        for col in numeric_cols:
            profile = profiles.get(str(col))
            series = df[col]

            if pd.api.types.is_bool_dtype(series):
                continue
            if profile is not None:
                if profile.semantic_type == "identifier":
                    continue
                if profile.semantic_type == "numeric" and profile.constant:
                    continue
                # NEW: skip bounded / ordinal scales (0-5 ratings, etc.)
                if self._is_semantically_bounded(profile, series):
                    continue
            if _is_ordinal_categorical(series, col):
                continue

            values = pd.to_numeric(series, errors="coerce")
            non_null = values.dropna()
            if len(non_null) < _MIN_VALUES_FOR_OUTLIERS or non_null.nunique() <= 2:
                continue

            # Small integer / ordinal encodings (education_num 1-16, ratings)
            # are not IQR-outlier domains.
            nunique = int(non_null.nunique())
            vmin, vmax = float(non_null.min()), float(non_null.max())
            if (
                nunique <= 20
                and (vmax - vmin) <= 30
                and abs(nunique - (vmax - vmin + 1)) <= 2
            ):
                continue

            q1 = non_null.quantile(0.25)
            q3 = non_null.quantile(0.75)
            iqr = q3 - q1
            if not np.isfinite(iqr) or iqr == 0:
                continue

            lower = q1 - self.threshold * iqr
            upper = q3 + self.threshold * iqr
            mask = (values < lower) | (values > upper)
            mask = mask.fillna(False)

            # NEW: strip semantically-invalid values from the outlier mask
            # (e.g. Age=200 is invalid, not merely an outlier)
            if profile is not None:
                semantic_invalid = self._semantic_invalid_mask(values, profile)
                if semantic_invalid is not None:
                    mask = mask & ~semantic_invalid

            count = int(mask.sum())
            if count == 0:
                continue
            # IQR fences that flag a huge slice of the column (e.g. hours_per_week
            # peaked at 40) are distribution shape, not outliers.
            if count / max(len(non_null), 1) > 0.20:
                continue

            outlier_values = values[mask]

            # NEW: confidence based on extremity (how far beyond the fence)
            if count > 0 and np.isfinite(iqr) and iqr > 0:
                distances = np.maximum(
                    (lower - outlier_values).fillna(0),
                    (outlier_values - upper).fillna(0)
                )
                max_distance = float(distances.max()) if len(distances) else 0
                # 1 IQR beyond fence → 0.5, 3 IQRs → 1.0
                confidence = min(1.0, 0.5 + (max_distance / iqr) * 0.25)
            else:
                confidence = 0.5

            # Robust MAD cross-check
            median = float(non_null.median())
            mad = float((non_null - median).abs().median())
            mad_extreme_share = None
            if np.isfinite(mad) and mad > 0:
                mad_mask = (values - median).abs() > 3.5 * 1.4826 * mad
                mad_extreme_share = round(
                    float(mask.fillna(False)[mad_mask.fillna(False)].mean()
                          ) if int(mad_mask.sum()) else 0.0, 4)

            evidence.append(
                Evidence(
                    detector=self.name,
                    problem_type=self.problem_type,
                    column=str(col),
                    method="IQR",
                    affected_count=count,
                    affected_row_indices=_sample_indices(
                        df.index[mask].tolist()
                    ),
                    statistics={
                        "lower_bound": float(lower),
                        "upper_bound": float(upper),
                        "q1": float(q1),
                        "q3": float(q3),
                        "iqr": float(iqr),
                        "threshold_multiplier": self.threshold,
                        "percentage": round(float(mask.mean() * 100), 4),
                        "min_outlier_value": _finite_or_none(outlier_values.min()),
                        "max_outlier_value": _finite_or_none(outlier_values.max()),
                        "mad_extreme_share": mad_extreme_share,
                    },
                    confidence=round(confidence, 4),
                    severity=self._severity(count, inspection.rows),
                    explanation=(
                        f"{count} value(s) in '{col}' fall outside the IQR fence "
                        f"[{lower:.4g}, {upper:.4g}]. Unusual is not invalid."
                    ),
                )
            )
        return evidence

    @staticmethod
    def _severity(count: int, total_rows: int) -> str:
        pct = count / max(total_rows, 1) * 100
        if pct >= 10:
            return "high"
        if pct >= 1:
            return "medium"
        return "low"