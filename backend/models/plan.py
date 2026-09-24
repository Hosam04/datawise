from pydantic import BaseModel, Field
from typing import List
from backend.models.chart import ChartConfig

class Plan(BaseModel):
    steps: List[str]
    requires_cleaning: bool
    charts: List[ChartConfig]
    requires_report: bool
    analysis_focus: List[str] = Field(default_factory=list)