"""Pydantic schemas for ML layer results."""
from typing import List, Dict, Optional, Any, Literal
from pydantic import BaseModel, Field


class ClassMetrics(BaseModel):
    """Metrics for a single class in multi-class classification."""
    precision: float
    recall: float
    f1: float
    support: int


class MLMetrics(BaseModel):
    """Unified metrics container for any model type."""
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1: Optional[float] = None
    auc_roc: Optional[float] = None
    mse: Optional[float] = None
    rmse: Optional[float] = None
    mae: Optional[float] = None
    r2: Optional[float] = None
    per_class: Optional[Dict[str, ClassMetrics]] = None


class FeatureImportanceItem(BaseModel):
    feature: str
    importance: float


class MLResults(BaseModel):
    """Structured ML results stored in AgentState."""
    status: Literal["pending", "success", "failed", "skipped"] = "skipped"
    reason: Optional[str] = None
    problem_type: Optional[Literal["classification", "regression", "text_classification"]] = None
    data_modality: Optional[Literal["tabular", "text", "mixed"]] = None
    selected_model: Optional[str] = None
    fallback_model: Optional[str] = None
    used_fallback: bool = False
    selection_reason: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    metrics: MLMetrics = Field(default_factory=MLMetrics)
    feature_importance: List[FeatureImportanceItem] = Field(default_factory=list)
    confusion_matrix: Optional[Dict[str, Any]] = None
    actual_vs_predicted: Optional[List[Dict[str, Any]]] = None
    residuals: Optional[List[float]] = None
    warnings: List[str] = Field(default_factory=list)
    training_time_sec: Optional[float] = None
    rows_used: Optional[int] = None