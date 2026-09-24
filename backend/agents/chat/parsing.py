"""Tool call parsing for the Chat Agent."""
import json
import re
from typing import Any, Dict, Optional


def _parse_tool_call(text: str) -> Optional[Dict[str, Any]]:
    """Parse an LLM tool call."""
    text = (text or "").strip()

    if not text:
        return None

    # JSON inside Markdown code block
    json_match = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        text,
        re.DOTALL | re.IGNORECASE,
    )

    if json_match:
        try:
            parsed = json.loads(json_match.group(1))

            if (
                isinstance(parsed, dict)
                and "tool" in parsed
                and "input" in parsed
            ):
                return parsed

        except (json.JSONDecodeError, TypeError):
            pass

    # Raw JSON
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and start < end:
        try:
            parsed = json.loads(text[start:end + 1])

            if (
                isinstance(parsed, dict)
                and "tool" in parsed
                and "input" in parsed
            ):
                return parsed

        except (json.JSONDecodeError, TypeError):
            pass

    # Legacy Action format
    action_match = re.search(
        r"Action:\s*(\w+)[\s\n]+Action\s*Input:\s*(\{.*?\}|\[.*?\]|\".*?\"|\S+)",
        text,
        re.DOTALL | re.IGNORECASE,
    )

    if action_match:
        tool_name = action_match.group(1).strip()
        input_str = action_match.group(2).strip()

        try:
            tool_input = json.loads(input_str)

        except (json.JSONDecodeError, TypeError):
            tool_input = {"query": input_str}

        return {
            "tool": tool_name,
            "input": tool_input,
        }

    # USE_TOOL format
    tool_match = re.search(
        r"USE_TOOL:\s*(\w+)\s+INPUT:\s*(\{.*?\})",
        text,
        re.DOTALL | re.IGNORECASE,
    )

    if tool_match:
        try:
            return {
                "tool": tool_match.group(1).strip(),
                "input": json.loads(tool_match.group(2)),
            }

        except (json.JSONDecodeError, TypeError):
            pass

    return None