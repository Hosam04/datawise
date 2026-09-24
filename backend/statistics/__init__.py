"""DataWise Statistical Engine — public interface.

The Statistical Engine is READ-ONLY: it produces structured statistical
evidence about a dataset and never modifies it. All dataset modification —
including outlier treatment decisions — belongs to the Cleaning Engine
(backend.cleaning).

Primary entry point:

    from backend.statistics import StatisticalEngine

    engine = StatisticalEngine()
    results = engine.analyze(df)          # -> StatisticalResults (pydantic)
"""
from backend.statistics.contracts import (
    AssociationTest,
    BooleanSummary,
    CategoricalSummary,
    ColumnOutlierEvidence,
    CorrelationAnalysis,
    CorrelationPair,
    DatasetOverview,
    DatetimeSummary,
    DistributionCheck,
    GroupStatistics,
    GroupStatisticsEntry,
    GroupValueStats,
    NumericSummary,
    OutlierEvidence,
    StatisticalResults,
    TargetAssociations,
    TextSummary,
)
from backend.statistics.engine import StatisticalEngine, ENGINE_VERSION

__all__ = [
    "StatisticalEngine",
    "ENGINE_VERSION",
    "StatisticalResults",
    "DatasetOverview",
    "NumericSummary",
    "CategoricalSummary",
    "BooleanSummary",
    "DatetimeSummary",
    "TextSummary",
    "OutlierEvidence",
    "ColumnOutlierEvidence",
    "CorrelationAnalysis",
    "CorrelationPair",
    "DistributionCheck",
    "GroupStatistics",
    "GroupStatisticsEntry",
    "GroupValueStats",
    "AssociationTest",
    "TargetAssociations",
]
