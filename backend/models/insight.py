from pydantic import BaseModel
from typing import Dict, Any, Optional


class InsightCandidate(BaseModel):

    type: str
    title: str
    finding: str

    business_interpretation: Optional[str] = None

    evidence: Dict[str, Any]

    confidence: float
    importance_score: float