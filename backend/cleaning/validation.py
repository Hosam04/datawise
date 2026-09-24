"""Real validation for applied cleaning actions.

Validation compares the ACTUAL before/after states — row counts, column
sets, schemas, dtypes, missingness and cell-level content — against a
deterministically recomputed expected result. An operation is successful
only when validation passes, never merely because no exception occurred.
"""
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from backend.cleaning.contracts import (
    INFO_LOSS_MODE_SHARE,
    Decision,
    ValidationResult,
)

# Class-level expectation registry: custom action classes may register a
# deterministic expected-frame builder without touching engine code.
_EXPECTATION_REGISTRY: Dict[str, Any] = {}


def register_expectation(action_name: str, expected_frame_fn):
    """Register `expected_frame_fn(before, decision, info) -> DataFrame`
    for `action_name`. Registered expectations are consulted when the
    action instance itself provides no `expected_frame` hook."""
    _EXPECTATION_REGISTRY[str(action_name)] = expected_frame_fn


def clear_registered_expectations() -> None:
    _EXPECTATION_REGISTRY.clear()


def verify_rollback(restored: pd.DataFrame, snapshot: pd.DataFrame) -> Optional[str]:
    """Verify a restored frame equals the pre-action snapshot.

    Returns None when equal, else a precise failure description.
    """
    if len(restored) != len(snapshot):
        return f"Row count differs after rollback: {len(snapshot)} -> {len(restored)}"
    if list(map(str, restored.columns)) != list(map(str, snapshot.columns)):
        return "Column set differs after rollback."
    for col in snapshot.columns:
        left = snapshot[col]
        right = restored[col]
        if left.dtype != right.dtype:
            return f"Dtype of '{col}' changed after rollback."
        if int(left.isna().sum()) != int(right.isna().sum()):
            return f"Missingness of '{col}' changed after rollback."
        try:
            pd.testing.assert_series_equal(left, right, check_names=False)
        except AssertionError:
            return f"Values of '{col}' differ after rollback."
    return None


def make_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    """Deep copy used as the reliable rollback baseline."""
    return df.copy(deep=True)


def rollback(snapshot: pd.DataFrame) -> pd.DataFrame:
    """Return an independent copy of the stored pre-action state."""
    return snapshot.copy(deep=True)


