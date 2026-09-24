"""Unit tests: ChatAgent routes drawing / chart-creation requests to generate_chart
(which delegates to VisualizationAgent / vis agent).

These tests cover the routing layer so that phrases like "draw a chart",
"plot age", "visualize sales" force the generate_chart tool instead of plain
text answers or get_chart_data (explain-existing).
"""

from __future__ import annotations

import inspect
import sys
import types
from unittest.mock import MagicMock, patch

import pytest


def _ensure_chat_agent_importable():
    """Stub optional heavy deps so ChatAgent can be imported in a minimal env.

    Production test runs that already have langchain / gemini installed will
    simply use the real modules; the stubs only fill gaps.
    """
    stubs = {
        "langchain_google_genai": MagicMock(),
        "langchain_core": MagicMock(),
        "langchain_core.tools": MagicMock(),
        "langchain_core.messages": MagicMock(),
    }
    for name, mod in stubs.items():
        sys.modules.setdefault(name, mod)

    if "backend.tools.dataframe_tools" not in sys.modules:
        fake_tools = types.ModuleType("backend.tools.dataframe_tools")
        for name in (
            "get_row",
            "calculate_percentage",
            "filter_rows",
            "dataset_info",
            "get_column_stats",
            "get_unique_values",
            "get_ml_analysis",
            "get_chart_data",
            "generate_chart",
        ):
            t = MagicMock()
            t.description = (
                f"Tool {name}. Use when the user asks to draw / plot / create a chart."
                if name == "generate_chart"
                else f"Tool {name}"
            )
            setattr(fake_tools, name, t)
        sys.modules["backend.tools.dataframe_tools"] = fake_tools

    if "backend.llm.prompts" not in sys.modules:
        fake_prompts = types.ModuleType("backend.llm.prompts")
        fake_prompts.CHAT_SYSTEM_PROMPT = "system"
        sys.modules["backend.llm.prompts"] = fake_prompts

    if "backend.llm.gemini_client" not in sys.modules:
        fake_gemini = types.ModuleType("backend.llm.gemini_client")
        fake_gemini.get_chat_model = MagicMock(return_value=MagicMock())
        sys.modules["backend.llm.gemini_client"] = fake_gemini


_ensure_chat_agent_importable()


@pytest.fixture
def chat_agent():
    """ChatAgent with LLM mocked so tests never hit Gemini."""
    _ensure_chat_agent_importable()
    with patch("backend.agents.chat.chat_agent.get_chat_model", return_value=MagicMock()):
        from backend.agents.chat.chat_agent import ChatAgent

        yield ChatAgent()


# ---------------------------------------------------------------------------
# 1. Drawing / creation phrases → generate_chart (vis agent path)
# ---------------------------------------------------------------------------

DRAW_PHRASES = [
    "draw a histogram of age",
    "draw a chart of sales by region",
    "draw this as a bar chart",
    "generate chart for revenue",
    "generate a chart of temperature",
    "generate graph of clicks over time",
    "generate a graph showing conversion",
    "create chart of price vs quantity",
    "create a chart for categories",
    "create graph of daily active users",
    "create a graph of residuals",
    "make a chart of feature importance",
    "make chart for age distribution",
    "make a graph of sales",
    "make graph of profit",
    "plot a scatter of height and weight",
    "plot the line chart of revenue",
    "plot me a box plot of salary by department",
    "plot this as a pie chart",
    "show me a chart of monthly sales",
    "show a chart for churn rate",
    "show me a graph of traffic",
    "show a graph of errors",
    "visualize the correlation matrix",
    "visualise age distribution",
]


@pytest.mark.parametrize("question", DRAW_PHRASES)
def test_draw_phrases_route_to_generate_chart(chat_agent, question):
    """Any draw/plot/create/visualize signal must route to generate_chart."""
    tool = chat_agent._detect_required_tool(question)
    assert tool == "generate_chart", (
        f"Expected generate_chart for {question!r}, got {tool!r}"
    )


def test_draw_phrases_case_insensitive(chat_agent):
    """Routing is case-insensitive."""
    assert chat_agent._detect_required_tool("DRAW A BAR CHART OF AGE") == "generate_chart"
    assert chat_agent._detect_required_tool("Plot A Scatter Of X And Y") == "generate_chart"
    assert chat_agent._detect_required_tool("Visualize Sales") == "generate_chart"


# ---------------------------------------------------------------------------
# 2. Explain-existing chart phrases → get_chart_data (NOT generate_chart)
# ---------------------------------------------------------------------------

EXPLAIN_PHRASES = [
    "explain the chart",
    "describe the chart",
    "what does this chart show",
    "tell me about the histogram",
    "explain this scatter plot",
    "what is the box plot saying",
    "describe the heatmap",
    "explain the confusion matrix",
]


