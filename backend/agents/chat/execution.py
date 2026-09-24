"""Tool execution for the Chat Agent."""
import os
import json
from typing import Any, Dict, Optional

from backend.tools.dataframe_exploration import (
    get_row,
    dataset_info,
    get_unique_values,
)
from backend.tools.dataframe_stats import (
    calculate_percentage,
    filter_rows,
    get_column_stats,
)
from backend.tools.dataframe_ml_chart import (
    get_ml_analysis,
    get_chart_data,
    generate_chart,
)


tools = {
    "get_row": get_row,
    "calculate_percentage": calculate_percentage,
    "filter_rows": filter_rows,
    "dataset_info": dataset_info,
    "get_column_stats": get_column_stats,
    "get_unique_values": get_unique_values,
    "get_ml_analysis": get_ml_analysis,
    "get_chart_data": get_chart_data,
    "generate_chart": generate_chart,
}


def _build_tools_description() -> str:
    """Build a human-readable description of all available tools."""
    desc = []

    for name, tool in tools.items():
        desc.append(f"Tool: {name}")
        desc.append(f"Description: {tool.description}")
        desc.append("---")

    return "\n".join(desc)


def _execute_tool(
    tool_name: str,
    tool_input: dict,
    context: dict,
) -> Dict[str, Any]:
    """Execute a selected tool safely."""
    if tool_name not in tools:
        return {
            "error": f"Tool '{tool_name}' not found"
        }

    tool_input = dict(tool_input or {})

    # Dataset-based tools (need df_path)
    if tool_name not in [
        "get_ml_analysis",
        "get_chart_data",
        "generate_chart",
    ]:

        if not tool_input.get("df_path"):
            df_path = context.get("df_path")

            if df_path and os.path.exists(df_path):
                tool_input["df_path"] = df_path

            else:
                return {
                    "error": (
                        "No valid dataset path available. "
                        f"Path: '{df_path}'"
                    )
                }

    # Dataset-id based tools
    if tool_name in [
        "get_ml_analysis",
        "get_chart_data",
        "generate_chart",
    ]:

        if not tool_input.get("dataset_id"):
            tool_input["dataset_id"] = context.get(
                "dataset_id",
                "",
            )

        if not tool_input["dataset_id"]:
            return {
                "error": "No dataset_id available"
            }

    try:
        tool_func = tools[tool_name]

        if isinstance(tool_input, dict):

            result = (
                tool_func.invoke(tool_input)
                if hasattr(tool_func, "invoke")
                else tool_func(**tool_input)
            )

        else:

            result = (
                tool_func.invoke(
                    {"query": str(tool_input)}
                )
                if hasattr(tool_func, "invoke")
                else tool_func(
                    query=str(tool_input)
                )
            )

        return (
            result
            if isinstance(result, dict)
            else {"result": str(result)}
        )

    except Exception as e:
        return {
            "error": str(e)
        }