def validate_action(
    before: pd.DataFrame,
    after: pd.DataFrame,
    decision: Decision,
    info: Dict,
    action_obj=None,
) -> ValidationResult:
    """Validate ONE applied action against its approved parameters.

    `action_obj` may carry an `expected_frame(before, decision, info)`
    implementation for custom registered actions.
    """
    result = ValidationResult()
    action = decision.action or ""
    problem = decision.evidence.problem_type
    column = decision.evidence.column

    # --- structural checks -------------------------------------------------
    expected_rows = _expected_row_count(before, decision)
    result.record(
        "row_count",
        len(after) == expected_rows,
        f"Row count changed unexpectedly: {len(before)} -> {len(after)} "
        f"(expected {expected_rows}).",
    )

    allowed_new = {
        str(c) for c in info.get("columns_touched", []) if c not in before.columns
    }
    unexpected_cols = [
        c for c in after.columns if c not in before.columns and str(c) not in allowed_new
    ]

    # >>> FIX: Allow dropped columns if the action is DropColumnAction <<<
    is_drop_action = (action == "DropColumnAction")
    dropped_cols = [c for c in before.columns if c not in after.columns]
    expected_dropped = dropped_cols if is_drop_action else []

    result.record(
        "column_set",
        not unexpected_cols and (dropped_cols == expected_dropped),
        (
            f"Unexpected schema change. Added: {unexpected_cols}; "
            f"dropped: {dropped_cols}."
        ),
    )

    # --- intended change really happened -----------------------------------
    # >>> FIX: Skip missing_values check for DropColumnAction to avoid KeyError <<<
    if problem == "missing_values" and column is not None and action != "DropColumnAction":
        from backend.core.constants import missing_equivalent_mask
        fill_value = decision.parameters.get("fill_value")
        before_nulls = int(missing_equivalent_mask(before[column]).sum())
        after_nulls = int(
            missing_equivalent_mask(after[column], exclude_values=[fill_value]).sum()
        )
        intended_reduction = int(info.get("cells_changed", 0))
        result.record(
            "intended_change",
            (
                before_nulls - after_nulls == intended_reduction
                and after_nulls < before_nulls
            ),
            (
                f"Missing cells in '{column}' did not decrease by the intended "
                f"{intended_reduction} (before={before_nulls}, after={after_nulls})."
            ),
        )
        # Other columns must keep their own missingness untouched.
        others_unchanged = True
        for other in before.columns:
            if other == column or str(other) not in after.columns:
                continue
            if int(missing_equivalent_mask(before[other]).sum()) != int(
                missing_equivalent_mask(after[other]).sum()
            ):
                others_unchanged = False
                break
        result.record(
            "collateral_missingness",
            others_unchanged,
            "Missingness of unrelated columns changed.",
        )

        # Information-loss audit: a single invented value dominating the
        # column afterwards (e.g. 177 missing ages all becoming 28.0) is a
        # suspicious transformation even when the imputation was approved.
        # Only warn when the fill *materially increases* the dominance of
        # that value (not when it was already the majority class).
        strategy = decision.parameters.get("strategy")
        fill_value = decision.parameters.get("fill_value")
        if strategy in ("median", "constant", "mode") and fill_value is not None:
            post = after[column]
            pre = before[column]
            pre_obs = ~missing_equivalent_mask(pre)
            post_obs = ~missing_equivalent_mask(post, exclude_values=[fill_value])
            post_non_null = int(post_obs.sum())
            pre_non_null = int(pre_obs.sum())
            if post_non_null and pre_non_null:
                post_share = float(
                    (post.astype("string") == str(fill_value)).sum() / post_non_null
                )
                pre_share = float(
                    (pre[pre_obs].astype("string") == str(fill_value)).sum()
                    / pre_non_null
                )
                share_increase = post_share - pre_share
                # Warn only if the value dominates after fill AND the
                # imputation itself contributed a meaningful increase.
                if (
                    post_share >= INFO_LOSS_MODE_SHARE
                    and share_increase >= 0.05
                ):
                    result.summary["information_loss"] = {
                        "column": str(column),
                        "dominant_value": str(fill_value),
                        "dominant_share_after": round(post_share, 4),
                        "dominant_share_before": round(pre_share, 4),
                        "warning": (
                            f"After imputation {post_share:.0%} of "
                            f"'{column}' holds the single invented value "
                            f"{fill_value} (was {pre_share:.0%} before); "
                            "treat downstream statistics with caution."
                        ),
                    }

    elif problem == "duplicates":
        remaining_dupes = int(after.duplicated().sum())
        result.record(
            "intended_change",
            remaining_dupes == 0,
            f"{remaining_dupes} duplicate row(s) remain after removal.",
        )
        excluded_columns = set(decision.parameters.get("excluded_columns", []))
        subset = [c for c in before.columns if c not in excluded_columns] or None
        try:
            merged = after.merge(
                before.drop_duplicates(subset=subset), how="left", indicator=True
            )
            result.record(
                "row_integrity",
                bool((merged["_merge"] == "both").all()) and len(merged) == len(after),
                "Some surviving rows do not match any original row.",
            )
        except (pd.errors.MergeError, ValueError):
            result.record(
                "row_integrity",
                False,
                "Row-integrity check could not be computed.",
            )

    elif problem == "categorical_consistency" and column is not None:
        mapping = decision.parameters.get("mapping") or {}
        nulls_preserved = int(before[column].isna().sum()) == int(
            after[column].isna().sum()
        )
        result.record(
            "nulls_preserved",
            nulls_preserved,
            f"Categorical normalization changed the null count of '{column}'.",
        )
        remaining_variants = set(mapping.keys()) & set(
            after[column].dropna().astype(str)
        )
        result.record(
            "intended_change",
            not remaining_variants,
            f"Variant value(s) still present after normalization: "
            f"{sorted(remaining_variants)}",
        )

    elif problem == "formatting" and column is not None and column in before.columns:
        residual_ws = int(
            after[column]
            .astype("string")
            .str.contains(r"^\s|\s$|\s{2,}", regex=True, na=False)
            .sum()
        )
        result.record(
            "intended_change",
            residual_ws == 0,
            f"{residual_ws} value(s) in '{column}' still carry stray whitespace.",
        )
        content_preserved = (
            after[column].astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
            == after[column].astype("string")
        ).all()
        result.record(
            "content_preserved",
            bool(content_preserved),
            "Formatting changed non-whitespace content.",
        )

    elif problem == "derived_column" and column is not None:
        params = decision.parameters
        labels = list(params.get("repair_row_labels", []))
        if not labels:
            result.record("intended_change", False, "No repair rows were provided.")
        else:
            src_ok = all(
                str(params[key]) in after.columns
                for key in ("source_a", "source_b", "source")
                if key in params
            )
            repaired = after.loc[after.index.isin(labels), column]
            recomputed_ok = True
            if params.get("op") == "string_length":
                expected_vals = before.loc[
                    before.index.isin(labels), str(params["source"])
                ].astype("string").str.len()
                recomputed_ok = bool(
                    (pd.Series(repaired.values) == pd.Series(expected_vals.values)).all()
                )
            result.record(
                "intended_change",
                bool(src_ok) and len(repaired) == len(labels) and recomputed_ok,
                "Derived-column repair did not recompute exactly the approved rows.",
            )

    elif problem == "outliers":
        flag_col = info.get("flag_column")
        present = flag_col in after.columns if flag_col else False
        result.record(
            "intended_change",
            present,
            f"Expected annotation column '{flag_col}' was not created.",
        )
        if present:
            values = pd.to_numeric(before[column], errors="coerce")
            lower = decision.parameters.get("lower_bound")
            upper = decision.parameters.get("upper_bound")
            expected_mask = ((values < lower) | (values > upper)).fillna(False)
            # Compare as int arrays: dtype-insensitive (nullable boolean vs
            # numpy bool would otherwise produce false mismatches).
            expected_arr = expected_mask.astype("int8").to_numpy()
            actual_arr = after[flag_col].astype("int8").to_numpy()
            result.record(
                "flag_correctness",
                bool((expected_arr == actual_arr).all()),
                f"'{flag_col}' does not mark exactly the approved fence bounds.",
            )

    # --- exact expected-frame comparison ------------------------------------
    expected = None
    if action_obj is not None and hasattr(action_obj, "expected_frame"):
        # Custom registered actions may supply their own deterministic
        # expectation; it must still match the after-state exactly.
        try:
            expected = action_obj.expected_frame(before, decision, info)
        except Exception as exc:  # noqa: BLE001 - surfaced as failure
            result.record(
                "matches_expected", False,
                f"Action-provided expectation raised: {exc}",
            )
    if expected is None:
        expected = _expected_frame(before, decision, info)

    if expected is not None:
        diff_message = _frame_difference(before, after, expected, column)
        result.record(
            "matches_expected",
            diff_message is None,
            diff_message or "",
        )
        result.summary["validated_against"] = action
    else:
        spec = getattr(action_obj, "spec", None)
        if getattr(spec, "self_validating", False):
            result.record("matches_expected", True, "")
            result.summary["validated_against"] = "self_validating"
        else:
            result.record(
                "matches_expected",
                False,
                f"No deterministic expectation available for action '{action}'.",
            )

    return result


