"""Type and value consistency detectors for the DataWise Cleaning Engine."""
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from backend.cleaning.contracts import (
    AGE_MAX_PLAUSIBLE,
    TYPE_ANOMALY_MIN_CONFLICTS,
    TYPE_DOMINANCE_RATIO,
)
from backend.core.constants import (
    AGE_KEYWORDS,
    PERCENTAGE_KEYWORDS,
    PROBABILITY_KEYWORDS,
    COUNT_KEYWORDS,
    PRICE_KEYWORDS,
)
from backend.cleaning.detectors.base import (
    BaseDetector,
    Evidence,
    ColumnProfile,
    InspectionResult,
    _sample_indices,
    _finite_or_none,
    _MAX_EXAMPLES,
    _MAX_AFFECTED_ROW_SAMPLES,
    _name_segments,
    _name_has_keyword,
    AGE_KEYWORDS,
    _is_string_like,
)


class InvalidValueDetector(BaseDetector):
    """Detects OBJECTIVELY invalid values against explicit semantic ranges.

    Rules fire only when the column NAME carries the corresponding keyword
    (e.g. 'age', 'completion_pct'). Statistical rarity alone never fires a
    rule here: age=89 or fare=512 are legitimate observations.
    """

    name = "InvalidValueDetector"
    problem_type = "invalid_values"

    def _rules_for(self, name: str) -> List[Tuple[str, Optional[float], Optional[float]]]:
        segments = _name_segments(name)
        rules: List[Tuple[str, Optional[float], Optional[float]]] = []
        if any(_name_has_keyword(segments, kw) for kw in AGE_KEYWORDS):
            rules.append(("age_range", 0.0, float(AGE_MAX_PLAUSIBLE)))
        if any(_name_has_keyword(segments, kw) for kw in PERCENTAGE_KEYWORDS):
            rules.append(("percentage_range", 0.0, 100.0))
        if any(_name_has_keyword(segments, kw) for kw in PROBABILITY_KEYWORDS):
            rules.append(("probability_range", 0.0, 1.0))
        if any(_name_has_keyword(segments, kw) for kw in COUNT_KEYWORDS):
            rules.append(("non_negative_count", 0.0, None))
        if any(_name_has_keyword(segments, kw) for kw in PRICE_KEYWORDS):
            rules.append(("non_negative_price", 0.0, None))

        lat_keywords = {"lat", "latitude"}
        lon_keywords = {"lon", "lng", "longitude"}
        if any(_name_has_keyword(segments, kw) for kw in lat_keywords):
            rules.append(("latitude_range", -90.0, 90.0))
        if any(_name_has_keyword(segments, kw) for kw in lon_keywords):
            rules.append(("longitude_range", -180.0, 180.0))

        return rules

    def detect(self, df, profiles, inspection) -> List[Evidence]:
        evidence: List[Evidence] = []
        if inspection.rows == 0:
            return evidence

        for col in df.select_dtypes(include=[np.number]).columns:
            profile = profiles.get(str(col))
            if profile is not None and profile.semantic_type == "identifier":
                continue
            series = df[col]
            if pd.api.types.is_bool_dtype(series):
                continue
            for rule_name, minimum, maximum in self._rules_for(str(col)):
                values = pd.to_numeric(series, errors="coerce")
                violates = pd.Series(False, index=values.index)
                if minimum is not None:
                    violates |= values < minimum
                if maximum is not None:
                    violates |= values > maximum
                mask = values.notna() & violates
                count = int(mask.sum())
                if count == 0:
                    continue
                offending = values[mask]
                evidence.append(
                    Evidence(
                        detector=self.name,
                        problem_type=self.problem_type,
                        column=str(col),
                        method=rule_name,
                        affected_count=count,
                        affected_row_indices=_sample_indices(df.index[mask].tolist()),
                        statistics={
                            "rule": rule_name,
                            "min_allowed": minimum,
                            "max_allowed": maximum,
                            "min_offending": _finite_or_none(offending.min()),
                            "max_offending": _finite_or_none(offending.max()),
                            "examples": [
                                _finite_or_none(v) for v in offending.head(_MAX_EXAMPLES)
                            ],
                        },
                        confidence=1.0,
                        severity="medium" if count <= inspection.rows * 0.05 else "high",
                        explanation=(
                            f"{count} value(s) in '{col}' violate the explicit "
                            f"{rule_name} rule [{minimum}, {maximum}]."
                        ),
                    )
                )

            # Explicit metadata: caller-declared bounds on numeric columns.
            if profile is None:
                continue
            values = pd.to_numeric(series, errors="coerce")
            explicit_min = profile.valid_min
            explicit_max = profile.valid_max
            if explicit_min is not None or explicit_max is not None:
                violates = pd.Series(False, index=values.index)
                if explicit_min is not None:
                    violates |= values < explicit_min
                if explicit_max is not None:
                    violates |= values > explicit_max
                mask = values.notna() & violates
                count = int(mask.sum())
                if count:
                    offending = values[mask]
                    evidence.append(Evidence(
                        detector=self.name,
                        problem_type=self.problem_type,
                        column=str(col),
                        method="explicit_range",
                        affected_count=count,
                        affected_row_indices=_sample_indices(df.index[mask].tolist()),
                        statistics={
                            "rule": "explicit_range",
                            "min_allowed": explicit_min,
                            "max_allowed": explicit_max,
                            "examples": [
                                _finite_or_none(v)
                                for v in offending.head(_MAX_EXAMPLES)
                            ],
                        },
                        confidence=1.0,
                        severity="medium" if count <= inspection.rows * 0.05 else "high",
                        explanation=(
                            f"{count} value(s) in '{col}' violate the "
                            f"caller-declared range "
                            f"[{explicit_min}, {explicit_max}]."
                        ),
                    ))

            allowed_ev = self._allowed_values_evidence(
                df, str(col), series, profile, inspection)
            if allowed_ev is not None:
                evidence.append(allowed_ev)

        # Explicit closed domains also apply to NON-numeric columns
        # (categorical/text/boolean-like), which the numeric loop skips.
        numeric_cols_seen = set(df.select_dtypes(include=[np.number]).columns)
        for col in df.columns:
            if col in numeric_cols_seen:
                continue
            profile = profiles.get(str(col))
            if profile is None or profile.semantic_type == "identifier":
                continue
            series = df[col]
            if pd.api.types.is_bool_dtype(series):
                continue
            allowed_ev = self._allowed_values_evidence(
                df, str(col), series, profile, inspection)
            if allowed_ev is not None:
                evidence.append(allowed_ev)
        return evidence

    def _allowed_values_evidence(self, df, col_name, series, profile, inspection):
        """Evidence for values outside a caller-declared closed domain."""
        allowed = getattr(profile, "allowed_values", None)
        if not allowed:
            return None
        allowed_set = {str(v) for v in allowed}
        strings = series.dropna().astype(str)
        outside = ~strings.isin(allowed_set)
        count = int(outside.sum())
        if count == 0:
            return None
        examples = [str(v)[:60] for v in strings[outside].head(_MAX_EXAMPLES)]
        return Evidence(
            detector=self.name,
            problem_type=self.problem_type,
            column=col_name,
            method="explicit_allowed_values",
            affected_count=count,
            affected_row_indices=_sample_indices(
                df.index[df[col_name].notna()
                         & df[col_name].astype(str).isin(set(strings[outside]))].tolist()
            ),
            statistics={
                "rule": "explicit_allowed_values",
                "allowed_values": sorted(allowed_set),
                "examples": examples,
            },
            confidence=1.0,
            severity="low" if count <= inspection.rows * 0.02 else "medium",
            explanation=(
                f"{count} value(s) in '{col_name}' are outside the "
                "caller-declared domain; flagged, never rewritten."
            ),
        )


