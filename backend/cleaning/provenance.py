"""Cleaning provenance & tamper-evident audit trail.

Phase 8: every CleaningEngine run can now answer, cryptographically:

    - WHICH exact input produced this output?      (input_digest)
    - WHAT is the digest of the result?            (output_digest)
    - UNDER which policy / declared rules?         (policy/rules snapshots)
    - IS the recorded log intact?                  (chained entry hashes)

Design notes:
    * frame_digest is deterministic for a given pandas version: structure
      metadata (shape/dtypes/names) + per-column content hashes.
    * Log entries form a hash chain (genesis prev_hash = "0"*64); modifying
      any historical field breaks every subsequent hash.
    * Nothing here mutates DataFrames or the run result beyond attaching
      provenance metadata.
"""
import hashlib
import json
from typing import Any, Dict, List

import numpy as np
import pandas as pd

_GENESIS = "0" * 64


def frame_digest(df: pd.DataFrame) -> str:
    """Deterministic SHA-256 fingerprint of a DataFrame's structure+content."""
    h = hashlib.sha256()
    h.update(f"{len(df)}x{len(df.columns)}|".encode())
    h.update((";".join(map(str, df.columns)) + "|").encode())
    h.update((";".join(map(str, df.dtypes)) + "|").encode())

    if len(df) == 0:
        return h.hexdigest()

    # Column-wise content hashing keeps memory bounded and is order-stable
    # for identical inputs.
    for col in df.columns:
        series = df[col]
        try:
            row_hashes = pd.util.hash_pandas_object(
                series, index=False
            ).to_numpy(dtype="uint64")
        except Exception:  # unhashable cell types -> stringify fallback
            row_hashes = pd.util.hash_pandas_object(
                series.astype(str), index=False
            ).to_numpy(dtype="uint64")
        # Order-independent aggregate plus order-sensitive mix: the sum
        # catches multiset changes, the xor-shifted fold catches order.
        h.update(np.sum(row_hashes, dtype="uint64").tobytes())
        # Perform the intentional uint64 wraparound using Python integers so
        # NumPy does not emit overflow warnings. The modulo operation is the
        # exact FNV-1a 64-bit arithmetic intended by this fingerprint.
        acc = 1469598103934665603
        mask64 = (1 << 64) - 1
        for v in row_hashes[:20000]:
            acc = ((acc ^ int(v)) * 1099511628211) & mask64
        h.update(np.uint64(acc).tobytes())
    return h.hexdigest()


def _entry_payload(entry) -> str:
    """Canonical JSON payload of a log entry for chaining."""
    payload = {
        "entry_id": entry.entry_id,
        "prev_hash": entry.prev_hash,
        "action": entry.action,
        "decision_verdict": entry.decision_verdict,
        "problem_type": entry.problem_type,
        "column": entry.column,
        "detector": entry.detector,
        "method": entry.method,
        "confidence": entry.confidence,
        "applied": entry.applied,
        "rolled_back": entry.rolled_back,
        "rollback_verified": entry.rollback_verified,
        "rows_affected": entry.rows_affected,
        "cells_changed": entry.cells_changed,
        "columns_touched": entry.columns_touched,
        "error": entry.error,
    }
    return json.dumps(payload, sort_keys=True, default=str)


def _hash_entry(payload: str) -> str:
    return hashlib.sha256(payload.encode()).hexdigest()


def chain_log_entries(entries) -> None:
    """Assign entry_id/prev_hash/entry_hash in place, in order."""
    prev = _GENESIS
    for i, entry in enumerate(entries, start=1):
        entry.entry_id = i
        entry.prev_hash = prev
        entry.entry_hash = _hash_entry(_entry_payload(entry))
        prev = entry.entry_hash


