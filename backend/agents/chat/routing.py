"""Tool routing and detection for the Chat Agent."""
from typing import Dict


# Tool detection signals
GENERATE_CHART_SIGNALS = [
    "draw",
    "draw a",
    "draw this",
    "generate chart",
    "generate a chart",
    "generate graph",
    "generate a graph",
    "create chart",
    "create a chart",
    "create graph",
    "create a graph",
    "make a chart",
    "make chart",
    "make a graph",
    "make graph",
    "plot a",
    "plot the",
    "plot me",
    "plot this",
    "show me a chart",
    "show a chart",
    "show me a graph",
    "show a graph",
    "visualize",
    "visualise",
]

EXPLAIN_CHART_SIGNALS = [
    "chart",
    "graph",
    "visualization",
    "visualisation",
    "plot",
    "figure",
    "image",
    "confusion matrix",
    "heatmap",
    "box plot",
    "boxplot",
    "histogram",
    "scatter",
    "explain the chart",
    "describe the chart",
    "this chart",
]

ML_SIGNALS = [
    "machine learning",
    " ml ",
    "model",
    "predict",
    "prediction",
    "feature importance",
    "accuracy",
    "precision",
    "recall",
    "f1",
    "classification",
    "regression",
    "algorithm",
    "train",
    "training",
]

UNIQUE_VALUES_SIGNALS = [
    "unique",
    "distinct",
    "categories",
    "category",
    "values",
    "what values",
    "which values",
    "possible values",
    "what are the",
]

COLUMN_STATS_SIGNALS = [
    "average",
    "avg",
    "mean",
    "median",
    "mode",
    "minimum",
    "minimum value",
    "maximum",
    "maximum value",
    "min",
    "max",
    "standard deviation",
    "std",
    "variance",
    "quantile",
    "percentile",
    "statistics",
    "statistic",
    "distribution",
]

ROW_LOOKUP_SIGNALS = [
    "row",
    "record",
    "records",
    "show me the person",
    "show me the row",
    "find the row",
    "lookup",
]

FILTERING_SIGNALS = [
    "how many",
    "count",
    "number of",
    "filter",
    "where",
    "how much",
    "how often",
]

PERCENTAGE_SIGNALS = [
    "percentage",
    "percent",
    "%",
    "proportion",
    "share",
    "rate",
]


def _detect_required_tool(question: str) -> str:
    """
    Detect the most appropriate tool category from the user's question.

    This does NOT execute the tool.
    It only provides a routing hint to Gemini.
    """
    q = question.lower().strip()

    # Generate a NEW chart (on-demand via VisualizationAgent)
    if any(signal in q for signal in GENERATE_CHART_SIGNALS):
        return "generate_chart"

    # Explain / retrieve an EXISTING chart from analysis
    if any(signal in q for signal in EXPLAIN_CHART_SIGNALS):
        return "get_chart_data"

    # ML
    if any(signal in q for signal in ML_SIGNALS):
        return "get_ml_analysis"

    # Unique values / categories
    if any(signal in q for signal in UNIQUE_VALUES_SIGNALS):
        return "get_unique_values"

    # Column statistics
    if any(signal in q for signal in COLUMN_STATS_SIGNALS):
        return "get_column_stats"

    # Row lookup / exact record
    if any(signal in q for signal in ROW_LOOKUP_SIGNALS):
        return "get_row"

    # Filtering / counting
    if any(signal in q for signal in FILTERING_SIGNALS):
        return "filter_rows"

    # Percentage
    if any(signal in q for signal in PERCENTAGE_SIGNALS):
        return "calculate_percentage"

    # General dataset question
    return "dataset_info"


def _build_routing_hint(question: str) -> str:
    preferred_tool = _detect_required_tool(question)

    if preferred_tool == "dataset_info":
        return """
            ROUTING HINT:
            This appears to be a general dataset question.

            Use dataset_info if the current context does not contain enough information.
            """

    if preferred_tool == "generate_chart":
        return """
            ROUTING HINT:
            The user is asking to DRAW / CREATE a new chart.

            CRITICAL RULE: You MUST respond with ONLY the raw JSON tool call. 
            Do NOT output any text, explanation, or markdown before the JSON.

            You MUST call the `generate_chart` tool NOW with this exact JSON format:
            {"tool": "generate_chart", "input": {"chart_type": "...", "x_axis": "...", "y_axis": "...", "title": "..."}}

            Rules:
            - chart_type: one of bar, scatter, line, histogram, box, pie, heatmap.
            - x_axis / y_axis: exact column names from REAL_DATA_FACTS (never invent columns).
            - y_axis is optional for histogram / count bar / pie.
            - ML CHARTS EXCEPTION: If the user asks for "feature importance", you MUST use exactly:
              chart_type="bar", x_axis="feature", y_axis="importance". 
              (Note: "feature" and "importance" are synthetic ML axes provided by the backend, do not look for them as CSV columns).
            - Do NOT use get_chart_data (that only explains existing charts).
            - Do NOT answer in plain text before calling the tool.
            """

    return f"""
        ROUTING HINT:
        The user's question appears to require the `{preferred_tool}` tool.

        If the question requires an exact value, calculation, filtering,
        column statistic, unique-value lookup, ML result, row lookup,
        percentage calculation, or chart data, USE THE `{preferred_tool}` TOOL
        BEFORE giving the final answer.

        Do not answer an exact data question from a generic dataset overview
        when the appropriate tool can retrieve the exact result.
        """