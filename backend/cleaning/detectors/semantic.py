"""Semantic anomaly and unit inconsistency detectors for the DataWise Cleaning Engine."""
from typing import Dict, List, Optional
import re

import numpy as np
import pandas as pd

from backend.cleaning.contracts import (
    COMPONENT_MUTUAL_CORR_FLOOR,
    SEMANTIC_MIN_ROWS,
    SEMANTIC_NO_RELATIONSHIP_RHO,
    UNIT_MODE_GAP_ORDERS,
    UNIT_MODE_MIN_PER_MODE,
    UNIT_MODE_MIN_SHARE,
)
from backend.core.constants import (
    AGGREGATE_SUFFIXES,
)
from backend.cleaning.detectors.base import (
    BaseDetector,
    Evidence,
    ColumnProfile,
    InspectionResult,
    _sample_indices,
    _finite_or_none,
)


class SemanticAnomalyDetector(BaseDetector):
    """Flags aggregates that behave inconsistently with the components their
    name implies they summarize (e.g. engagement_score unrelated to every
    engagement_* component). A semantic anomaly is NOT a confirmed error:
    findings are always FLAG-only."""

    name = "SemanticAnomalyDetector"
    problem_type = "semantic_anomaly"

    def __init__(self, max_corr_rows: Optional[int] = None):
        # Scale guard (Phase 9): correlation analysis samples at most this
        # many rows (deterministic head sample).
        self.max_corr_rows = max_corr_rows

    def detect(self, df, profiles, inspection) -> List[Evidence]:
        evidence: List[Evidence] = []
        if inspection.rows < SEMANTIC_MIN_ROWS:
            return evidence
        numeric_info = {}
        for col in df.select_dtypes(include=[np.number]).columns:
            profile = profiles.get(str(col))
            semantic = profile.semantic_type if profile else "numeric"
            if semantic in ("identifier",):
                continue
            if pd.api.types.is_bool_dtype(df[col]):
                continue
            # Ordered name tokens: aggregates share a PREFIX of their
            # components' names (engagement_score -> engagement_*).
            numeric_info[str(col)] = [
                s for s in re.split(r"[^a-z0-9]+", str(col).lower()) if s
            ]

        aggregate_cols = {}
        for col, tokens in numeric_info.items():
            if len(tokens) < 2:
                continue
            if tokens[-1] in AGGREGATE_SUFFIXES:
                aggregate_cols[col] = tuple(tokens[:-1])

        for agg, prefix in aggregate_cols.items():
            components = [
                c for c, tokens in numeric_info.items()
                if c != agg and len(tokens) > len(prefix)
                and tuple(tokens[:len(prefix)]) == prefix
            ]
            if len(components) < 2:
                continue

            work = df[[agg] + components].apply(pd.to_numeric, errors="coerce")
            if self.max_corr_rows is not None:
                work = work.head(self.max_corr_rows)
            work = work.dropna()
            if len(work) < SEMANTIC_MIN_ROWS:
                continue
            corr = work.corr(method="spearman")

            # Significance-aware disconnection bar: with few rows, |rho| of
            # truly unrelated variables is easily ~0.1+, so the "no
            # relationship" threshold widens with sample size.
            no_relationship_bar = max(
                SEMANTIC_NO_RELATIONSHIP_RHO, 2.0 / np.sqrt(len(work))
            )
            agg_corrs = [abs(float(corr.loc[agg, c])) for c in components]
            if any(np.isnan(v) for v in agg_corrs):
                continue
            if max(agg_corrs) >= no_relationship_bar:
                continue  # aggregate IS related to at least one component

            mutual = []
            for i, ca in enumerate(components):
                for cb in components[i + 1:]:
                    v = corr.loc[ca, cb]
                    if pd.notna(v):
                        mutual.append(abs(float(v)))
            if not mutual or float(np.mean(mutual)) < COMPONENT_MUTUAL_CORR_FLOOR:
                continue  # components unrelated among themselves: no expectation

            evidence.append(Evidence(
                detector=self.name,
                problem_type=self.problem_type,
                column=agg,
                method="aggregate_component_disconnection",
                affected_count=int(len(work)),
                affected_row_indices=[],
                statistics={
                    "components": components,
                    "abs_aggregate_correlations": {
                        c: round(v, 4) for c, v in zip(components, agg_corrs)
                    },
                    "mean_mutual_component_corr": round(float(np.mean(mutual)), 4),
                    "no_relationship_bar": round(no_relationship_bar, 4),
                },
                confidence=0.55,
                severity="medium",
                explanation=(
                    f"'{agg}' shows no monotone relationship with ANY of its "
                    f"name-implied components {components}, although those "
                    "components relate to each other. Suspicious, not proven "
                    "wrong — flagged."
                ),
            ))

        # Repeated-text / template suspicion: a string column (free text OR
        # high-cardinality categorical) where one value covers half the rows
        # suggests synthetic/template data or copy-paste spam. Evidence only.
        for col in df.columns:
            profile = profiles.get(str(col))
            if profile is None or profile.semantic_type not in ("text", "categorical"):
                continue
            if profile.cardinality < 10:
                continue  # small closed category sets legitimately repeat
            strings = df[col].dropna().astype(str)
            if len(strings) < SEMANTIC_MIN_ROWS:
                continue
            top_share = float(strings.str.strip().str.lower().value_counts().iloc[0]
                              / len(strings))
            if top_share < 0.5:
                continue
            evidence.append(Evidence(
                detector=self.name,
                problem_type=self.problem_type,
                column=str(col),
                method="repeated_text_pattern",
                affected_count=int(len(strings)),
                affected_row_indices=[],
                statistics={
                    "dominant_value_share": round(top_share, 4),
                    "cardinality": profile.cardinality,
                    "note": (
                        "Possible template/synthetic content or duplicate "
                        "postings; values preserved."
                    ),
                },
                confidence=round(top_share, 4),
                severity="low",
                explanation=(
                    f"{top_share:.0%} of '{col}' is the same text "
                    f"({profile.cardinality} distinct values) — possible "
                    "template/spam pattern, flagged only."
                ),
            ))
        return evidence