def verify_chain(result) -> List[str]:
    """Recompute the hash chain. Returns a list of problems (empty=valid)."""
    problems: List[str] = []
    prev = _GENESIS
    for expected_id, entry in enumerate(result.log, start=1):
        if entry.prev_hash != prev:
            problems.append(
                f"entry {expected_id}: prev_hash does not match parent"
            )
            break
        recomputed = _hash_entry(_entry_payload(entry))
        if recomputed != entry.entry_hash:
            problems.append(
                f"entry {expected_id}: payload modified "
                f"(stored {entry.entry_hash[:12]}, computed {recomputed[:12]})"
            )
        prev = entry.entry_hash
    return problems


def compute_provenance(
    input_digest: str,
    output_digest: str,
    policy_snapshot: Dict[str, Any],
    rules_snapshot: Dict[str, Any],
    entries,
) -> Dict[str, str]:
    """Assemble the provenance block attached to a CleaningResult."""
    chain_root = (
        entries[-1].entry_hash if entries else _GENESIS
    )
    policy_digest = hashlib.sha256(
        json.dumps(policy_snapshot, sort_keys=True, default=str).encode()
    ).hexdigest()
    rules_digest = hashlib.sha256(
        json.dumps(rules_snapshot, sort_keys=True, default=str).encode()
    ).hexdigest()
    return {
        "input_digest": input_digest,
        "output_digest": output_digest,
        "policy_digest": policy_digest,
        "rules_digest": rules_digest,
        "chain_root": chain_root,
    }


# ---------------------------------------------------------------------------
# Audit bundle I/O
# ---------------------------------------------------------------------------

def export_audit_bundle(result, path: str) -> str:
    """Write the full audit trail (provenance + chained log + decisions +
    run validation) as JSON. Returns the path written."""
    bundle = {
        "provenance": {
            "input_digest": result.input_digest,
            "output_digest": result.output_digest,
            "policy_snapshot": result.policy_snapshot,
            "rules_snapshot": result.rules_snapshot,
            "chain_root": result.chain_root,
        },
        "assessment": result.assessment,
        "success": result.success,
        "blocked": result.blocked,
        "run_validation": result.run_validation,
        "decisions": [d.model_dump(mode="json") for d in result.decisions],
        "log": [e.model_dump(mode="json") for e in result.log],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2, default=str)
    return path


def load_and_verify_audit_bundle(path: str) -> Dict[str, Any]:
    """Load an exported bundle and re-verify its hash chain.

    Returns {"valid": bool, "problems": [...], "bundle": <loaded dict>}.
    """
    with open(path, "r", encoding="utf-8") as f:
        bundle = json.load(f)

    problems: List[str] = []
    prev = _GENESIS
    for i, entry in enumerate(bundle.get("log", []), start=1):
        if entry.get("prev_hash") != prev:
            problems.append(f"entry {i}: broken chain linkage")
            break
        recomputed = _hash_entry(_entry_payload_values(entry, prev, i))
        if recomputed != entry.get("entry_hash"):
            problems.append(
                f"entry {i}: payload modified since export"
            )
        prev = entry.get("entry_hash", "")

    root_ok = (
        not problems
        and (bundle["log"][-1]["entry_hash"] == bundle["provenance"]["chain_root"]
             if bundle.get("log") else
             bundle["provenance"]["chain_root"] == _GENESIS)
    )
    if not root_ok:
        problems.append("chain_root does not match final entry hash")

    return {"valid": not problems, "problems": problems, "bundle": bundle}


def _entry_payload_values(entry: Dict[str, Any], prev: str, entry_id: int) -> str:
    """Rebuild the canonical payload from a deserialized (JSON) entry using
    exactly the same restricted key set as _entry_payload."""
    keys = [
        "entry_id", "prev_hash", "action", "decision_verdict",
        "problem_type", "column", "detector", "method", "confidence",
        "applied", "rolled_back", "rollback_verified", "rows_affected",
        "cells_changed", "columns_touched", "error",
    ]
    payload = {k: entry.get(k) for k in keys}
    payload["prev_hash"] = prev
    payload["entry_id"] = entry_id
    return json.dumps(payload, sort_keys=True, default=str)
