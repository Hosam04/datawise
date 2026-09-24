from pydantic import BaseModel
from typing import Optional, Literal

class ChartConfig(BaseModel):
    chart_type: Literal["bar", "scatter", "line", "histogram", "box", "pie", "heatmap"]
    x_axis: str
    y_axis: Optional[str] = None
    title: str
    x_label: str
    y_label: Optional[str] = None
    # Optional grouping/color dimension (e.g. target for "by income" bars).
    # Backward-compatible: existing callers omit it and behaviour is unchanged.
    color: Optional[str] = None