# ---------------------------------------------------------------------------
# Deterministic expectations (mirror of each action's contract)
# ---------------------------------------------------------------------------

def _expected_row_count(before: pd.DataFrame, decision: Decision) -> int:
    if decision.evidence.problem_type == "duplicates":
        removed = int(decision.parameters.get("rows_to_remove", 0))
        return len(before) - removed
    return len(before)


def _expected_frame(
    before: pd.DataFrame, decision: Decision, info: Dict
) -> Optional[pd.DataFrame]:
    action = decision.action or ""

    if action == "MissingValueAction":
        from backend.core.constants import missing_equivalent_mask
        column = decision.evidence.column
        fill_value = decision.parameters.get("fill_value")
        if decision.parameters.get("strategy") == "explicit_unknown_category":
            from backend.cleaning.contracts import UNKNOWN_CATEGORY_LABEL
            fill_value = UNKNOWN_CATEGORY_LABEL
        expected = before.copy()
        col_series = expected[column]
        if isinstance(col_series.dtype, pd.CategoricalDtype):
            if fill_value not in col_series.cat.categories:
                col_series = col_series.cat.add_categories([fill_value])
        mask = missing_equivalent_mask(col_series, exclude_values=[fill_value])
        col_series = col_series.copy()
        col_series.loc[mask] = fill_value
        expected[column] = col_series
        return expected

    # >>> FIX: Add expectation for DropColumnAction <<<
    if action == "DropColumnAction":
        column = decision.parameters.get("column") or decision.evidence.column
        expected = before.drop(columns=[column], errors="ignore")
        return expected
    # >>> END FIX <<<

    if action == "HTMLDecodingAction":
        import html as html_module
        column = decision.parameters.get("column") or decision.evidence.column
        expected = before.copy()
        def _decode(value):
            if pd.isna(value):
                return value
            try:
                return html_module.unescape(str(value))
            except Exception:
                return value
        expected[column] = expected[column].apply(_decode)
        return expected

    if action == "CoordinateValidatorAction":
        column = decision.parameters.get("column") or decision.evidence.column
        invalid_values = set(decision.parameters.get("invalid_values", []))
        expected = before.copy()
        mask = expected[column].astype(str).str.strip().isin(invalid_values)
        expected.loc[mask, column] = np.nan
        return expected

    if action == "DuplicateRemovalAction":
        keep = decision.parameters.get("keep", "first")
        excluded_columns = set(decision.parameters.get("excluded_columns", []))
        subset = [c for c in before.columns if c not in excluded_columns] or None
        return before.drop_duplicates(subset=subset, keep=keep)
    
    if action == "OutlierFlagAction":
        column = decision.evidence.column
        lower = decision.parameters.get("lower_bound")
        upper = decision.parameters.get("upper_bound")
        flag_col = info.get("flag_column") or f"{column}_OutlierFlag"
        values = pd.to_numeric(before[column], errors="coerce")
        mask = ((values < lower) | (values > upper)).fillna(False)
        expected = before.copy()
        expected[flag_col] = mask.astype(bool).astype("int8")
        return expected

    if action == "CategoricalNormalizationAction":
        column = decision.evidence.column
        mapping = decision.parameters.get("mapping") or {}
        expected = before.copy()
        mask = before[column].notna() & before[column].astype(str).isin(mapping.keys())
        expected.loc[mask, column] = before[column][mask].map(mapping)
        return expected

    if action == "FormattingNormalizationAction":
        column = decision.evidence.column
        expected = before.copy()
        expected[column] = (
            before[column]
            .astype("string")
            .str.strip()
            .str.replace(r"\s+", " ", regex=True)
        )
        return expected

    if action == "TypeNormalizationAction":
        column = decision.evidence.column
        normalization = decision.parameters.get("normalization")
        expected = before.copy()
        if normalization == "remove_currency_separators_and_accounting_parentheses":
            normalized = (
                before[column].astype("string")
                .str.strip()
                .str.replace(r"[\$€£¥,%]", "", regex=True)
                .str.replace(r"^\((.*)\)$", r"-\1", regex=True)
                .str.replace(",", "", regex=False)
            )
            expected[column] = pd.to_numeric(normalized, errors="coerce")
        elif normalization == "to_datetime":
            expected[column] = pd.to_datetime(before[column], errors="coerce", format="mixed")
        elif normalization == "parse_coordinate":
            expected[column] = pd.to_numeric(
                before[column].astype("string").str.strip(), errors="coerce"
            )
        else:
            expected[column] = pd.to_numeric(before[column], errors="coerce")
        return expected

    registered = _EXPECTATION_REGISTRY.get(action)
    if registered is not None:
        return registered(before, decision, info)

    if action == "DerivedColumnRepairAction":
        from backend.cleaning.actions import compute_derived_values
        params = decision.parameters
        target = decision.evidence.column
        op = params.get("op")
        if op not in ("sum_offset", "product", "string_length", "day_of_week"):
            return None  # unknown op: force validation failure
        labels = [lbl for lbl in params.get("repair_row_labels", []) if lbl in before.index]
        expected = before.copy()
        if labels:
            computed = compute_derived_values(expected, op, params)
            expected.loc[labels, target] = computed.loc[labels]
        return expected

    return None


