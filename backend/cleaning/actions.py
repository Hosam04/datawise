"""Cleaning actions for the DataWise Cleaning Engine.

Actions are explicit, deterministic executors. They contain NO detection
logic of their own: they receive an approved Decision (with concrete
parameters such as an exact fill value or fence bounds) and materialize it.

Every action returns a NEW DataFrame plus an info dict describing what it
changed, including a bounded cell-level change ledger and a logical inverse
patch. On any failure the exception propagates to the engine, which restores
its snapshot (rollback).
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
import html as html_module

from backend.cleaning.contracts import UNKNOWN_CATEGORY_LABEL, Decision
from .schemas import CleaningActionSpec

# Bounded change ledger per action execution.
MAX_LEDGER_CHANGES = 100


@dataclass(frozen=True)
class ActionSpec:
    """Self-description consumed by engine budgets and reporting."""

    kind: str          # ActionKind.CONTENT | ANNOTATION | ROW_REMOVAL | SCHEMA
    scope: str         # "column" | "dataset" | "schema"
    # When True the engine skips generic expectation-matching (used only by
    # actions that carry their own expected_frame implementation).
    self_validating: bool = False


def _ledger(series_before: pd.Series, series_after: pd.Series,
            column: str) -> List[Dict[str, Any]]:
    """Bounded before/after cell records for changed positions.

    Object-level comparison so NaN->value transitions are detected
    reliably even under pandas' NA-propagating string dtypes.
    """
    left = series_before.to_numpy(dtype=object)
    right = series_after.to_numpy(dtype=object)
    labels = [
        label
        for label, l, r in zip(series_before.index, left, right)
        if _cell_differs(l, r)
    ][:MAX_LEDGER_CHANGES]
    return [
        {
            "column": column,
            "row": int(label),
            "before": _safe(series_before[label]),
            "after": _safe(series_after[label]),
        }
        for label in labels
    ]


def _cell_differs(left, right) -> bool:
    try:
        if pd.isna(left) and pd.isna(right):
            return False
        if pd.isna(left) or pd.isna(right):
            return True
    except (TypeError, ValueError):
        pass
    return left != right


def _apply_info(
    rows_affected: int,
    cells_changed: int,
    columns_touched: list,
    **extra: Any,
) -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "rows_affected": int(rows_affected),
        "cells_changed": int(cells_changed),
        "columns_touched": [str(c) for c in columns_touched],
    }
    info.update(extra)
    return info


class MissingValueAction:
    """Fills missing cells in ONE column using the decision-approved value.

    Supported strategies (all decided upstream):
      - "median": numeric median fill of missing cells only
      - "constant": fill with the column's single observed value
      - "mode": fill with the most frequent observed value
      - "explicit_unknown_category": preserve missingness as an explicit label
    """

    name = "MissingValueAction"
    spec = ActionSpec(kind="content", scope="column")

    def apply(self, df: pd.DataFrame, decision: Decision) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        params = decision.parameters
        column = str(decision.evidence.column)
        strategy = params.get("strategy")
        fill_value = params.get("fill_value")

        if column not in df.columns:
            raise ValueError(f"Target column '{column}' not found.")
        if strategy not in {"median", "constant", "mode", "explicit_unknown_category"}:
            raise ValueError(f"Unsupported imputation strategy: {strategy!r}")
        if strategy == "explicit_unknown_category":
            fill_value = UNKNOWN_CATEGORY_LABEL
        if fill_value is None:
            raise ValueError("Decision did not provide a concrete fill value.")

        series = df[column]
        from backend.core.constants import missing_equivalent_mask
        mask = missing_equivalent_mask(series, exclude_values=[fill_value])
        affected = int(mask.sum())
        if affected == 0:
            # Nothing to do; return an equal frame rather than guessing.
            return df.copy(), _apply_info(
                0, 0, [column], strategy=strategy, fill_value=_safe(fill_value)
            )

        # Assign only the approved missing cells. This avoids pandas' legacy
        # silent-downcasting path while preserving the original dtype when
        # possible.
        filled = series.copy()
        if isinstance(filled.dtype, pd.CategoricalDtype):
            if fill_value not in filled.cat.categories:
                filled = filled.cat.add_categories([fill_value])
        filled.loc[mask] = fill_value

        result = df.copy()
        result[column] = filled

        return result, _apply_info(
            rows_affected=affected,
            cells_changed=affected,
            columns_touched=[column],
            strategy=strategy,
            fill_value=_safe(fill_value),
            changes=_ledger(series, result[column], column),
            inverse=_ledger(series, result[column], column),
        )


class DuplicateRemovalAction:
    """Removes EXACT duplicate rows, keeping the first occurrence.

    Compares only the columns the Decision approved (identifier columns
    are excluded to match the detector's evidence exactly)."""

    name = "DuplicateRemovalAction"
    spec = ActionSpec(kind="row_removal", scope="dataset")

    def apply(self, df: pd.DataFrame, decision: Decision) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        keep = decision.parameters.get("keep", "first")
        expected_removed = int(decision.parameters.get("rows_to_remove", 0))
        excluded_columns = set(decision.parameters.get("excluded_columns", []))
        subset = [c for c in df.columns if c not in excluded_columns] or None

        before_rows = len(df)
        result = df.drop_duplicates(subset=subset, keep=keep)
        removed = before_rows - len(result)

        if removed != expected_removed:
            raise RuntimeError(
                f"Duplicate count changed between detection "
                f"({expected_removed}) and execution ({removed})."
            )

        return result, _apply_info(
            rows_affected=removed,
            cells_changed=int(df.shape[1]) * removed,
            columns_touched=[str(c) for c in df.columns],
            keep=keep,
            subset=subset,
        )


class OutlierFlagAction:
    """Annotation-only: adds/updates a boolean <column>_OutlierFlag column.

    This modifies SCHEMA additively but never changes any existing cell
    value. The mask is derived mechanically from the decision-approved
    fences — whether to annotate at all was decided upstream.
    """

    name = "OutlierFlagAction"
    spec = ActionSpec(kind="annotation", scope="schema")

    def apply(self, df: pd.DataFrame, decision: Decision) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        params = decision.parameters
        column = params.get("column") or decision.evidence.column
        lower = params.get("lower_bound")
        upper = params.get("upper_bound")

        if column is None or column not in df.columns:
            raise ValueError(f"Outlier target column '{column}' not found.")

        values = pd.to_numeric(df[column], errors="coerce")
        mask = (values < lower) | (values > upper) if lower is not None and upper is not None \
            else pd.Series(False, index=df.index)
        mask = mask.fillna(False).astype(bool)

        flag_name = f"{column}_OutlierFlag"
        result = df.copy()
        result[flag_name] = mask.astype("int8")

        return result, _apply_info(
            rows_affected=int(mask.sum()),
            cells_changed=0,  # no existing cell was modified
            columns_touched=[flag_name],
            flag_column=flag_name,
        )


class CategoricalNormalizationAction:
    """Applies decision-approved variant->canonical mappings to ONE column.

    Only exact string matches are rewritten; NaN and any value not listed in
    the approved mapping are left untouched.
    """

    name = "CategoricalNormalizationAction"
    spec = ActionSpec(kind="content", scope="column")

    def apply(self, df: pd.DataFrame, decision: Decision) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        column = str(decision.evidence.column)
        mapping = decision.parameters.get("mapping")
        if not isinstance(mapping, dict) or not mapping:
            raise ValueError("Decision did not provide a variant mapping.")
        if column not in df.columns:
            raise ValueError(f"Target column '{column}' not found.")

        series = df[column]
        mask = series.notna() & series.astype(str).isin(mapping.keys())
        affected = int(mask.sum())

        result = df.copy()
        result.loc[mask, column] = series[mask].map(mapping)

        return result, _apply_info(
            rows_affected=affected,
            cells_changed=affected,
            columns_touched=[column],
            applied_mapping=dict(mapping),
            changes=_ledger(series, result[column], column),
            inverse=_ledger(series, result[column], column),
        )


class FormattingNormalizationAction:
    """Strips leading/trailing whitespace and collapses repeated internal
    whitespace in ONE approved text-like column. Content-preserving by
    definition; identifiers are never routed here by the decision layer."""

    name = "FormattingNormalizationAction"
    spec = ActionSpec(kind="content", scope="column")

    def apply(self, df: pd.DataFrame, decision: Decision) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        column = str(decision.evidence.column)
        if column not in df.columns:
            raise ValueError(f"Target column '{column}' not found.")
        if decision.parameters.get("allow_identifier_column"):
            raise ValueError("Refusing to reformat an identifier column.")

        series = df[column]
        normalized = (
            series.astype("string")
            .str.strip()
            .str.replace(r"\s+", " ", regex=True)
        )
        changed = series.notna() & (series.astype("string") != normalized)
        affected = int(changed.sum())

        result = df.copy()
        result[column] = normalized

        return result, _apply_info(
            rows_affected=affected,
            cells_changed=affected,
            columns_touched=[column],
            transformation="strip+collapse_whitespace",
            changes=_ledger(series, result[column], column),
            inverse=_ledger(series, result[column], column),
        )


class TypeNormalizationAction:
    """Converts a string column to numeric/datetime when the decision layer
    proved the conversion LOSSLESS. Identifiers are never routed here."""

    name = "TypeNormalizationAction"
    spec = ActionSpec(kind="content", scope="column")

    def apply(self, df: pd.DataFrame, decision: Decision) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        column = str(decision.evidence.column)
        if column not in df.columns:
            raise ValueError(f"Target column '{column}' not found.")
        if decision.parameters.get("is_identifier"):
            raise ValueError("Refusing to convert an identifier column.")

        series = df[column]
        normalization = decision.parameters.get("normalization")

        if normalization == "remove_currency_separators_and_accounting_parentheses":
            normalized = (
                series.astype("string")
                .str.strip()
                .str.replace(r"[\$€£¥,%]", "", regex=True)
                .str.replace(r"^\((.*)\)$", r"-\1", regex=True)
                .str.replace(",", "", regex=False)
            )
            converted = pd.to_numeric(normalized, errors="coerce")
        elif normalization == "to_datetime":
            converted = pd.to_datetime(series, errors="coerce", format="mixed")
        elif normalization == "parse_coordinate":
            cleaned = series.astype("string").str.strip()
            converted = pd.to_numeric(cleaned, errors="coerce")
        else:
            converted = pd.to_numeric(series, errors="coerce")

        # Losslessness guard at execution time: any value that would become
        # NaN without having been NaN before means the approval is stale.
        newly_lost = int((series.notna() & converted.isna()).sum())
        if newly_lost:
            raise RuntimeError(
                f"Conversion of '{column}' would lose {newly_lost} value(s); "
                "refusing to guess."
            )

        result = df.copy()
        result[column] = converted

        return result, _apply_info(
            rows_affected=int(series.notna().sum()),
            cells_changed=int(series.notna().sum()),
            columns_touched=[column],
            converted_dtype=str(result[column].dtype),
        )


def compute_derived_values(df: pd.DataFrame, op: str, params: Dict[str, Any]) -> pd.Series:
    """Compute derived values for an entire column based on the operation.

    This is a pure computation function used by validation to build the
    deterministic expected frame. It computes the full column, not just
    the repair rows.
    """
    if op == "string_length":
        source = str(params["source"])
        return df[source].astype("string").str.len()
    elif op == "day_of_week":
        source = str(params["source"])
        mode = params.get("mode", "day_name")
        dt = pd.to_datetime(df[source], errors="coerce")
        if mode == "iso_number":
            return dt.dt.isoweekday().astype("Float64").astype("string")
        else:
            return dt.dt.day_name().astype("string")
    elif op == "product":
        src_a = pd.to_numeric(df[str(params["source_a"])], errors="coerce").astype(float)
        src_b = pd.to_numeric(df[str(params["source_b"])], errors="coerce").astype(float)
        return src_a * src_b
    elif op == "sum_offset":
        src_a = pd.to_numeric(df[str(params["source_a"])], errors="coerce").astype(float)
        src_b = pd.to_numeric(df[str(params["source_b"])], errors="coerce").astype(float)
        return src_a + src_b + int(params.get("offset", 0))
    else:
        raise ValueError(f"Unsupported derived operation: {op!r}")


class DerivedColumnRepairAction:
    """Recomputes ONLY the violating rows of a decision-approved
    deterministic relationship (sum_offset / product / string_length /
    day_of_week).

    Sources are never modified. Rows outside the approved violation set are
    never touched, even if they would evaluate differently."""

    name = "DerivedColumnRepairAction"
    spec = ActionSpec(kind="content", scope="column")

    def apply(self, df: pd.DataFrame, decision: Decision) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        params = decision.parameters
        target = str(decision.evidence.column)
        op = params.get("op")
        row_labels = params.get("repair_row_labels")

        if target not in df.columns:
            raise ValueError(f"Target column '{target}' not found.")
        if op not in ("sum_offset", "product", "string_length", "day_of_week"):
            raise ValueError(f"Unsupported derived operation: {op!r}")
        if not isinstance(row_labels, (list, tuple)) or not row_labels:
            raise ValueError("Decision did not provide repair row labels.")

        result = df.copy()

        if op == "string_length":
            source = str(params["source"])
            computed = result.loc[list(row_labels), source].astype("string").str.len()
        elif op == "day_of_week":
            source = str(params["source"])
            mode = params.get("mode", "day_name")
            dt = pd.to_datetime(result[source], errors="coerce")
            if mode == "iso_number":
                computed = dt.dt.isoweekday().astype("Float64").astype("string")
            else:
                computed = dt.dt.day_name().astype("string")
            computed = computed.astype("string")
        elif op == "product":
            src_a = pd.to_numeric(result[str(params["source_a"])], errors="coerce").astype(float)
            src_b = pd.to_numeric(result[str(params["source_b"])], errors="coerce").astype(float)
            computed = src_a * src_b
        elif op == "sum_offset":
            src_a = pd.to_numeric(result[str(params["source_a"])], errors="coerce").astype(float)
            src_b = pd.to_numeric(result[str(params["source_b"])], errors="coerce").astype(float)
            computed = src_a + src_b + int(params.get("offset", 0))
        else:
            # Defensive: should be unreachable due to the earlier membership check.
            raise ValueError(f"Unsupported derived operation: {op!r}")

        result.loc[list(row_labels), target] = computed.loc[list(row_labels)]

        return result, _apply_info(
            rows_affected=len(row_labels),
            cells_changed=len(row_labels),
            columns_touched=[target],
            op=op,
            repaired_rows=len(row_labels),
            changes=_ledger(df[target], result[target], target),
            inverse=_ledger(df[target], result[target], target),
        )

class DropColumnAction:
    """Drops a column entirely from the DataFrame.

    Used for columns with excessive missing data (>80%) that would become
    near-constant if filled with 'Unknown'.
    """

    name = "DropColumnAction"
    spec = ActionSpec(kind="schema", scope="schema")

    @classmethod
    def from_spec(cls, spec: "CleaningActionSpec") -> "DropColumnAction":
        """Normalize the action spec to the canonical column-removal kind.

        Column drops are schema mutations; the public kind used by regression
        locks and callers that go through from_spec is ``column_removal``.
        """
        spec.kind = "column_removal"
        return cls()

    def apply(
        self,
        df: pd.DataFrame,
        decision: Optional[Decision] = None,
        **kwargs: Any
    ):
        # Support both engine calls (Decision) and direct test calls (column=...)
        if decision is not None:
            column = str(decision.parameters.get("column") or decision.evidence.column)
        else:
            column = str(kwargs.get("column"))

        if column not in df.columns:
            raise ValueError(f"Target column '{column}' not found.")

        result = df.drop(columns=[column])
        info = _apply_info(
            rows_affected=0,
            cells_changed=int(df[column].notna().sum()),
            columns_touched=[column],
            dropped_column=column,
        )
        # Engine always passes a Decision and unpacks (df, info).
        # Direct / regression-test calls pass column= and expect the info dict.
        if decision is not None:
            return result, info
        return info


class HTMLDecodingAction:
    """Decodes HTML entities like &amp;, &gt;, &lt; in text columns.

    Deterministic and content-preserving.
    """

    name = "HTMLDecodingAction"
    spec = ActionSpec(kind="content", scope="column")

    @classmethod
    def from_spec(cls, spec: "CleaningActionSpec") -> "HTMLDecodingAction":
        """Ensures the action kind is correctly set if an incorrect kind is passed."""
        if spec.kind != "content":
            spec.kind = "content"
        return cls()

    def apply(
        self,
        df: pd.DataFrame,
        decision: Optional[Decision] = None,
        **kwargs: Any
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        if decision is not None:
            column = str(decision.parameters.get("column") or decision.evidence.column)
        else:
            column = str(kwargs.get("column"))

        if column not in df.columns:
            raise ValueError(f"Target column '{column}' not found.")

        series = df[column]

        def _decode(value: Any) -> Any:
            if pd.isna(value):
                return value
            try:
                return html_module.unescape(str(value))
            except Exception:
                return value

        decoded_series = series.apply(_decode)
        mask = series.notna() & (series.astype(str) != decoded_series.astype(str))
        affected = int(mask.sum())

        result = df.copy()
        result[column] = decoded_series

        return result, _apply_info(
            rows_affected=affected,
            cells_changed=affected,
            columns_touched=[column],
            transformation="html_unescape",
            changes=_ledger(series, result[column], column),
            inverse=_ledger(series, result[column], column),
        )

class CoordinateValidatorAction:
    name = "CoordinateValidatorAction"
    spec = ActionSpec(kind="content", scope="column")
    
    def apply(self, df: pd.DataFrame, decision: Decision) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        column = str(decision.parameters.get("column") or decision.evidence.column)
        invalid_values = set(decision.parameters.get("invalid_values", []))
        
        if column not in df.columns:
            raise ValueError(f"Target column '{column}' not found.")
        
        series = df[column]
        mask = series.astype(str).str.strip().isin(invalid_values)
        affected = int(mask.sum())
        
        result = df.copy()
        result.loc[mask, column] = np.nan
        
        return result, _apply_info(
            rows_affected=affected,
            cells_changed=affected,
            columns_touched=[column],
            transformation="null_island_to_nan",
        )
    
DEFAULT_ACTIONS = {
    "MissingValueAction": MissingValueAction(),
    "DuplicateRemovalAction": DuplicateRemovalAction(),
    "OutlierFlagAction": OutlierFlagAction(),
    "CategoricalNormalizationAction": CategoricalNormalizationAction(),
    "FormattingNormalizationAction": FormattingNormalizationAction(),
    "DerivedColumnRepairAction": DerivedColumnRepairAction(),
    "TypeNormalizationAction": TypeNormalizationAction(),
    "DropColumnAction": DropColumnAction(),
    "HTMLDecodingAction": HTMLDecodingAction(),
    "CoordinateValidatorAction": CoordinateValidatorAction(),
}






def _safe(value: Any) -> Any:
    """JSON-safe scalar conversion for log payloads."""
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        val = float(value)
        return val if np.isfinite(val) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value