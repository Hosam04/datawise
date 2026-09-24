"""Main Chat Agent for the DataWise analysis pipeline."""
import time
import random
import json
import re
from typing import Any, Dict, List, Optional

from backend.llm.gemini_client import get_chat_model
from backend.llm.prompts import CHAT_SYSTEM_PROMPT

from backend.agents.chat.context import format_context
from backend.agents.chat.routing import _detect_required_tool, _build_routing_hint
from backend.agents.chat.parsing import _parse_tool_call
from backend.agents.chat.execution import _execute_tool, _build_tools_description
from backend.agents.chat.fallback import _fallback_answer

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


class ChatAgent:
    def __init__(self):
        """Initialize the chat agent with LLM and available tools."""
        self.llm = get_chat_model()

        self.tools = {
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
        self.tools_description = self._build_tools_description()

    def _build_tools_description(self) -> str:
        """Build a human-readable description of all available tools."""
        from backend.agents.chat.execution import _build_tools_description as _build
        return _build()

    def _format_context(self, context: dict) -> str:
        from backend.agents.chat.context import format_context
        return format_context(context)

    def _detect_required_tool(self, question: str) -> str:
        from backend.agents.chat.routing import _detect_required_tool
        return _detect_required_tool(question)

    def _build_routing_hint(self, question: str) -> str:
        from backend.agents.chat.routing import _build_routing_hint
        return _build_routing_hint(question)

    def _parse_tool_call(self, text: str):
        from backend.agents.chat.parsing import _parse_tool_call
        return _parse_tool_call(text)

    def _execute_tool(
        self,
        tool_name: str,
        tool_input: dict,
        context: dict,
    ):
        from backend.agents.chat.execution import _execute_tool
        return _execute_tool(tool_name, tool_input, context)

    def _fallback_answer(
        self,
        question: str,
        context: dict,
    ) -> str:
        from backend.agents.chat.fallback import _fallback_answer
        return _fallback_answer(question, context)

    def _call_llm_with_retry(
        self,
        prompt: str,
        max_retries: int = 3,
    ):
        """Call Gemini with retry handling."""
        last_error = None

        for attempt in range(max_retries):
            try:
                response = self.llm.invoke(prompt)

                return (
                    response.content
                    if hasattr(response, "content")
                    else str(response)
                )

            except Exception as e:
                last_error = str(e)
                error_lower = last_error.lower()

                if (
                    "429" in last_error
                    or "resource_exhausted" in error_lower
                    or "quota" in error_lower
                ):
                    wait_time = (
                        (2 ** attempt)
                        + random.uniform(0, 1)
                    )

                    if attempt < max_retries - 1:
                        time.sleep(wait_time)
                        continue

                if attempt == max_retries - 1:
                    raise Exception(last_error)

        raise Exception(
            f"Failed after {max_retries} attempts: {last_error}"
        )

    def _build_prompt(
        self,
        question: str,
        context_str: str,
        tool_results: list = None,
        history: list = None,
    ) -> str:

        tool_results_str = ""

        if tool_results:
            tool_results_str = "\n\nPREVIOUS TOOL RESULTS:\n"

            for i, result in enumerate(tool_results, 1):
                output_str = json.dumps(
                    result["output"],
                    ensure_ascii=False,
                    default=str,
                )[:4000]

                tool_results_str += (
                    f"\nStep {i}:\n"
                    f"Tool: {result['tool']}\n"
                    f"Input: {json.dumps(result['input'], ensure_ascii=False)}\n"
                    f"Output: {output_str}\n"
                )

        history_str = ""

        if history:
            history_str = (
                "\n\nCONVERSATION HISTORY "
                "(most recent last):\n"
            )

            for turn in history:
                role = (
                    "User"
                    if turn.get("role") == "user"
                    else "DataWise"
                )

                content = str(
                    turn.get("content", "")
                ).strip()

                if content:
                    history_str += f"{role}: {content}\n"

            history_str += (
                "\nUse this history only to understand follow-up "
                "questions and references.\n"
            )

        routing_hint = self._build_routing_hint(question)

        return f"""{CHAT_SYSTEM_PROMPT}

AVAILABLE TOOLS:
{self.tools_description}

{context_str}

{routing_hint}

{history_str}

{tool_results_str}

CURRENT USER QUESTION:
{question}

IMPORTANT:
- The CURRENT USER QUESTION is the primary task.
- Do not answer a different question just because related information exists in the context.
- Context provides background information.
- For exact dataset questions, prefer the appropriate tool and use its result.
- Never reuse a previous answer for a new question unless the current question genuinely asks for the same information.

TOOL USAGE:
If a tool is needed, respond ONLY with valid JSON:

{{"tool": "tool_name", "input": {{"param": "value"}}}}

Do not add explanation before or after a tool-call JSON.

FINAL ANSWER:
- Answer the CURRENT USER QUESTION directly.
- Use only verified context or tool results.
- Return clean Markdown.
- Use blank lines between sections.
- Use "-" for bullet points.
- Never expose tool JSON.

Your response:"""

    def run(
        self,
        question: str,
        context: dict,
        history: list = None,
    ) -> str:
        """Main execution loop."""
        question = (question or "").strip()

        if not question:
            return (
                "Please enter a question about the dataset."
            )

        context_str = self._format_context(
            context
        )

        tool_results = []

        # Reduced because each iteration is expensive.
        max_iterations = 3

        for _ in range(max_iterations):

            prompt = self._build_prompt(
                question=question,
                context_str=context_str,
                tool_results=tool_results,
                history=history,
            )

            try:
                response_text = (
                    self._call_llm_with_retry(prompt)
                )

            except Exception:
                return self._fallback_answer(
                    question,
                    context,
                )

            response_text = (
                response_text or ""
            ).strip()

            tool_call = self._parse_tool_call(
                response_text
            )

            # Final answer
            if tool_call is None:

                if not response_text:
                    return self._fallback_answer(
                        question,
                        context,
                    )

                return response_text

            # Tool call
            tool_name = tool_call.get(
                "tool"
            )

            tool_input = tool_call.get(
                "input",
                {},
            )

            result = self._execute_tool(
                tool_name,
                tool_input,
                context,
            )

            tool_results.append(
                {
                    "tool": tool_name,
                    "input": tool_input,
                    "output": result,
                }
            )

            # generate_chart is a terminal side-effect tool: once it succeeds
            # (or fails), stop the loop. Otherwise the model often re-calls it
            # until max_iterations and the user only sees the fallback apology.
            if tool_name == "generate_chart" and isinstance(result, dict):
                status = result.get("status")
                if status == "success":
                    chart_meta = result.get("chart") or {}
                    title = chart_meta.get("title") or "New chart"
                    chart_index = result.get("chart_index")
                    total = result.get("total_charts")
                    return (
                        f"I've created a new chart and added it to your "
                        f"**Charts** tab.\n\n"
                        f"- **Title:** {title}\n"
                        f"- **Chart index:** {chart_index}\n"
                        f"- **Total charts now:** {total}\n\n"
                        f"Open the Charts tab to view it."
                    )
                reason = (
                    result.get("reason")
                    or result.get("error")
                    or "Chart generation failed."
                )
                return (
                    f"I couldn't create that chart.\n\n"
                    f"- **Reason:** {reason}"
                )

        return self._fallback_answer(
            question,
            context,
        )