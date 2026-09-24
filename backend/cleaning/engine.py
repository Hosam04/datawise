"""The DataWise Cleaning Engine orchestrator.

Pipeline (strict separation):

    DATAFRAME
       -> INSPECTION            (read-only)
       -> COLUMN UNDERSTANDING  (read-only)
       -> DETECTORS             (read-only, produce Evidence)
       -> DECISION ENGINE       (read-only, produces Decisions)
       -> ACTIONS               (only place allowed to modify data)
       -> VALIDATION            (real before/after comparison)
       -> PASS -> commit / FAIL -> rollback
       -> CLEANING LOG          (structured record of everything)

The LLM is intentionally absent from this pipeline: cleaning is code-driven
and evidence-driven. Any future LLM reasoning must remain subordinate to
these deterministic safety rules.
"""
import traceback
from typing import Dict, List, Optional, Tuple, Union, Any

import pandas as pd

from backend.cleaning.actions import DEFAULT_ACTIONS
from backend.cleaning.contracts import (
    ActionKind,
    CleaningLogEntry,
    CleaningPolicy,
    CleaningResult,
    ColumnProfile,
    Decision,
    Evidence,
)
from backend.cleaning.decision import DecisionEngine
from backend.cleaning.detectors import (
    BaseDetector,
    CategoricalConsistencyDetector,
    ConstraintDetector,
    DerivedColumnConsistencyDetector,
    DuplicateDetector,
    EncodingArtifactDetector,
    FormattingAnomalyDetector,
    InvalidValueDetector,
    MissingnessPatternDetector,
    MissingValueDetector,
    NearDuplicateDetector,
    OutlierDetector,
    SemanticAnomalyDetector,
    TemporalSanityDetector,
    TypeAnomalyDetector,
    UnitInconsistencyDetector,
)
from backend.cleaning.inspection import (
    build_column_profiles,
    inspect_dataframe,
    profile_lookup,
)
from backend.cleaning.validation import (
    make_snapshot,
    rollback,
    validate_action,
    validate_run,
    verify_rollback,
)
from backend.cleaning.structural import (
    check_structural_integrity,
    check_schema_integrity,
    quick_duplicate_column_check,
)
from backend.cleaning.provenance import (
    chain_log_entries,
    compute_provenance,
    frame_digest,
)
from backend.cleaning.metadata import DatasetRules, apply_rules_to_profiles
from backend.cleaning.contracts import (
    CleaningStrategy as _StrategyModel,
    resolve_strategy,
)
from backend.core.exceptions import CleaningError
from backend.utils.logger import setup_logger


# ===========================================================================
# NEW: General Numeric Protection Logic
# ===========================================================================
NUMERIC_KEYWORDS = {
    'count', 'id', 'num', 'number', 'amount', 'price', 'value',
    'score', 'rate', 'ratio', 'confidence', 'probability', 'percent',
    'pct', 'total', 'sum', 'avg', 'mean', 'min', 'max', 'age',
    'year', 'month', 'day', 'hour', 'minute', 'second', 'duration',
    'size', 'length', 'width', 'height', 'weight', 'distance',
    'latitude', 'longitude', 'coord', 'x', 'y', 'z', 'retweet'
}

def _should_remain_numeric(col_name: str, series: pd.Series) -> bool:
    """Check if a column should remain numeric based on name or content."""
    col_lower = str(col_name).lower()
    
    # Check 1: Name contains numeric keywords
    if any(keyword in col_lower for keyword in NUMERIC_KEYWORDS):
        return True
    
    # Check 2: Content is overwhelmingly numeric (>95%)
    non_null = series.dropna()
    if non_null.empty:
        return False
    
    numeric_converted = pd.to_numeric(non_null, errors='coerce')
    numeric_ratio = numeric_converted.notna().sum() / len(non_null)
    
    return numeric_ratio >= 0.95
# ===========================================================================

