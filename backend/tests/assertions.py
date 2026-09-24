"""Reusable diagnostic assertions for the DataWise test suite.

Every failure raised through :func:`fail` follows a uniform template so that
the diagnostic report (TEST_DIAGNOSTIC_REPORT.md) can be reconstructed from
pytest output:

    [TEST-001] Component | stage=Stage | dataset=...
    expected: ...
    actual:   ...
    affected artifact: ...
    likely root cause: ...
"""

from __future__ import annotations

from typing import Any, Iterable, List, Optional


def fail(
    test_id: str,
    component: str,
    stage: str,
    expected: Any,
    actual: Any,
    dataset: str = "",
    artifact: str = "",
    root_cause: str = "",
    severity: str = "MEDIUM",
) -> None:
    """Raise AssertionError with a diagnostic header."""
    lines = [
        f"[{test_id}] {component} | stage={stage} | severity={severity} | dataset={dataset}",
        f"  expected: {expected}",
        f"  actual:   {actual}",
    ]
    if artifact:
        lines.append(f"  affected artifact: {artifact}")
    if root_cause:
        lines.append(f"  likely root cause: {root_cause}")
    raise AssertionError("\n".join(lines))


def check(
    condition: bool,
    test_id: str,
    component: str,
    stage: str,
    expected: Any,
    actual: Any,
    dataset: str = "",
    artifact: str = "",
    root_cause: str = "",
    severity: str = "MEDIUM",
) -> None:
    """Assert ``condition`` and emit a diagnostic failure if it is falsy."""
    if not condition:
        fail(
            test_id,
            component,
            stage,
            expected,
            actual,
            dataset=dataset,
            artifact=artifact,
            root_cause=root_cause,
            severity=severity,
        )


def check_close(
    value: float,
    expected: float,
    test_id: str,
    component: str,
    stage: str,
    dataset: str = "",
    artifact: str = "",
    root_cause: str = "",
    severity: str = "MEDIUM",
    tol: float = 1e-5,
) -> None:
    if value is None:
        fail(
            test_id, component, stage, expected, "None", dataset=dataset,
            artifact=artifact, root_cause=root_cause, severity=severity,
        )
    if abs(float(value) - float(expected)) > tol:
        fail(
            test_id, component, stage, f"{expected} +/- {tol}", value,
            dataset=dataset, artifact=artifact, root_cause=root_cause,
            severity=severity,
        )


def rows_accounted(
    raw_rows: int,
    cleaned_rows: int,
    duplicate_removed: int = 0,
    other_removed: int = 0,
) -> bool:
    """Row-count balance: cleaned == raw - (duplicate rows + other removals)."""
    return cleaned_rows == raw_rows - duplicate_removed - other_removed


def cell_counts_from_log(log_entries: Iterable[dict], action: Optional[str] = None) -> int:
    """Sum ``cells_changed`` over applied log entries (optionally filtered)."""
    total = 0
    for e in log_entries:
        if not e.get("applied"):
            continue
        if action is not None and e.get("action") != action:
            continue
        total += int(e.get("cells_changed") or 0)
    return total


def ensure_dict_keys(mapping: dict, required: list, where: str) -> List[str]:
    """Return the list of required keys missing from ``mapping``."""
    return [k for k in required if k not in mapping]