def validate_run(
    original: pd.DataFrame,
    final: pd.DataFrame,
    result,  
) -> Dict[str, Any]:
    """Whole-run validation: aggregate accounting between the ORIGINAL input frame
    and the FINAL output frame.

    Verifies that every row removal and schema change is fully explained by
    committed log entries, and itemizes every dtype change. Failures are
    returned so the engine can surface them as run errors.
    """
    report: Dict[str, Any] = {"checks": {}, "failures": [], "dtype_changes": []}

    # Row accounting.
    removed_total = sum(
        e.rows_affected
        for e in result.log
        if e.applied and e.problem_type == "duplicates"
    )
    
    empty_dropped = 0
    expected_final_rows = original.shape[0] - removed_total
    rows_ok = len(final) == expected_final_rows
    report["checks"]["row_accounting"] = {
        "original_rows": int(original.shape[0]),
        "empty_rows_dropped": int(empty_dropped),
        "duplicate_rows_removed": int(removed_total),
        "final_rows": int(len(final)),
        "ok": bool(rows_ok),
    }
    if not rows_ok:
        report["failures"].append(
            f"Row accounting mismatch: expected {expected_final_rows} "
            f"final rows, found {len(final)}."
        )

    # >>> FIX: Column accounting - allow explicitly dropped columns <<<
    explicitly_dropped = {
        str(e.columns_touched[0]) 
        for e in result.log 
        if e.applied and e.action == "DropColumnAction" and e.columns_touched
    }
    
    dropped = [
        str(c) for c in original.columns 
        if str(c) not in map(str, final.columns) and str(c) not in explicitly_dropped
    ]
    report["checks"]["dropped_columns"] = dropped
    if dropped:
        report["failures"].append(
            f"Columns disappeared during cleaning: {dropped}."
        )
    # >>> END FIX <<<
    
    for col in final.columns:
        before_dtype = original[col].dtype if col in original.columns else None
        after_dtype = final[col].dtype
        if before_dtype is not None and str(before_dtype) != str(after_dtype):
            report["dtype_changes"].append(
                {
                    "column": str(col),
                    "from": str(before_dtype),
                    "to": str(after_dtype),
                }
            )

    report["checks"]["index_is_range"] = isinstance(final.index, pd.RangeIndex)
    return report


def _frame_difference(
    before: pd.DataFrame,
    after: pd.DataFrame,
    expected: pd.DataFrame,
    primary_column: Optional[str],
) -> Optional[str]:
    """Return None when after == expected, else a precise explanation."""
    try:
        pd.testing.assert_frame_equal(after, expected)
        return None
    except AssertionError as err:
        detail = str(err).split("\n")[0]

        # Pinpoint whether any UNTOUCHED column diverged from the original.
        touched = {primary_column}
        for col in before.columns:
            if col in touched:
                continue
            if str(col) not in after.columns:
                continue  # already reported by the column_set check
            if len(after) == len(before) and not _column_equal(
                before[col], after[col]
            ):
                return f"Untouched column '{col}' was modified."
        return f"Result differs from deterministic expectation: {detail}"


def _column_equal(left: pd.Series, right: pd.Series) -> bool:
    if left.dtype != right.dtype:
        return False
    try:
        pd.testing.assert_series_equal(left, right, check_names=False)
        return True
    except AssertionError:
        return False