def _optimize_dtypes(df: pd.DataFrame, report: Dict[str, Any]) -> pd.DataFrame:
    """Optimize dtypes for storage and model preparation, safely."""
    df = df.copy()
    conversions = []
    target_like = {"target", "label", "class", "survived", "outcome", "response", "y", "prediction", "default", "churn"}

    for col in df.columns:
        s = df[col]
        col_lower = str(col).lower()
        
        # Skip target-like columns from aggressive optimization
        if any(t in col_lower for t in target_like):
            continue

        # 1. Numeric columns: ensure they stay numeric
        if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
            continue
            
        # 2. Boolean columns
        if pd.api.types.is_bool_dtype(s):
            continue
            
        # 3. Datetime columns
        if pd.api.types.is_datetime64_any_dtype(s):
            continue

        # 4. Object/String columns: the danger zone for silent reclassification
        if pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s):
            
            # >>> FIX APPLIED HERE <<<
            if _should_remain_numeric(col, s):
                df[col] = pd.to_numeric(s, errors='coerce')
                conversions.append((col, str(df[col].dtype)))
                continue

            # Original low-cardinality categorization logic
            unique = s.nunique(dropna=True)
            if unique > 0 and unique <= min(50, max(10, int(len(df) * 0.10))):
                df[col] = s.astype("category")
                conversions.append((col, "category"))

    if conversions:
        report["cleaning_steps"].append({
            "step": "dtype_optimization",
            "conversions": [{"column": c, "new_dtype": d} for c, d in conversions]
        })
        
    return df

def _state_summary(df: pd.DataFrame) -> Dict:
    """Compact fingerprint of a DataFrame state for log entries."""
    return {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "missing_cells": int(df.isna().sum().sum()),
        "duplicate_rows": int(df.duplicated().sum()),
    }


def _assess(result: "CleaningResult") -> str:
    """Overall evidence-based verdict for the run (never a cleanliness
    claim without evidence)."""
    if result.blocked:
        return "BLOCKED"
    if result.errors or any(e.rolled_back for e in result.log):
        return "NEEDS REVIEW"

    high = medium = low = 0
    for d in result.decisions:
        if d.verdict != "flag":
            continue
        if d.evidence.severity == "high":
            high += 1
        elif d.evidence.severity == "medium":
            medium += 1
        else:
            low += 1

    if high:
        return "NEEDS CLEANING"
    if medium or result.information_loss_warnings:
        return "NEEDS REVIEW"
    if low:
        return "MOSTLY CLEAN"
    return "CLEAN"