@pytest.mark.parametrize("question", EXPLAIN_PHRASES)
def test_explain_existing_routes_to_get_chart_data(chat_agent, question):
    """Phrases about existing charts must NOT trigger generate_chart."""
    tool = chat_agent._detect_required_tool(question)
    assert tool == "get_chart_data", (
        f"Expected get_chart_data for {question!r}, got {tool!r}"
    )


def test_bare_chart_word_routes_to_get_chart_data(chat_agent):
    """A bare 'chart' without create/draw signals → explain path."""
    tool = chat_agent._detect_required_tool("what about the chart?")
    assert tool == "get_chart_data"


# ---------------------------------------------------------------------------
# 3. generate_chart takes priority over get_chart_data when both match
# ---------------------------------------------------------------------------

def test_draw_beats_generic_chart_word(chat_agent):
    """'draw a chart' contains both 'draw' and 'chart' → must be generate_chart."""
    assert chat_agent._detect_required_tool("draw a chart of age") == "generate_chart"
    assert chat_agent._detect_required_tool("create a chart please") == "generate_chart"
    assert chat_agent._detect_required_tool("plot a histogram") == "generate_chart"


# ---------------------------------------------------------------------------
# 4. Tool registry: generate_chart is wired
# ---------------------------------------------------------------------------

def test_generate_chart_tool_is_registered(chat_agent):
    """ChatAgent must expose generate_chart in its tools dict."""
    assert "generate_chart" in chat_agent.tools
    tool = chat_agent.tools["generate_chart"]
    assert tool is not None
    assert hasattr(tool, "description")
    desc = (getattr(tool, "description", None) or "").lower()
    assert "draw" in desc or "plot" in desc or "chart" in desc


def test_generate_chart_implementation_uses_visualization_agent():
    """Source of generate_chart must import and call VisualizationAgent.

    Lightweight static check so a future refactor cannot silently drop the
    vis-agent handoff. Reads the source file directly to avoid depending on
    a fully importable dataframe_tools module.
    """
    from pathlib import Path

    # generate_chart lives in dataframe_ml_chart after the dataframe_tools split
    candidates = [
        Path(__file__).resolve().parents[3] / "tools" / "dataframe_ml_chart.py",
        Path("backend/tools/dataframe_ml_chart.py"),
        # legacy monolithic path (pre-split) — keep as last fallback
        Path(__file__).resolve().parents[3] / "tools" / "dataframe_tools.py",
        Path("backend/tools/dataframe_tools.py"),
    ]

    src_path = next((p for p in candidates if p.is_file()), None)
    if src_path is None:
        pytest.skip("generate_chart source not found (dataframe_ml_chart.py / dataframe_tools.py)")

    source = src_path.read_text(encoding="utf-8")
    assert "def generate_chart(" in source
    assert "VisualizationAgent" in source
    assert "viz_agent" in source or "VisualizationAgent()" in source


# ---------------------------------------------------------------------------
# 5. Routing hint forces the LLM to call generate_chart for draw requests
# ---------------------------------------------------------------------------

def test_build_routing_hint_for_draw_forces_generate_chart(chat_agent):
    """_build_routing_hint must force a generate_chart tool call for draw requests."""
    hint = chat_agent._build_routing_hint("draw a bar chart of age")
    assert "generate_chart" in hint
    assert "MUST call" in hint or "MUST respond" in hint
    assert "get_chart_data" in hint  # explicitly tells LLM not to use it
    assert "DRAW / CREATE" in hint or "draw" in hint.lower()


def test_build_routing_hint_for_explain_uses_get_chart_data(chat_agent):
    """Explain-existing should prefer get_chart_data, not force generate_chart."""
    preferred = chat_agent._detect_required_tool("explain the chart")
    assert preferred == "get_chart_data"
    hint = chat_agent._build_routing_hint("explain the chart")
    # Generic hint mentions the preferred tool name
    assert "get_chart_data" in hint
    assert "MUST call the `generate_chart`" not in hint


# ---------------------------------------------------------------------------
# 6. Non-chart questions do not accidentally route to generate_chart
# ---------------------------------------------------------------------------

NON_CHART_PHRASES = [
    "how many rows are in the dataset?",
    "what is the average age?",
    "filter rows where salary > 50000",
    "show unique values of department",
    "what is the accuracy of the model?",
    "calculate the percentage of missing values",
]


@pytest.mark.parametrize("question", NON_CHART_PHRASES)
def test_non_chart_questions_do_not_route_to_generate_chart(chat_agent, question):
    tool = chat_agent._detect_required_tool(question)
    assert tool != "generate_chart", (
        f"Unexpected generate_chart routing for non-chart question: {question!r}"
    )