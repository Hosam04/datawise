from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Optional, Any
from backend.models.plan import Plan
from pandas import DataFrame
import os
import pandas as pd
import csv

# NEW: Import MLResults schema
from backend.ml.schemas import MLResults

class AgentState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    session_id: str
    session_dir: str
    file_path: str
    user_query: str

    df: Optional[DataFrame] = Field(default=None, exclude=True)
    df_path: Optional[str] = Field(default=None)
    processed_columns: List[str] = Field(default_factory=list)

    plan: Optional[Any] = None  
    data_summary: Dict[str, Any] = Field(default_factory=dict)
    # Structured Statistical Engine results (read-only evidence about the
    # cleaned dataset). JSON-serializable; consumed by Insights /
    # Visualization / Report instead of recomputing statistics.
    statistical_results: Optional[Dict[str, Any]] = Field(default=None)
    visualization_paths: List[str] = Field(default_factory=list)
    visualizations: List[Dict[str, Any]] = Field(default_factory=list)
    insights: Optional[dict] = None
    insight_evidence: Dict[str, Any] = Field(default_factory=dict)
    evidence_tokens_used: int = 0
    dataset_profile: Dict[str, Any] = Field(default_factory=dict)
    target_detection: Optional[Dict[str, Any]] = Field(default_factory=dict)
    final_report: str = ""
    final_report_path: str = ""
    analysis_type: str = "exploratory"

    # NEW: ML results
    ml_results: Optional[MLResults] = Field(default=None)

    error: Optional[str] = None

    def get_df(self):
        if self.df is not None:
            return self.df

        if self.df_path and os.path.exists(self.df_path):
            self.df = pd.read_pickle(self.df_path)
            return self.df

        return None

    def save_safe_csv(self, filename: str = "processed_data.csv") -> Optional[str]:
        """Saves the dataframe to CSV safely, preventing newline corruption."""
        if self.df is None:
            self.get_df()
    
        if self.df is not None:
            csv_path = os.path.join(self.session_dir, filename)
            self.df.to_csv(csv_path, index=False, quoting=csv.QUOTE_ALL, lineterminator='\n', encoding='utf-8')
            print("SAFE CSV SAVED:", csv_path)
            return csv_path
        return None

  