class CleaningEngine:
    """Conservative, evidence-driven, dataset-agnostic cleaning pipeline."""

    def __init__(
        self,
        enable_imputation: bool = True,
        enable_duplicate_removal: bool = True,
        add_outlier_flags: bool = True,
        outlier_threshold: float = 1.5,
        detectors: Optional[List[BaseDetector]] = None,
        rules: Optional["DatasetRules"] = None,
        policy: Optional[CleaningPolicy] = None,
        strategy: Optional[Union[str, "_StrategyModel"]] = None,
    ):
        self.config = {
            "enable_imputation": enable_imputation,
            "enable_duplicate_removal": enable_duplicate_removal,
            "add_outlier_flags": add_outlier_flags,
            "outlier_threshold": outlier_threshold,
        }
        self.rules = rules
        self.requested_strategy = strategy
        self.policy = policy or CleaningPolicy(
            enable_imputation=enable_imputation,
            enable_duplicate_removal=enable_duplicate_removal,
            add_outlier_flags=add_outlier_flags,
        )
        self.detectors: List[BaseDetector] = detectors if detectors is not None else [
            # Phase-1 detectors (evidence describes the input state).
            MissingValueDetector(
                extra_suppression_tokens=(
                    list(rules.suppression_tokens) if rules else []
                )
            ),
            DuplicateDetector(),
            InvalidValueDetector(),
            TypeAnomalyDetector(),
            FormattingAnomalyDetector(),
            MissingnessPatternDetector(),
            DerivedColumnConsistencyDetector(),
            ConstraintDetector(
                extra_pairs=list(rules.constraint_pairs) if rules else []
            ),
            SemanticAnomalyDetector(),
            NearDuplicateDetector(),
            EncodingArtifactDetector(),
            TemporalSanityDetector(),
            UnitInconsistencyDetector(),
            # Deferred detectors: re-run AFTER mutation actions commit so
            # their findings describe the final state.
            OutlierDetector(threshold=outlier_threshold),
            CategoricalConsistencyDetector(),
        ]
        self.decider = DecisionEngine(
            policy=self.policy,
        )
        self.actions = dict(DEFAULT_ACTIONS)
        self.logger = setup_logger("CleaningEngine")

    def register_action(self, name: str, action) -> None:
        """Register an executor under `name`. The action should expose a
        spec attribute (ActionSpec) so budgets classify it correctly."""
        self.actions[name] = action

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, CleaningResult]:
        """Execute the full pipeline. Returns (cleaned_df, structured_result)."""
        if not isinstance(df, pd.DataFrame):
            raise TypeError("CleaningEngine.run expects a pandas DataFrame.")

        result = CleaningResult()

        # Empty / degenerate datasets are returned untouched: there is no
        # evidence to justify any modification.
        if df.empty or len(df.columns) == 0:
            result.inspection = inspect_dataframe(df)
            return df.copy(), result

        # 0a. Index bookkeeping BEFORE anything reads positional data:
        # non-unique labels would make label-based repairs ambiguous.
        # Index-only operation; no cell value is touched.
        if not isinstance(df.index, pd.RangeIndex) or not df.index.is_unique:
            df = df.reset_index(drop=True)
            result.structural_findings.append({
                "check": "index_normalized",
                "severity": "info",
                "column": None,
                "affected_count": int(len(df)),
                "details": {
                    "reason": (
                        "Non-canonical or duplicate index labels were "
                        "reset before cleaning to keep row addressing "
                        "unambiguous. No cell values changed."
                    ),
                },
            })

        # 0a'. Duplicate column labels guard BEFORE inspection/profiles:
        # label-based iteration is ambiguous (and can crash) under
        # duplication. This must precede inspect_dataframe().
        dupe_finding = quick_duplicate_column_check(df)
        if dupe_finding is not None:
            result.structural_findings.append(dict(dupe_finding))
            result.blocked = True
            result.success = False
            result.assessment = _assess(result)
            result.decisions.append(Decision(
                evidence=Evidence(
                    detector="SchemaIntegrityChecker",
                    problem_type="structural",
                    column=dupe_finding.get("column"),
                    method=str(dupe_finding.get("check")),
                    affected_count=int(dupe_finding.get("affected_count", 0)),
                    statistics=dict(dupe_finding.get("details", {})),
                    confidence=1.0,
                    severity="high",
                    explanation=str(
                        dupe_finding.get("details", {}).get("reason", "")
                    ),
                ),
                verdict="block",
                reasons=[
                    "Duplicate column labels detected; speculative repair "
                    "is forbidden. Dataset returned UNCHANGED."
                ],
            ))
            self.logger.error(
                "Cleaning BLOCKED: duplicate column labels (%s). No "
                "modifications performed.",
                dupe_finding.get("column"),
            )
            return df.copy(), result

        # 1-2. Inspection + column understanding (read-only), then merge any
        # caller-declared metadata into the profiles so detectors consume
        # explicit domain knowledge instead of guessing.
        inspection = inspect_dataframe(df)
        profiles: List[ColumnProfile] = build_column_profiles(df)
        apply_rules_to_profiles(profiles, self.rules)
        profiles_by_name = profile_lookup(profiles)
        result.inspection = inspection
        result.column_profiles = profiles

        # Strategy resolution (Phase 9): deterministic orchestration based
        # on the actual dataset size and any explicit request.
        try:
            self.strategy = resolve_strategy(
                self.requested_strategy, inspection.rows, inspection.column_count
            )
        except ValueError as exc:
            raise CleaningError(str(exc)) from exc
        result.strategy = self.strategy.name
        result.strategy_plan = {
            "strategy": self.strategy.name,
            "rows": inspection.rows,
            "columns": inspection.column_count,
            "max_numeric_pair_cols": self.strategy.max_numeric_pair_cols,
            "max_corr_rows": self.strategy.max_corr_rows,
            "detection_enabled": self.strategy.enable_detection,
        }

        # Provenance baselines: post-normalization input state + governing
        # policy/rules, captured before any integrity gate can short-circuit.
        result.input_digest = frame_digest(df)
        result.output_digest = result.input_digest  # overwritten on commit
        result.chain_root = "0" * 64                # genesis for blocked runs
        result.policy_snapshot = self.policy.model_dump(mode="json")
        result.rules_snapshot = (
            self.rules.model_dump(mode="json") if self.rules else {}
        )

        # 0. INPUT / STRUCTURAL INTEGRITY (read-only, before any cleaning).
        # Corruption that destroys trust in row alignment BLOCKS the run:
        # the dataset is returned untouched rather than "cleaned" on top of
        # broken structure.
        structural_findings = check_structural_integrity(
            df, profiles_by_name, inspection
        )
        result.structural_findings.extend(
            dict(f) for f in structural_findings
        )
        blocking = [f for f in structural_findings if f.get("severity") == "block"]
        for finding in structural_findings:
            self.logger.warning(
                "STRUCTURAL %s | check=%s | column=%s | rows=%d",
                finding.get("severity", "flag").upper(),
                finding.get("check"),
                finding.get("column"),
                finding.get("affected_count", 0),
            )
        if blocking:
            result.blocked = True
            result.success = False
            result.assessment = _assess(result)
            for finding in blocking:
                result.decisions.append(Decision(
                    evidence=Evidence(
                        detector="StructuralIntegrityChecker",
                        problem_type="structural",
                        column=finding.get("column"),
                        method=str(finding.get("check")),
                        affected_count=int(finding.get("affected_count", 0)),
                        statistics=dict(finding.get("details", {})),
                        confidence=1.0,
                        severity="high",
                        explanation=str(
                            finding.get("details", {}).get("reason", "")
                        ),
                    ),
                    verdict="block",
                    reasons=[
                        "Structural corruption detected; speculative repair "
                        "is forbidden. Dataset returned UNCHANGED."
                    ],
                ))
            self.logger.error(
                "Cleaning BLOCKED: %d structural finding(s) make the "
                "dataset untrustworthy (%s). No modifications performed.",
                len(blocking),
                ", ".join(f.get("check", "?") for f in blocking),
            )
            return df.copy(), result

        # 0b. Post-parse SCHEMA integrity (DataFrame level, read-only).
        # Duplicate labels or a misaligned header make safe cleaning
        # impossible -> BLOCK. Everything else is recorded as evidence.
        # Extends (never replaces) the raw-text findings above.
        schema_findings = check_schema_integrity(
            df, profile_lookup(profiles), inspection
        )

        result.structural_findings.extend(
            dict(f) for f in schema_findings
        )
        blocking = [f for f in schema_findings
                    if f.get("severity") == "block"]
        for finding in schema_findings:
            if finding.get("severity") in ("block", "flag"):
                self.logger.warning(
                    "SCHEMA %s | check=%s | column=%s | rows=%d",
                    str(finding.get("severity")).upper(),
                    finding.get("check"),
                    finding.get("column"),
                    finding.get("affected_count", 0),
                )
        if blocking:
            result.blocked = True
            result.success = False
            result.assessment = _assess(result)
            for finding in blocking:
                result.decisions.append(Decision(
                    evidence=Evidence(
                        detector="SchemaIntegrityChecker",
                        problem_type="structural",
                        column=finding.get("column"),
                        method=str(finding.get("check")),
                        affected_count=int(finding.get("affected_count", 0)),
                        statistics=dict(finding.get("details", {})),
                        confidence=1.0,
                        severity="high",
                        explanation=str(
                            finding.get("details", {}).get("reason", "")
                        ),
                    ),
                    verdict="block",
                    reasons=[
                        "Schema corruption detected; speculative repair is "
                        "forbidden. Dataset returned UNCHANGED."
                    ],
                ))
            self.logger.error(
                "Cleaning BLOCKED: %d schema finding(s) make the dataset "
                "untrustworthy (%s). No modifications performed.",
                len(blocking),
                ", ".join(f.get("check", "?") for f in blocking),
            )
            return df.copy(), result

        # Scale caps (Phase 9): apply strategy bounds to the expensive
        # scanners owned by this engine instance.
        if self.strategy.max_numeric_pair_cols is not None:
            for det in self.detectors:
                if isinstance(det, DerivedColumnConsistencyDetector):
                    det.max_numeric_pair_cols = self.strategy.max_numeric_pair_cols
        if self.strategy.max_corr_rows is not None:
            for det in self.detectors:
                if isinstance(det, SemanticAnomalyDetector):
                    det.max_corr_rows = self.strategy.max_corr_rows

        # 3. Detection phase 1 (read-only evidence on the input state).
        #    Detectors whose evidence must describe the FINAL state (e.g.
        #    outlier fences) are deferred until after mutation actions.
        deferred_detectors = [d for d in self.detectors if d.rerun_after_actions]
        active_detectors = [d for d in self.detectors if not d.rerun_after_actions]

        evidence: List[Evidence] = []
        decisions: List[Decision] = []
        counters = {"per_column": {}, "total": 0}
        working = df.copy()

        if self.strategy.enable_detection:
            for detector in active_detectors:
                try:
                    found = detector.detect(df, profiles_by_name, inspection)
                except Exception as exc:
                    self.logger.exception(
                        "CLEANING DETECTOR FAILED: %s",
                        detector.__class__.__name__,
                    )
                    raise
                
                self.logger.info(
                    "%s produced %d evidence item(s).",
                    detector.name,
                    len(found),
                )
                for ev in found:
                    self.logger.info(
                        "  finding | issue=%s | column=%s | rows=%d | severity=%s | confidence=%.2f | %s",
                        ev.problem_type,
                        ev.column or "<dataset>",
                        ev.affected_count,
                        ev.severity,
                        ev.confidence,
                        ev.method,
                    )
                evidence.extend(found)

            # 4. Decisions (safety gate, read-only).
            decisions = []
            for ev in evidence:
                # On multi-valued categorical columns, whitespace normalization
                # and categorical canonicalization are the same logical
                # mutation. Let the deferred categorical detector own that
                # mutation so the per-column budget cannot block the canonical
                # mapping after formatting runs first. Constant categorical
                # columns still use the formatting action directly.
                if (
                    ev.problem_type == "formatting"
                    and ev.method == "whitespace_normalization"
                    and ev.column in profiles_by_name
                    and profiles_by_name[ev.column].semantic_type == "categorical"
                    and not profiles_by_name[ev.column].constant
                ):
                    decision = Decision(
                        evidence=ev,
                        verdict="skip",
                        action=None,
                        reasons=[
                            "Deferred to CategoricalConsistencyDetector so "
                            "case/whitespace variants are normalized in one "
                            "deterministic action without consuming two mutation-budget slots."
                        ],
                    )
                else:
                    decision = self.decider.decide(
                        ev, profiles_by_name, inspection, df
                    )
                decisions.append(decision)
            result.decisions = decisions
            for decision in decisions:
                self._log_decision(decision)

            # 5-6. Execute approved/annotating actions with snapshot -> validate
            #      -> commit / rollback. Budgets are enforced per column and
            #      globally for content-mutating actions.
            for decision in decisions:
                working = self._process_decision(
                    decision, working, counters, result
                )
        else:
            result.strategy_plan["note"] = (
                "structure_only: semantic detection and cleaning actions "
                "skipped by strategy."
            )

        # 3b. Detection phase 2: fresh evidence on the mutated state so
        #     annotations never reference stale statistics. Skipped entirely
        #     under structure_only (no actions ran, nothing went stale).
        if self.strategy.enable_detection:
            for detector in deferred_detectors:
                current_inspection = inspect_dataframe(working)
                current_profiles = profile_lookup(build_column_profiles(working))
                try:
                    found = detector.detect(
                        working,
                        current_profiles,
                        current_inspection,
                    )
                except Exception as exc:
                    self.logger.exception(
                        "CLEANING DETECTOR FAILED (post-action): %s",
                        detector.__class__.__name__,
                    )
                    raise
                
                self.logger.info(
                    "%s (post-action) produced %d evidence item(s).",
                    detector.name,
                    len(found),
                )
                for ev in found:
                    decision = self.decider.decide(
                        ev,
                        current_profiles,
                        current_inspection,
                        working,
                    )
                    result.decisions.append(decision)
                    self._log_decision(decision, post_action=True)
                    working = self._process_decision(
                        decision, working, counters, result
                    )

        # Index normalization bookkeeping (matches the historical behaviour of
        # tools/cleaner.py which always emitted a clean RangeIndex).
        working = working.reset_index(drop=True)

        # 8. Provenance & audit trail: chain the log, digest the output,
        # and attach the full provenance block.
        chain_log_entries(result.log)
        result.output_digest = frame_digest(working)
        result.chain_root = (
            result.log[-1].entry_hash if result.log else "0" * 64
        )
        prov = compute_provenance(
            result.input_digest,
            result.output_digest,
            result.policy_snapshot,
            result.rules_snapshot,
            result.log,
        )
        result.chain_root = prov["chain_root"]

        # Information-loss audit aggregation: approved imputations that
        # create artificial dominant values are reported, never hidden.
        for entry in result.log:
            if not entry.applied:
                continue
            validation = entry.validation
            if validation is None:
                continue
            loss = validation.summary.get("information_loss")
            if isinstance(loss, dict) and loss.get("warning"):
                result.information_loss_warnings.append(str(loss["warning"]))
                self.logger.warning("INFORMATION LOSS | %s", loss["warning"])

        # 7. Whole-run validation: aggregate accounting between the ORIGINAL
        # input and the FINAL output. Any unexplained delta is an error.
        run_report = validate_run(df, working, result)
        result.run_validation = run_report
        for failure in run_report.get("failures", []):
            result.errors.append(f"Run validation: {failure}")
            self.logger.error("RUN VALIDATION | %s", failure)
        if run_report.get("failures"):
            result.success = False

        result.assessment = _assess(result)
        self.logger.info(
            "Assessment: %s (decisions=%d, applied=%d, flagged=%d)",
            result.assessment,
            len(result.decisions),
            sum(1 for e in result.log if e.applied),
            len(result.flagged_issues),
        )

        return working, result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _process_decision(
        self,
        decision: Decision,
        working: pd.DataFrame,
        counters: Dict,
        result: CleaningResult,
    ) -> pd.DataFrame:
        """Route one decision through budget gates, execute it, and update
        the run result. Returns the (possibly unchanged) working frame."""
        if not decision.action:
            if decision.verdict == "flag":
                result.flagged_issues.append(decision.evidence)
            return working

        action = self.actions.get(decision.action)
        if action is None:
            result.errors.append(
                f"No executor registered for action '{decision.action}'."
            )
            return working

        # Mutation-budget gate: content-mutating actions only, classified
        # by the action's own spec (annotation/row-removal semantics differ).
        is_content_mutation = (
            getattr(action, "spec", None) is not None
            and action.spec.kind == ActionKind.CONTENT
        )
        if decision.verdict == "apply" and is_content_mutation:
            col_key = decision.evidence.column or "<dataset>"
            used = counters["per_column"].get(col_key, 0)
            over_column = used >= self.policy.max_mutations_per_column
            over_total = (
                self.policy.max_total_mutations is not None
                and counters["total"] >= self.policy.max_total_mutations
            )
            if over_column or over_total:
                withheld = decision.action
                decision.policy_checks.append({
                    "rule": "mutation_budget",
                    "passed": False,
                    "detail": (
                        f"column '{col_key}' used {used} of "
                        f"{self.policy.max_mutations_per_column}"
                        + (
                            f"; total {counters['total']} of "
                            f"{self.policy.max_total_mutations}"
                            if over_total else ""
                        )
                    ),
                })
                decision.verdict = "flag"
                decision.action = None
                decision.reasons.append(
                    f"Mutation budget exhausted; '{withheld}' was withheld "
                    "and the finding is flagged for review."
                )
                result.flagged_issues.append(decision.evidence)
                self.logger.warning(
                    "BUDGET | action %s on '%s' withheld (%s).",
                    withheld, col_key, decision.reasons[-1],
                )
                return working

        entry, working = self._execute(action, working, decision, result)
        result.log.append(entry)
        if entry.applied and (
            getattr(action, "spec", None) is not None
            and action.spec.kind == ActionKind.CONTENT
        ):
            col_key = decision.evidence.column or "<dataset>"
            counters["per_column"][col_key] = (
                counters["per_column"].get(col_key, 0) + 1
            )
            counters["total"] += 1
        if entry.error or entry.rolled_back:
            result.success = False
        return working

    def _log_decision(self, decision: Decision, post_action: bool = False) -> None:
        ev = decision.evidence
        self.logger.info(
            "decision | issue=%s | column=%s | verdict=%s | action=%s%s",
            ev.problem_type,
            ev.column or "<dataset>",
            decision.verdict,
            decision.action or "-",
            " | phase=post-action" if post_action else "",
        )

    def _execute(
        self,
        action,
        working: pd.DataFrame,
        decision: Decision,
        result: CleaningResult,
    ) -> Tuple[CleaningLogEntry, pd.DataFrame]:
        """snapshot -> action -> validation -> commit / rollback."""
        ev = decision.evidence
        entry = CleaningLogEntry(
            action=decision.action or "",
            decision_verdict=decision.verdict,
            problem_type=ev.problem_type,
            column=ev.column,
            detector=ev.detector,
            method=ev.method,
            confidence=ev.confidence,
            reasons=list(decision.reasons),
        )

        snapshot = make_snapshot(working)
        entry.before_state = _state_summary(snapshot)

        try:
            candidate, info = action.apply(working, decision)
        except Exception as exc:  # noqa: BLE001 - contained & logged, never silent
            entry.applied = False
            entry.rolled_back = True
            entry.error = f"{type(exc).__name__}: {exc}"
            entry.after_state = entry.before_state
            self.logger.warning(
                "Action %s failed (%s); rollback to pre-action state.",
                entry.action,
                entry.error,
            )
            restored = rollback(snapshot)
            mismatch = verify_rollback(restored, snapshot)
            entry.rollback_verified = mismatch is None
            if mismatch is not None:
                self.logger.error(
                    "ROLLBACK VERIFICATION FAILED after %s: %s",
                    entry.action, mismatch,
                )
                result.errors.append(
                    f"Rollback verification failed: {mismatch}"
                )
            return entry, restored

        validation = validate_action(snapshot, candidate, decision, info, action)
        entry.validation = validation
        entry.rows_affected = int(info.get("rows_affected", 0))
        entry.cells_changed = int(info.get("cells_changed", 0))
        entry.columns_touched = list(info.get("columns_touched", []))
        entry.changes = list(info.get("changes", []))
        entry.inverse = list(info.get("inverse", []))

        if validation.passed:
            entry.applied = True
            entry.after_state = _state_summary(candidate)
            self.logger.info(
                "Action %s on '%s' committed (%d row(s) affected).",
                entry.action,
                entry.column,
                entry.rows_affected,
            )
            return entry, candidate

        entry.applied = False
        entry.rolled_back = True
        entry.error = "; ".join(validation.failures)
        entry.after_state = entry.before_state
        self.logger.warning(
            "Action %s FAILED validation (%s); rollback to pre-action state.",
            entry.action,
            entry.error,
        )
        restored = rollback(snapshot)
        mismatch = verify_rollback(restored, snapshot)
        entry.rollback_verified = mismatch is None
        if mismatch is not None:
            self.logger.error(
                "ROLLBACK VERIFICATION FAILED after %s: %s",
                entry.action, mismatch,
            )
            result.errors.append(f"Rollback verification failed: {mismatch}")
        return entry, restored