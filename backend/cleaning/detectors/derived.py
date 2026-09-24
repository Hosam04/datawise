"""Derived column consistency detector for the DataWise Cleaning Engine."""
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from backend.cleaning.contracts import (
    DERIVED_EXACT_COVERAGE,
    DERIVED_MIN_ROWS,
    DERIVED_OFFSET_SEARCH,
    DERIVED_SUSPECT_COVERAGE,
)
from backend.cleaning.detectors.base import (
    BaseDetector,
    Evidence,
    ColumnProfile,
    InspectionResult,
    _sample_indices,
    _WEEKDAY_NAMES,
    DAYOFWEEK_TOKENS,
    DAYOFWEEK_PAIR_TOKENS,
    _name_segments,
    _name_has_keyword,
    _is_string_like,
)


class DerivedColumnConsistencyDetector(BaseDetector):
    """Verifies deterministic relationships between derived and source
    columns (target == a+b+k, target == a*b, target == len(text)).

    Coverage == 100%      -> relationship VALID: nothing reported.
    EXACT..SUSPECT range  -> VIOLATION/SUSPICIOUS evidence; repair is decided
                             by the Decision Engine only for near-exact
                             relationships with unambiguous formulas.
    Below SUSPECT         -> not considered a relationship at all.
    """

    name = "DerivedColumnConsistencyDetector"
    problem_type = "derived_column"

    def __init__(self, max_numeric_pair_cols: Optional[int] = None):
        # Scale guard (Phase 9): when set, only the first N numeric columns
        # participate in O(n^2) pair scans. Deterministic order = column order.
        self.max_numeric_pair_cols = max_numeric_pair_cols

    def detect(self, df, profiles, inspection) -> List[Evidence]:
        evidence: List[Evidence] = []

        numeric_cols = []
        for col in df.select_dtypes(include=[np.number]).columns:
            profile = profiles.get(str(col))
            if profile is not None and profile.semantic_type == "identifier":
                continue
            if pd.api.types.is_bool_dtype(df[col]):
                continue
            numeric_cols.append(col)
        if (self.max_numeric_pair_cols is not None
                and len(numeric_cols) > self.max_numeric_pair_cols):
            numeric_cols = numeric_cols[: self.max_numeric_pair_cols]

        def _relation_coverage(target: pd.Series, computed: pd.Series):
            valid = target.notna() & computed.notna()
            n = int(valid.sum())
            if n < DERIVED_MIN_ROWS:
                return None
            match = (target[valid] == computed[valid])
            return float(match.mean()), n

        def _emit(target_col, formula, params, violations_mask, coverage, n):
            count = int(violations_mask.sum())
            if coverage >= DERIVED_EXACT_COVERAGE:
                if count == 0:
                    return  # VALID relationship — nothing to report
                sev, conf, kind = "medium", round(coverage, 4), "violations"
            elif coverage >= DERIVED_SUSPECT_COVERAGE:
                sev, conf, kind = "low", round(coverage, 4), "suspicious_partial"
            else:
                return
            evidence.append(Evidence(
                detector=self.name,
                problem_type=self.problem_type,
                column=str(target_col),
                method=formula,
                affected_count=count,
                affected_row_indices=_sample_indices(df.index[violations_mask.fillna(False)].tolist()),
                statistics={
                    **params,
                    "coverage": round(coverage, 6),
                    "rows_evaluated": n,
                    "kind": kind,
                    # Uncapped labels: the decision layer needs every
                    # violating row, not a bounded sample.
                    "violation_row_labels": [
                        int(i) for i in df.index[violations_mask.fillna(False)].tolist()
                    ],
                },
                confidence=conf,
                severity=sev,
                explanation=(
                    f"'{target_col}' matches {formula} on {coverage:.1%} of "
                    f"{n} valid rows ({count} deviation(s))."
                ),
            ))

        # Explicit metadata first: caller-DECLARED formulas are verified
        # exactly as stated. Auto-discovery below then skips these targets,
        # so a declared relationship is never second-guessed by a guess.
        declared_targets: set = set()
        for profile_col, profile in profiles.items():
            formula = getattr(profile, "declared_formula", None)
            if not formula:
                continue
            target = str(profile_col)
            if target not in df.columns:
                continue
            declared_targets.add(target)

            op = formula.get("op")
            sources = [str(s) for s in formula.get("sources") or []]
            offset = formula.get("offset")

            if op == "day_of_week":
                if len(sources) != 1 or sources[0] not in df.columns:
                    continue
                src = sources[0]
                dt = pd.to_datetime(df[src], errors="coerce")
                sample = set(
                    df[target].dropna().astype(str).str.strip().str.lower().unique()
                )
                if sample <= {d.lower() for d in _WEEKDAY_NAMES}:
                    mode = "day_name"
                    expected = dt.dt.day_name().astype("string").str.lower()
                    actual = df[target].astype("string").str.strip().str.lower()
                elif sample <= {"1", "2", "3", "4", "5", "6", "7"}:
                    mode = "iso_number"
                    expected = dt.dt.isoweekday().astype("Float64")
                    actual = pd.to_numeric(df[target], errors="coerce")
                else:
                    continue
                both = actual.notna() & expected.notna()
                n = int(both.sum())
                if n < DERIVED_MIN_ROWS:
                    continue
                coverage = float((actual[both] == expected[both]).mean())
                violations = both & (actual != expected)
                _emit(target, "day_of_week",
                      {"source": src, "mode": mode, "declared": True},
                      violations, coverage, n)
                continue

            if op == "string_length":
                if len(sources) != 1 or sources[0] not in df.columns:
                    continue
                computed = df[sources[0]].astype("string").str.len().astype("Float64")
                t = pd.to_numeric(df[target], errors="coerce")
                cov = _relation_coverage(t, computed)
                if cov is None:
                    continue
                coverage, n = cov
                violations = t.notna() & computed.notna() & (t != computed)
                _emit(target, "string_length",
                      {"source": sources[0], "declared": True},
                      violations, coverage, n)
                continue

            if op in ("sum_offset", "product"):
                if len(sources) != 2 or any(s not in df.columns for s in sources):
                    continue
                a = pd.to_numeric(df[sources[0]], errors="coerce")
                b = pd.to_numeric(df[sources[1]], errors="coerce")
                t = pd.to_numeric(df[target], errors="coerce")
                computed = a * b if op == "product" else a + b + float(offset or 0)
                cov = _relation_coverage(t, computed)
                if cov is None:
                    continue
                coverage, n = cov
                violations = t.notna() & computed.notna() & (t != computed)
                params = {"source_a": sources[0], "source_b": sources[1],
                          "declared": True}
                if op == "sum_offset":
                    params["offset"] = int(offset) if offset is not None else 0
                _emit(target, op, params, violations, coverage, n)

        # target == a + b + k  /  target == a * b
        for ti, target in enumerate(numeric_cols):
            if target in declared_targets:
                continue
            others = [c for c in numeric_cols if c != target]
            t = pd.to_numeric(df[target], errors="coerce")
            # Sparse / near-zero targets produce huge numbers of accidental
            # product matches (0 * x == 0). Skip product discovery when the
            # target is dominated by zeros; sum_offset is still allowed.
            t_nonzero_share = 0.0
            t_valid = t.notna()
            if int(t_valid.sum()) > 0:
                t_nonzero_share = float((t[t_valid] != 0).mean())

            for i, src_a in enumerate(others):
                for src_b in others[i + 1:]:
                    a = pd.to_numeric(df[src_a], errors="coerce")
                    b = pd.to_numeric(df[src_b], errors="coerce")
                    for k in DERIVED_OFFSET_SEARCH:
                        cov = _relation_coverage(t, a + b + k)
                        if cov is None:
                            continue
                        coverage, n = cov
                        if coverage < DERIVED_SUSPECT_COVERAGE:
                            continue
                        violations = t.notna() & (a + b + k).notna() & (
                            t != (a + b + k)
                        )
                        _emit(target, "sum_offset", {
                            "source_a": str(src_a), "source_b": str(src_b),
                            "offset": int(k),
                        }, violations, coverage, n)

                    # Product relationships are only considered when the
                    # target has a meaningful non-zero density. Otherwise
                    # zero-heavy count columns (children, babies, etc.)
                    # generate hundreds of false partial matches.
                    if t_nonzero_share < 0.15:
                        continue
                    cov = _relation_coverage(t, a * b)
                    if cov is not None:
                        coverage, n = cov
                        # Slightly stricter bar for auto-discovered products
                        # to further suppress chance matches on sparse data.
                        if coverage >= max(DERIVED_SUSPECT_COVERAGE, 0.95):
                            product = a * b
                            violations = t.notna() & product.notna() & (t != product)
                            _emit(target, "product", {
                                "source_a": str(src_a), "source_b": str(src_b),
                            }, violations, coverage, n)

        # target == len(text_source)
        text_cols = [
            c for c in df.columns
            if profiles.get(str(c)) is not None
            and profiles[str(c)].semantic_type in ("text", "categorical")
            and _is_string_like(df[c])
        ]
        for target in numeric_cols:
            if target in declared_targets:
                continue
            t = pd.to_numeric(df[target], errors="coerce")
            for src in text_cols:
                lengths = df[src].astype("string").str.len().astype("Float64")
                cov = _relation_coverage(t, lengths)
                if cov is None:
                    continue
                coverage, n = cov
                if coverage < DERIVED_SUSPECT_COVERAGE:
                    continue
                violations = t.notna() & lengths.notna() & (t != lengths)
                _emit(target, "string_length", {"source": str(src)}, violations, coverage, n)

        # target == weekday(datetime_source)  — mathematically determined,
        # therefore safely repairable when the relationship is near-exact.
        evidence.extend(self._detect_weekday_relations(df, profiles))

        # Deduplicate: keep only the highest-coverage finding per target column.
        # This prevents multiple source combinations for the same target from
        # all being reported (e.g. target = a + b and target = a + c both match).
        best_per_target: Dict[str, Evidence] = {}
        for ev in evidence:
            existing = best_per_target.get(ev.column)
            if existing is None or ev.statistics.get("coverage", 0) > existing.statistics.get("coverage", 0):
                best_per_target[ev.column] = ev

        return list(best_per_target.values())

    def _detect_weekday_relations(
        self, df: pd.DataFrame, profiles: Dict[str, ColumnProfile]
    ) -> List[Evidence]:
        """Detect weekday columns derivable from a datetime column.

        Generic name-based matching (weekday/dow/day-of-week vocabulary);
        the value representation (English day names or ISO numbers 1..7) is
        inferred from the data itself.
        """
        evidence: List[Evidence] = []

        datetime_cols = [
            c for c in df.columns
            if pd.api.types.is_datetime64_any_dtype(df[c])
        ]
        if not datetime_cols:
            return evidence

        def _is_weekday_name(name: str) -> bool:
            segs = _name_segments(name)
            if any(_name_has_keyword(segs, t) for t in DAYOFWEEK_TOKENS):
                return True
            return any(all(tok in segs for tok in pair)
                       for pair in DAYOFWEEK_PAIR_TOKENS)

        weekday_cols = [
            c for c in df.columns
            if c not in datetime_cols and _is_weekday_name(str(c))
            and (profiles.get(str(c)) is None
                 or profiles[str(c)].semantic_type != "identifier")
        ]
        if not weekday_cols:
            return evidence

        for target in weekday_cols:
            profile = profiles.get(str(target))
            if profile is not None and getattr(profile, "declared_formula", None):
                continue  # declared formulas are verified above, not re-guessed
            series = df[target].dropna()
            if series.empty:
                continue
            sample_values = set(series.astype(str).str.strip().str.lower().unique())

            for source in datetime_cols:
                dt = pd.to_datetime(df[source], errors="coerce")

                name_repr = {
                    day.lower() for day in
                    ["Monday", "Tuesday", "Wednesday", "Thursday",
                     "Friday", "Saturday", "Sunday"]
                }
                number_repr = {"1", "2", "3", "4", "5", "6", "7"}

                if sample_values <= name_repr:
                    mode, expected = "day_name", dt.dt.day_name()
                elif sample_values <= number_repr:
                    mode, expected = "iso_number", dt.dt.isoweekday().astype("Float64")
                    expected = expected.astype("string")
                else:
                    continue

                target_clean = df[target]
                if mode == "day_name":
                    target_cmp = target_clean.astype("string").str.strip().str.lower()
                    expected = expected.astype("string").str.lower()
                else:
                    target_cmp = (
                        pd.to_numeric(target_clean, errors="coerce")
                        .astype("Int64").astype("string")
                    )

                both = target_cmp.notna() & expected.notna()
                n = int(both.sum())
                if n < DERIVED_MIN_ROWS:
                    continue
                match = target_cmp[both] == expected[both]
                coverage = float(match.mean())
                violations_mask = both & (target_cmp != expected)
                count = int(violations_mask.sum())
                if coverage < DERIVED_SUSPECT_COVERAGE:
                    continue
                if coverage >= DERIVED_EXACT_COVERAGE and count == 0:
                    continue  # VALID — nothing to report

                kind = ("violations" if coverage >= DERIVED_EXACT_COVERAGE
                        else "suspicious_partial")
                evidence.append(Evidence(
                    detector=self.name,
                    problem_type=self.problem_type,
                    column=str(target),
                    method="day_of_week",
                    affected_count=count,
                    affected_row_indices=_sample_indices(
                        df.index[violations_mask].tolist()
                    ),
                    statistics={
                        "source": str(source),
                        "mode": mode,
                        "coverage": round(coverage, 6),
                        "rows_evaluated": n,
                        "kind": kind,
                        "violation_row_labels": [
                            int(i) for i in df.index[violations_mask].tolist()
                        ],
                    },
                    confidence=round(coverage, 4),
                    severity="medium" if kind == "violations" else "low",
                    explanation=(
                        f"'{target}' disagrees with weekday({source}) on "
                        f"{count}/{n} rows ({coverage:.1%} consistent). The "
                        "correct value is mathematically determined."
                        if kind == "violations" else
                        f"'{target}' only loosely matches weekday({source}) "
                        f"({coverage:.1%}); suspicious but unproven."
                    ),
                ))
        return evidence