"""Detectors package for the DataWise Cleaning Engine.

This package provides modular detector implementations while maintaining
backward compatibility with existing imports from backend.cleaning.detectors.
"""
from backend.cleaning.detectors.base import BaseDetector
from backend.cleaning.detectors.missing import MissingValueDetector
from backend.cleaning.detectors.duplicates import DuplicateDetector, NearDuplicateDetector
from backend.cleaning.detectors.outliers import OutlierDetector
from backend.cleaning.detectors.type_consistency import InvalidValueDetector, TypeAnomalyDetector
from backend.cleaning.detectors.categorical import CategoricalConsistencyDetector, MultiValueCategoryDetector
from backend.cleaning.detectors.formatting import FormattingAnomalyDetector, EncodingArtifactDetector
from backend.cleaning.detectors.derived import DerivedColumnConsistencyDetector
from backend.cleaning.detectors.constraints import ConstraintDetector, TemporalSanityDetector
from backend.cleaning.detectors.missingness import MissingnessPatternDetector
from backend.cleaning.detectors.semantic import SemanticAnomalyDetector, UnitInconsistencyDetector

# Default detectors used by the engine (mirrors the old DEFAULT_DETECTORS list)
DEFAULT_DETECTORS = [
    MissingValueDetector(),
    DuplicateDetector(),
]

__all__ = [
    "BaseDetector",
    "MissingValueDetector",
    "DuplicateDetector",
    "NearDuplicateDetector",
    "OutlierDetector",
    "InvalidValueDetector",
    "TypeAnomalyDetector",
    "CategoricalConsistencyDetector",
    "MultiValueCategoryDetector",
    "FormattingAnomalyDetector",
    "EncodingArtifactDetector",
    "DerivedColumnConsistencyDetector",
    "ConstraintDetector",
    "TemporalSanityDetector",
    "MissingnessPatternDetector",
    "SemanticAnomalyDetector",
    "UnitInconsistencyDetector",
    "DEFAULT_DETECTORS",
]