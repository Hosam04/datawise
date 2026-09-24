"""DataWise Cleaning Engine.

A conservative, evidence-driven, dataset-agnostic cleaning subsystem.

Strict separation of responsibilities:

    Detector  -> Evidence   (read-only)
    Evidence  -> Decision   (safety gate, read-only)
    Decision  -> Action     (only Actions may modify data)
    Action    -> Validation (real before/after comparison)
    Validation-> Commit / Rollback
    Everything-> CleaningLog

The engine is intentionally LLM-free: all decisions are deterministic and
evidence-based. See backend/cleaning/contracts.py for the data contracts.
"""
from backend.cleaning.contracts import (
    CleaningLogEntry,
    CleaningResult,
    ColumnProfile,
    Decision,
    Evidence,
    InspectionResult,
    ValidationResult,
)
from backend.cleaning.engine import CleaningEngine
from backend.cleaning.inspection import build_column_profiles, inspect_dataframe



__all__ = [
    "CleaningEngine",
    "CleaningResult",
    "CleaningLogEntry",
    "ColumnProfile",
    "Decision",
    "Evidence",
    "InspectionResult",
    "ValidationResult",
    "build_column_profiles",
    "inspect_dataframe",
]