class UnitInconsistencyDetector(BaseDetector):
    """Detects numeric columns whose magnitudes form two sharp clusters
    separated by orders of magnitude (e.g. grams mixed with kilograms).
    Statistical evidence only: which unit is correct cannot be known here."""

    name = "UnitInconsistencyDetector"
    problem_type = "semantic_anomaly"

    def detect(self, df, profiles, inspection) -> List[Evidence]:
        evidence: List[Evidence] = []

        for col in df.select_dtypes(include=[np.number]).columns:
            profile = profiles.get(str(col))
            if profile is not None and profile.semantic_type == "identifier":
                continue
            series = df[col]
            if pd.api.types.is_bool_dtype(series):
                continue
            values = pd.to_numeric(series, errors="coerce").dropna()
            values = values[values > 0]  # magnitude analysis needs positives
            if len(values) < UNIT_MODE_MIN_PER_MODE * 2:
                continue

            log10 = np.log10(values.to_numpy(dtype=float))
            low = log10[log10 < np.median(log10)]
            high = log10[log10 >= np.median(log10)]
            if len(low) < UNIT_MODE_MIN_PER_MODE or len(high) < UNIT_MODE_MIN_PER_MODE:
                continue

            gap_orders = float(high.min() - low.max())
            if gap_orders < UNIT_MODE_GAP_ORDERS:
                continue

            low_share = len(low) / len(log10)
            high_share = len(high) / len(log10)
            if min(low_share, high_share) < UNIT_MODE_MIN_SHARE:
                continue

            evidence.append(Evidence(
                detector=self.name,
                problem_type=self.problem_type,
                column=str(col),
                method="magnitude_bimodality",
                affected_count=int(min(len(low), len(high))),
                affected_row_indices=[],  # neither cluster is "the wrong one"
                statistics={
                    "low_mode_max": _finite_or_none(float(10 ** low.max())),
                    "high_mode_min": _finite_or_none(float(10 ** high.min())),
                    "gap_orders_of_magnitude": round(gap_orders, 3),
                    "low_share": round(low_share, 4),
                    "high_share": round(high_share, 4),
                    "note": (
                        "Possible mixed measurement units; conversion "
                        "direction is unknowable from data alone."
                    ),
                },
                confidence=round(gap_orders / 4.0, 4),
                severity="medium",
                explanation=(
                    f"'{col}' splits into two magnitude clusters separated "
                    f"by ~{gap_orders:.1f} orders of magnitude - possible "
                    "unit mixing, flagged for review."
                ),
            ))
        return evidence