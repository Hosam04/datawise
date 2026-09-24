"""Decision Engine for the DataWise Cleaning Engine.

SAFETY GATE: converts Evidence into conservative verdicts
(APPLY / SKIP / FLAG). This module NEVER modifies a DataFrame; it reads it
only to compute concrete, deterministic action parameters (e.g. a median).

Default posture: if evidence does not justify a change, DO NOT MODIFY — flag.
"""
from typing import Dict, List, Optional

import pandas as pd
from backend.utils.logger import setup_logger

from backend.cleaning.contracts import (
    DERIVED_EXACT_COVERAGE,
    MAX_DUPLICATE_RATIO_FOR_REMOVAL,
    MAX_IMPUTE_MISSING_RATIO,
    MAX_MODE_FILL_MISSING_RATIO,
    MIN_NON_NULL_FOR_IMPUTE,
    MODE_DOMINANCE_RATIO,
    UNKNOWN_CATEGORY_LABEL,
    CleaningPolicy,
    ColumnProfile,
    Decision,
    Evidence,
    InspectionResult,
)


class DecisionEngine:
    """Rule-based, dataset-agnostic decision layer."""

    def __init__(
        self,
        enable_imputation: bool = True,
        enable_duplicate_removal: bool = True,
        add_outlier_flags: bool = True,
        enable_formatting_normalization: bool = True,
        enable_categorical_normalization: bool = True,
        enable_derived_repair: bool = True,
        enable_type_normalization: bool = True,
        min_apply_confidence: float = 0.0,
        dry_run: bool = False,
        max_mutations_per_column: int = 1,
        max_total_mutations: Optional[int] = None,
        policy: Optional[CleaningPolicy] = None,
    ):

        self.logger = setup_logger("DecisionEngine")
        # A full CleaningPolicy wins when supplied; otherwise one is built
        # from the individual keyword arguments (legacy compatibility).
        if policy is not None:
            self.policy = policy
        else:
            self.policy = CleaningPolicy(
                enable_imputation=enable_imputation,
                enable_duplicate_removal=enable_duplicate_removal,
                add_outlier_flags=add_outlier_flags,
                enable_formatting_normalization=enable_formatting_normalization,
                enable_categorical_normalization=enable_categorical_normalization,
                enable_derived_repair=enable_derived_repair,
                enable_type_normalization=enable_type_normalization,
                min_apply_confidence=min_apply_confidence,
                dry_run=dry_run,
                max_mutations_per_column=max_mutations_per_column,
                max_total_mutations=max_total_mutations,
            )

    # Backwards-compatible attribute access routed through the policy.
    @property
    def enable_imputation(self) -> bool:
        return self.policy.enable_imputation

    @property
    def enable_duplicate_removal(self) -> bool:
        return self.policy.enable_duplicate_removal

    @property
    def add_outlier_flags(self) -> bool:
        return self.policy.add_outlier_flags

    @property
    def enable_formatting_normalization(self) -> bool:
        return self.policy.enable_formatting_normalization

    @property
    def enable_categorical_normalization(self) -> bool:
        return self.policy.enable_categorical_normalization

    @property
    def enable_derived_repair(self) -> bool:
        return self.policy.enable_derived_repair

    @property
    def enable_type_normalization(self) -> bool:
        return self.policy.enable_type_normalization

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def decide(
        self,
        evidence: Evidence,
        profiles: Dict[str, ColumnProfile],
        inspection: InspectionResult,
        df: pd.DataFrame,
    ) -> Decision:
        """Route one piece of evidence to its decision rule."""
        # Suppression-token findings are ALWAYS evidence-only: such values
        # carry meaning and must never be converted or imputed away.
        if evidence.method == "suppression_token_classification":
            return self._flag_only(
                evidence,
                [
                    "Suppression-style token(s) detected.",
                    "These values are semantic, not missing: they are "
                    "preserved untouched and never used as fill values.",
                ],
            )
        decision = self._route(evidence, profiles, inspection, df)
        return self._enforce_policy(decision)

    def _route(
        self,
        evidence: Evidence,
        profiles: Dict[str, ColumnProfile],
        inspection: InspectionResult,
        df: pd.DataFrame,
    ) -> Decision:
        """Problem-type routing (no policy gating here)."""
        if evidence.problem_type == "missing_values":
            return self._decide_missing(evidence, profiles, df)
        if evidence.problem_type == "duplicates":
            return self._decide_duplicates(evidence)
        if evidence.problem_type == "outliers":
            return self._decide_outliers(evidence)
        if evidence.problem_type == "invalid_values":
            return self._decide_invalid_values(evidence)
        if evidence.problem_type == "type_anomaly":
            return self._decide_type_anomaly(evidence)
        if evidence.problem_type == "categorical_consistency":
            return self._decide_categorical_consistency(evidence)
        if evidence.problem_type == "formatting":
            return self._decide_formatting(evidence)
        if evidence.problem_type == "constraint_violation":
            return self._decide_constraint(evidence)
        if evidence.problem_type == "derived_column":
            return self._decide_derived_column(evidence)
        # missingness_pattern / semantic_anomaly / suppression tokens /
        # plausibility hints are evidence-only by design: never actionable.
        if evidence.problem_type == "semantic_anomaly":
            if evidence.method == "encoding_artifacts":
                profile = profiles.get(evidence.column)
                if profile and profile.semantic_type in ("text", "categorical"):
                    return Decision(
                        evidence=evidence,
                        verdict="apply",
                        action="HTMLDecodingAction",
                        parameters={"column": evidence.column},
                        reasons=[
                            f"HTML entities detected in {profile.semantic_type} column.",
                            "Decoding is deterministic and preserves semantic content."
                        ],
                    )
            return self._flag_only(evidence, [
                "Semantic anomaly detected; no deterministic correction exists."
            ])
    
        # missingness_pattern / suppression tokens / plausibility hints
        # are evidence-only by design: never actionable.
        return self._flag_only(evidence, [
            "No deterministic correction exists; values preserved."
        ])

    def _enforce_policy(self, decision: Decision) -> Decision:
        """Central policy gates applied to every routed decision.

        - dry_run: strips the action from ANY executable decision
          (including annotation actions) and downgrades APPLY to FLAG.
        - min_apply_confidence: weak approvals are demoted to FLAG.
        """
        policy = self.policy

        if decision.verdict == "apply":
            confidence = float(decision.evidence.confidence)
            if confidence < policy.min_apply_confidence:
                decision.policy_checks.append({
                    "rule": "min_apply_confidence",
                    "passed": False,
                    "detail": (
                        f"confidence {confidence:.2f} < required "
                        f"{policy.min_apply_confidence:.2f}"
                    ),
                })
                decision.verdict = "flag"
                decision.action = None
                decision.reasons.append(
                    f"Confidence {confidence:.2f} below the policy "
                    f"application bar ({policy.min_apply_confidence:.2f})."
                )
                return decision
            decision.policy_checks.append({
                "rule": "apply_approved",
                "passed": True,
                "detail": f"confidence={confidence:.2f}",
            })

        if policy.dry_run and decision.action:
            decision.policy_checks.append({
                "rule": "dry_run",
                "passed": False,
                "detail": f"action '{decision.action}' withheld",
            })
            decision.reasons.append(
                f"Dry-run policy: action '{decision.action}' would have "
                "been executed but was withheld."
            )
            decision.action = None
        return decision

    # ------------------------------------------------------------------
    # Missing values
    # ------------------------------------------------------------------

    def _decide_missing(
        self, ev: Evidence, profiles: Dict[str, ColumnProfile], df: pd.DataFrame
    ) -> Decision:
        column = ev.column or ""
        profile = profiles.get(column)

        if not self.enable_imputation:
            return self._flag_only(ev, ["Imputation disabled by configuration."])
        if profile is None:
            return self._skip(ev, ["No column profile available; refusing to guess."])

        semantic = profile.semantic_type

        if semantic in ("identifier", "datetime", "boolean"):
            return self._flag_only(
                ev,
                [
                    f"Semantic type '{semantic}' has no safe deterministic "
                    "imputation; values left untouched."
                ],
            )

        stats = ev.statistics
        ratio = float(stats.get("missing_ratio", profile.missing_ratio))
        non_null = int(stats.get("non_null_count", 0))

        # Empty-string / whitespace-only "missing" cells are NOT NaN: filling
        # them would require an explicitly approved normalization action.
        # They are preserved and flagged instead of silently rewritten.
        non_nan_missingness = (
            int(stats.get("empty_string_count", 0))
            + int(stats.get("whitespace_only_count", 0))
        )
        if non_nan_missingness:
            return self._flag_only(
                ev,
                [
                    f"{non_nan_missingness} empty/whitespace-only value(s) "
                    "detected alongside real gaps.",
                    "Empty-string handling changes representation, not just "
                    "content; preserved and flagged for review.",
                ],
            )

        if semantic == "numeric":
            return self._decide_numeric_fill(
                ev, column, ratio, non_null, df, profile
            )

        if semantic == "text":
            return self._flag_only(
                ev,
                [
                    "Free-text column: no reliable fill strategy; "
                    "values left untouched."
                ],
            )

        return self._decide_categorical_fill(ev, profile, ratio)

    def _decide_numeric_fill(
        self,
        ev: Evidence,
        column: str,
        ratio: float,
        non_null: int,
        df: pd.DataFrame,
        profile: ColumnProfile,
    ) -> Decision:
        # Numeric imputation is intentionally stricter than categorical mode-fill.
        # Hard safety cap first (even constant columns must not fabricate most
        # of themselves), then the conservative 20% cluster-fabrication guard.
        if ratio > MAX_IMPUTE_MISSING_RATIO:
            return self._flag_only(
                ev,
                [
                    f"Missing ratio {ratio:.1%} exceeds the "
                    f"{MAX_IMPUTE_MISSING_RATIO:.0%} safety limit; median fill "
                    "would fabricate most of the column."
                ],
            )

        if ratio > MAX_MODE_FILL_MISSING_RATIO:
            return self._flag_only(
                ev,
                [
                    f"Missing ratio {ratio:.1%} exceeds the conservative "
                    f"numeric imputation limit of {MAX_MODE_FILL_MISSING_RATIO:.0%}; "
                    "median fill could fabricate a large artificial cluster."
                ],
            )

        # Constant column below both limits: the single observed value is
        # strong evidence for filling its gaps.
        if profile.constant:
            return self._decide_constant_fill(ev, profile, ratio)

        if non_null < MIN_NON_NULL_FOR_IMPUTE:
            return self._flag_only(
                ev,
                [
                    f"Only {non_null} observed value(s); not enough evidence "
                    "for a meaningful median."
                ],
            )

        values = pd.to_numeric(df[column], errors="coerce")
        median = float(values.median())
        if not pd.notna(median):
            return self._flag_only(
                ev, ["Median undefined (no numeric observations); cannot fill."]
            )

        decision = Decision(
            evidence=ev,
            verdict="apply",
            action="MissingValueAction",
            parameters={
                "strategy": "median",
                "fill_value": median,
            },
            reasons=[
                f"Numeric column with {non_null} observed value(s) and only "
                f"{ratio:.1%} missing; median is robust to skew and outliers.",
                "Only MISSING cells are filled — no observed value is altered.",
            ],
            policy_checks=[
                {"rule": "missing_ratio_cap", "passed": True,
                 "detail": f"{ratio:.4f} <= {MAX_IMPUTE_MISSING_RATIO}"},
                {"rule": "min_non_null", "passed": True,
                 "detail": f"{non_null} >= {MIN_NON_NULL_FOR_IMPUTE}"},
            ],
        )
        return decision

    def _decide_categorical_fill(
        self, ev: Evidence, profile: ColumnProfile, ratio: float
    ) -> Decision:
        mode_value = profile.top_values[0]["value"] if profile.top_values else None

        # A constant categorical column below the safety limit: gaps get the
        # only observed value.
        if profile.constant and ratio < MAX_IMPUTE_MISSING_RATIO and mode_value is not None:
            return self._decide_constant_fill(ev, profile, ratio)

        if ratio >= MAX_IMPUTE_MISSING_RATIO:
            self.logger.warning(
                f"Column '{ev.column}' has {ratio:.1%} missing data (>={MAX_IMPUTE_MISSING_RATIO:.0%}). "
                f"Dropping column instead of filling with '{UNKNOWN_CATEGORY_LABEL}'."
            )
            return Decision(
                evidence=ev,
                verdict="apply",
                action="DropColumnAction",
                parameters={"column": ev.column},
                reasons=[
                    f"Column has {ratio:.1%} missing data (>={MAX_IMPUTE_MISSING_RATIO:.0%}).",
                    f"Filling with '{UNKNOWN_CATEGORY_LABEL}' would create a near-constant column.",
                    "Dropping the column preserves dataset quality."
                ],
            )

        if mode_value is None:
            return self._flag_only(
                ev, ["No observed values available to derive any fill."]
            )

        if ratio <= MAX_MODE_FILL_MISSING_RATIO:
            token_count = int((ev.statistics or {}).get("missing_token_count", 0))
            effective = int(
                (ev.statistics or {}).get("effective_missing", ev.affected_count or 0)
            )
            # "?" / "NA" style tokens are explicit unknowns — preserve them
            # as a category instead of inventing the mode.
            if token_count > 0 and token_count >= 0.5 * max(effective, 1):
                return Decision(
                    evidence=ev,
                    verdict="apply",
                    action="MissingValueAction",
                    parameters={"strategy": "explicit_unknown_category"},
                    reasons=[
                        f"{token_count} missing-string token(s) (e.g. '?', 'NA'); "
                        f"preserving them as '{UNKNOWN_CATEGORY_LABEL}' rather than "
                        "inventing the mode."
                    ],
                )
            return Decision(
                evidence=ev,
                verdict="apply",
                action="MissingValueAction",
                parameters={"strategy": "mode", "fill_value": mode_value},
                reasons=[
                    f"Low missing ratio ({ratio:.1%}); mode fill is a bounded, "
                    "low-risk approximation."
                ],
            )

        if profile.dominant_share >= MODE_DOMINANCE_RATIO:
            return Decision(
                evidence=ev,
                verdict="apply",
                action="MissingValueAction",
                parameters={"strategy": "mode", "fill_value": mode_value},
                reasons=[
                    f"Moderate missing ratio ({ratio:.1%}) but one category "
                    f"dominates ({profile.dominant_share:.0%}); mode fill is "
                    "well supported by evidence."
                ],
            )

        return self._flag_only(
            ev,
            [
                f"Moderate missing ratio ({ratio:.1%}) without a dominant "
                "category; no justified fill — flagged for review."
            ],
        )

    # ------------------------------------------------------------------
    # Duplicates
    # ------------------------------------------------------------------

    def _decide_duplicates(self, ev: Evidence) -> Decision:
        # ONLY exact-match evidence may drive row removal. Near-duplicate
        # findings (normalized equality) describe potentially distinct
        # observations and are always flagged for review.
        valid_methods = {"exact_row_match", "exact_duplicate_rows", "exact_match"}
        if ev.method not in valid_methods:
            return self._flag_only(
                ev,
                [
                    f"'{ev.method}' duplicates are NOT exact matches; "
                    "removal could destroy distinct observations. "
                    "Flagged for caller review."
                ],
            )

        ratio = float(ev.statistics.get("duplicate_ratio", 0.0))
        count = int(ev.affected_count)

        if not self.enable_duplicate_removal:
            return self._flag_only(ev, ["Duplicate removal disabled by configuration."])

        if count > 0:
            excluded_columns = list(ev.statistics.get("excluded_identifier_columns", []))
            return Decision(
                evidence=ev,
                verdict="apply",
                action="DuplicateRemovalAction",
                parameters={
                    "keep": "first",
                    "rows_to_remove": count,
                    "excluded_columns": excluded_columns,
                },
                reasons=[
                    f"{count} exact duplicate row(s) detected ({ratio:.2%} of dataset).",
                    "Exact duplicate rows are deterministically redundant; keep the first occurrence.",
                ],
                policy_checks=[
                    {"rule": "exact_match_only", "passed": True,
                     "detail": ev.method},
                    {"rule": "duplicate_removal_enabled", "passed": True,
                     "detail": "enabled"},
                ],
            )

        return self._flag_only(ev, ["No duplicate rows require removal."])

    # ------------------------------------------------------------------
    # Outliers: OUTLIER ≠ ERROR — never modify, at most annotate flags
    # ------------------------------------------------------------------

    def _decide_outliers(self, ev: Evidence) -> Decision:
        params: Dict[str, object] = {
            "column": ev.column,
            "lower_bound": ev.statistics.get("lower_bound"),
            "upper_bound": ev.statistics.get("upper_bound"),
        }
        if self.add_outlier_flags and ev.column:
            return Decision(
                evidence=ev,
                verdict="flag",
                action="OutlierFlagAction",
                parameters=params,
                reasons=[
                    "Statistical unusualness is not proof of error; values are "
                    "kept and annotated with an *_OutlierFlag column."
                ],
            )
        return self._flag_only(
            ev,
            ["Outlier annotation disabled by configuration; issue reported only."],
        )

    # ------------------------------------------------------------------
    # Invalid values: objective range violations. No invented replacements
    # exist, so the value is preserved and flagged.
    # ------------------------------------------------------------------

    def _decide_invalid_values(self, ev: Evidence) -> Decision:
        column = ev.column or ""
        if "coord" in column.lower() or "location" in column.lower():
            known_null_island = {"[0.0, 0.0]", "[0,0]", "0,0", "[0.0,0.0]", "[0, 0]"}

            declared = ev.statistics.get("violations") or ev.statistics.get(
                "examples"
            ) or []
            invalid_coords = set(str(v) for v in declared) | known_null_island
        
            return Decision(
                evidence=ev,
                verdict="apply",
                action="CoordinateValidatorAction",
                parameters={
                    "column": column,
                    "invalid_values": list(invalid_coords),
                },
                reasons=[
                    f"Coordinate column '{column}' may contain invalid values (Null Island).",
                    "Replacing declared invalid coordinates with NaN preserves geographic accuracy.",
                ],
            )
        rule = str(ev.statistics.get("rule", "range"))
        return self._flag_only(
            ev,
            [
                f"{ev.affected_count} value(s) violate the explicit '{rule}' "
                "semantic bound.",
                "No deterministic correction exists (the true value is "
                "unknowable); preserving the row and flagging for review.",
            ],
        )

    # ------------------------------------------------------------------
    # Type anomalies: conflicting value classes inside one column. Casting
    # would guess — flag instead.
    # ------------------------------------------------------------------

    def _decide_type_anomaly(self, ev: Evidence) -> Decision:
        kind = str(ev.statistics.get("kind", "dominant_with_conflicts"))
        expected = str(ev.statistics.get("expected_class", "unknown"))

        if ev.method in {"lossless_numeric_string", "lossless_formatted_numeric_string"}:
            # Every non-null value parses; conversion provably loses nothing.
            if self.enable_type_normalization:
                return Decision(
                    evidence=ev,
                    verdict="apply",
                    action="TypeNormalizationAction",
                    parameters={
                        "is_identifier": False,
                        "normalization": ev.statistics.get("normalization"),
                    },
                    reasons=[
                        "Every non-null value parses as a number, so "
                        "conversion is deterministic and lossless.",
                        "Identifier columns are excluded by the detector.",
                    ],
                )
            return self._flag_only(
                ev, ["Type normalization disabled by configuration."]
            )
        if ev.method == "lossless_date_string":
            if self.enable_type_normalization:
                return Decision(
                    evidence=ev,
                    verdict="apply",
                    action="TypeNormalizationAction",
                    parameters={
                        "is_identifier": False,
                        "normalization": "to_datetime",
                    },
                    reasons=[
                        "Every non-null value parses as a datetime, so "
                        "conversion is deterministic and lossless.",
                        "Identifier columns are excluded by the detector.",
                    ],
                )
            return self._flag_only(
                ev, ["Type normalization disabled by configuration."]
            )

        # NEW: lossless coordinate-string conversion
        if ev.method == "lossless_coordinate_string":
            if self.enable_type_normalization:
                return Decision(
                    evidence=ev,
                    verdict="apply",
                    action="TypeNormalizationAction",
                    parameters={
                        "is_identifier": False,
                        "normalization": "parse_coordinate",
                    },
                    reasons=[
                        "Every non-null value parses as a float coordinate, so "
                        "conversion is deterministic and lossless.",
                    ],
                )
            return self._flag_only(
                ev, ["Type normalization disabled by configuration."]
            )

        if kind == "mixed_no_dominant_type":
            return self._flag_only(
                ev,
                [
                    f"Column mixes multiple value classes with no dominant "
                    f"type ({ev.statistics.get('observed_classes')}); any "
                    "conversion would be a guess.",
                ],
            )
        return self._flag_only(
            ev,
            [
                f"{ev.affected_count} conflicting value(s) inside a mostly-"
                f"{expected} column.",
                "Ambiguous tokens must not be blindly cast; flagged with "
                "examples for review.",
            ],
        )

    # ------------------------------------------------------------------
    # Categorical consistency: deterministic case-folds may be applied;
    # anything else stays untouched.
    # ------------------------------------------------------------------

    def _decide_categorical_consistency(self, ev: Evidence) -> Decision:
        proposals = ev.statistics.get("proposals", [])
        method = ev.method

        if method not in ("deterministic_case_fold",
                          "deterministic_separator_fold",
                          "deterministic_categorical_fold"):
            return self._flag_only(
                ev,
                [
                    "Category variants differ beyond deterministic "
                    "normalization rules; equivalence is not established — "
                    "flagged, not merged.",
                ],
            )

        if not self.enable_categorical_normalization:
            return self._flag_only(
                ev, ["Categorical normalization disabled by configuration."]
            )

        mapping: Dict[str, str] = {}
        touched_rows = 0
        for proposal in proposals:
            canonical = str(proposal["canonical"])
            for variant in proposal["variants"]:
                mapping[str(variant)] = canonical
            touched_rows += int(proposal.get("affected_rows", 0))

        column = ev.column or ""
        if not mapping:
            return self._skip(ev, ["No variants require normalization."])

        reasons = [
            f"Fold to canonical spellings is deterministic and reversible "
            f"({len(mapping)} variant(s), ~{touched_rows} cell(s)).",
            "Canonical chosen as the most frequent spelling; ties broken by "
            "first appearance.",
        ]
        if method == "deterministic_separator_fold":
            reasons.insert(0, (
                "Separator-only spelling differences (e.g. 'A_4' vs 'A4') "
                "map to the dominant form of each group."
            ))
        return Decision(
            evidence=ev,
            verdict="apply",
            action="CategoricalNormalizationAction",
            parameters={"mapping": mapping, "column": column},
            reasons=reasons,
        )

    # ------------------------------------------------------------------
    # Formatting: whitespace normalization is content-preserving; mixed
    # date/currency formats are ambiguous and stay untouched.
    # ------------------------------------------------------------------

    def _decide_formatting(self, ev: Evidence) -> Decision:
        method = ev.method

        if method == "whitespace_normalization":
            if not self.enable_formatting_normalization:
                return self._flag_only(
                    ev, ["Formatting normalization disabled by configuration."]
                )
            return Decision(
                evidence=ev,
                verdict="apply",
                action="FormattingNormalizationAction",
                parameters={
                    "transformation": "strip+collapse_whitespace",
                    "allow_identifier_column": False,
                },
                reasons=[
                    "Trimming leading/trailing and repeated internal "
                    "whitespace never changes semantic content.",
                    "Identifier columns are excluded upstream by the detector.",
                ],
            )

        if method == "mixed_date_formats":
            return self._flag_only(
                ev,
                [
                    "Multiple date formats coexist; day/month order differs "
                    "between conventions so no single deterministic parse "
                    "exists — flagged.",
                ],
            )

        if method == "mixed_currency_formatting":
            return self._flag_only(
                ev,
                [
                    "Currency-prefixed and plain numeric values coexist; "
                    "removing symbols changes representation and is not "
                    "provably semantics-free — flagged.",
                ],
            )

        return self._flag_only(ev, ["Unknown formatting issue; left untouched."])

    # ------------------------------------------------------------------
    # Cross-column constraints: violations are real, but which side is wrong
    # cannot be proven. Never repaired automatically.
    # ------------------------------------------------------------------

    def _decide_constraint(self, ev: Evidence) -> Decision:
        stats = ev.statistics
        return self._flag_only(
            ev,
            [
                f"'{stats.get('expected_relationship')}' violated by "
                f"{ev.affected_count} row(s).",
                "Repairing requires knowing which column is wrong; both sides "
                "are preserved and the conflict is reported.",
            ],
        )

    # ------------------------------------------------------------------
    # Derived-column consistency: repair ONLY near-exact relationships with
    # an unambiguous formula; weaker coverage is flagged.
    # ------------------------------------------------------------------

    def _decide_derived_column(self, ev: Evidence) -> Decision:
        params_src = ev.statistics
        kind = str(params_src.get("kind", ""))
        coverage = float(params_src.get("coverage", 0.0))

        # Only "violations" kind with high coverage is actionable.
        # "suspicious_partial" and any other/unknown kind are flagged.
        if kind != "violations":
            return self._flag_only(
                ev,
                [
                    f"Derived relationship kind '{kind}' is not actionable "
                    f"(coverage: {coverage:.1%}); flagged for review.",
                ],
            )

        if not self.enable_derived_repair:
            return self._flag_only(
                ev, ["Derived-column repair disabled by configuration."]
            )

        op_map = {
            "sum_offset": ("sum_offset", ["source_a", "source_b", "offset"]),
            "product": ("product", ["source_a", "source_b"]),
            "string_length": ("string_length", ["source"]),
            "day_of_week": ("day_of_week", ["source", "mode"]),
        }
        formula = ev.method
        if formula not in op_map:
            return self._flag_only(ev, ["Unknown derived formula; flagged."])
        op, keys = op_map[formula]
        if any(k not in params_src for k in keys):
            return self._flag_only(ev, ["Incomplete formula evidence; flagged."])

        # Full, UNCAPPED violating-row labels travel via statistics (the
        # evidence's affected_row_indices is a bounded sample).
        violation_labels = list(params_src.get("violation_row_labels", []))
        if not violation_labels:
            return self._skip(ev, ["No violating rows identified."])

        action_params: Dict[str, object] = {"op": op}
        for key in keys:
            action_params[key] = params_src[key]
        action_params["repair_row_labels"] = violation_labels
        if coverage >= DERIVED_EXACT_COVERAGE:
            return Decision(
                evidence=ev,
                verdict="apply",
                action="DerivedColumnRepairAction",
                parameters=action_params,
                reasons=[
                    f"Derived relationship supported by {coverage:.1%} of valid rows.",
                    "Deterministic recalculation restores exact consistency.",
                ],
            )

        return self._flag_only(ev, [f"Derived relationship coverage ({coverage:.1%}) below required threshold.",],)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _decide_constant_fill(
        self, ev: Evidence, profile: ColumnProfile, ratio: float
    ) -> Decision:
        return Decision(
            evidence=ev,
            verdict="apply",
            action="MissingValueAction",
            parameters={
                "strategy": "constant",
                "fill_value": self._constant_value(profile),
            },
            reasons=[
                f"Column is constant ({profile.dominant_share:.0%} of observed "
                f"value(s) identical, {ratio:.1%} missing); filling gaps with "
                "the only observed value."
            ],
        )

    @staticmethod
    def _constant_value(profile: ColumnProfile):
        return profile.top_values[0]["value"] if profile.top_values else None

    def _flag_only(self, ev: Evidence, reasons: List[str]) -> Decision:
        return Decision(evidence=ev, verdict="flag", action=None, reasons=reasons)

    def _skip(self, ev: Evidence, reasons: List[str]) -> Decision:
        return Decision(evidence=ev, verdict="skip", action=None, reasons=reasons)