class TypeAnomalyDetector(BaseDetector):
    """Detects values that conflict with the inferred class of their column
    (e.g. stray text inside a numeric-looking column). Never casts anything:
    ambiguous values are reported for review."""

    name = "TypeAnomalyDetector"
    problem_type = "type_anomaly"

    def detect(self, df, profiles, inspection) -> List[Evidence]:
        evidence: List[Evidence] = []
        if inspection.rows == 0:
            return evidence

        for col in df.columns:
            profile = profiles.get(str(col))
            if profile is None or profile.semantic_type not in ("categorical", "text"):
                continue
            if profile.constant:
                continue
            series = df[col].dropna()
            if series.empty:
                continue
            strings = series.astype(str)
            from backend.cleaning.inspection import classify_scalar as _classify_scalar
            classes = strings.map(_classify_scalar)
            counts = classes.value_counts()

            # --- lossless formatted numeric-string candidacy -------------
            # Currency/accounting separators are representational noise only
            # when EVERY non-null value parses after the deterministic
            # normalization. This is evidence, not a blind cast.
            def _normalized_numeric(text):
                value = str(text).strip()
                value = re.sub(r"[\$€£¥,%]", "", value)
                value = re.sub(r"^\((.*)\)$", r"-\1", value)
                value = value.replace(",", "")
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None

            import re
            normalized_numeric = strings.map(_normalized_numeric)
            if (
                len(normalized_numeric) > 0
                and normalized_numeric.notna().all()
                and any(re.search(r"[\$€£¥,%]|^\(.*\)$", str(v).strip()) for v in strings)
                and profile.semantic_type != "identifier"
                and not profile.is_possible_id
            ):
                evidence.append(Evidence(
                    detector=self.name,
                    problem_type=self.problem_type,
                    column=str(col),
                    method="lossless_formatted_numeric_string",
                    affected_count=int(len(strings)),
                    affected_row_indices=[],
                    statistics={
                        "kind": "lossless_formatted_numeric_string_candidate",
                        "parse_share": 1.0,
                        "normalization": "remove_currency_separators_and_accounting_parentheses",
                        "sample_values": [str(v) for v in strings.head(_MAX_EXAMPLES)],
                    },
                    confidence=1.0,
                    severity="low",
                    explanation=(
                        f"'{col}' stores numeric values using deterministic "
                        "currency/separator formatting; normalization is lossless."
                    ),
                ))
                continue

            # --- lossless numeric-string candidacy ------------------------
            # A string column whose EVERY non-null value parses as a number,
            # which is NOT an identifier and carries no other class, can be
            # converted with zero information loss. Anything less is a
            # FLAG-only anomaly (casting would destroy the stragglers).
            if (
                len(counts) >= 1
                and counts.index[0] == "numeric"
                and float(counts.iloc[0]) == len(strings)
                and profile.semantic_type != "identifier"
                and not profile.is_possible_id
            ):
                evidence.append(Evidence(
                    detector=self.name,
                    problem_type=self.problem_type,
                    column=str(col),
                    method="lossless_numeric_string",
                    affected_count=int(len(strings)),
                    affected_row_indices=[],
                    statistics={
                        "kind": "lossless_numeric_string_candidate",
                        "parse_share": 1.0,
                        "sample_values": [str(v) for v in strings.head(_MAX_EXAMPLES)],
                    },
                    confidence=1.0,
                    severity="low",
                    explanation=(
                        f"'{col}' stores numeric values as strings; every "
                        "value parses, so conversion loses nothing."
                    ),
                ))
                continue  # a fully-numeric column has no class conflicts

            # --- lossless date-string candidacy -----------------------------
            if (
                profile.semantic_type in ("categorical", "text")
                and not profile.is_possible_id
                and not profile.constant
            ):
                strings = series.dropna().astype(str).str.strip()
                # Avoid short numeric strings mis-parsed as dates (e.g. "2020" -> 2020-01-01)
                if strings.str.len().mean() >= 6:
                    parsed = pd.to_datetime(strings, errors="coerce", format="mixed")
                    parse_rate = float(parsed.notna().sum() / len(strings)) if len(strings) else 0.0
                    if parse_rate >= 0.95:
                        # Ensure real date separators exist to avoid pure integers
                        has_separators = strings.str.contains(r'[-/\.: ]').mean() >= 0.3
                        if has_separators:
                            evidence.append(Evidence(
                                detector=self.name,
                                problem_type=self.problem_type,
                                column=str(col),
                                method="lossless_date_string",
                                affected_count=int(len(strings)),
                                affected_row_indices=[],
                                statistics={
                                    "kind": "lossless_date_string_candidate",
                                    "parse_share": round(parse_rate, 4),
                                    "sample_values": [str(v) for v in strings.head(_MAX_EXAMPLES)],
                                },
                                confidence=1.0,
                                severity="low",
                                explanation=(
                                    f"'{col}' stores date values as strings; "
                                    f"{parse_rate:.0%} parse cleanly, so conversion loses nothing."
                                ),
                            ))
                            continue

            # --- coordinate-string candidacy --------------------------------
            if (
                profile.semantic_type in ("categorical", "text")
                and not profile.is_possible_id
                and profile.semantic_subtype == "geo_coordinate"
            ):
                strings = series.dropna().astype(str).str.strip()
                numeric_parsed = pd.to_numeric(strings, errors="coerce")
                parse_rate = float(numeric_parsed.notna().sum() / len(strings)) if len(strings) else 0.0
                if parse_rate >= 0.95:
                    evidence.append(Evidence(
                        detector=self.name,
                        problem_type=self.problem_type,
                        column=str(col),
                        method="lossless_coordinate_string",
                        affected_count=int(len(strings)),
                        affected_row_indices=[],
                        statistics={
                            "kind": "lossless_coordinate_string_candidate",
                            "parse_share": round(parse_rate, 4),
                            "sample_values": [str(v) for v in strings.head(_MAX_EXAMPLES)],
                        },
                        confidence=1.0,
                        severity="low",
                        explanation=(
                            f"'{col}' stores geographic coordinates as strings; "
                            f"{parse_rate:.0%} parse as numbers, so conversion loses nothing."
                        ),
                    ))
                    continue

            if len(counts) < 2:
                continue
            dominant_class = counts.index[0]
            dominant_share = float(counts.iloc[0] / len(strings))
            conflicts = classes[classes != dominant_class]

            if (
                dominant_share >= TYPE_DOMINANCE_RATIO
                and len(conflicts) >= TYPE_ANOMALY_MIN_CONFLICTS
            ):
                kind = "dominant_with_conflicts"
                confidence = round(dominant_share, 4)
            elif (
                dominant_share < TYPE_DOMINANCE_RATIO
                and len(counts) >= 2
                and float(counts.iloc[1] / len(strings)) >= 0.10
            ):
                # No class reaches the dominance bar: the column's type is
                # genuinely ambiguous.
                kind = "mixed_no_dominant_type"
                confidence = round(1.0 - dominant_share, 4)
            else:
                continue

            conflict_rows = conflicts.index
            evidence.append(
                Evidence(
                    detector=self.name,
                    problem_type=self.problem_type,
                    column=str(col),
                    method="value_class_profile",
                    affected_count=int(len(conflicts)),
                    affected_row_indices=_sample_indices(
                        [df.index.get_loc(i) for i in conflict_rows[:_MAX_AFFECTED_ROW_SAMPLES]]
                    ),
                    statistics={
                        "expected_class": dominant_class,
                        "dominant_share": round(dominant_share, 4),
                        "observed_classes": {
                            str(k): int(v) for k, v in counts.items()
                        },
                        "conflicting_examples": [
                            str(v)[:80]
                            for v in strings.loc[conflict_rows].head(_MAX_EXAMPLES)
                        ],
                        "kind": kind,
                    },
                    confidence=confidence,
                    severity="medium",
                    explanation=(
                        f"'{col}' is dominated by {dominant_class} values "
                        f"({dominant_share:.0%}) but contains {len(conflicts)} "
                        f"value(s) of other kinds ({kind})."
                    ),
                )
            )
        return evidence