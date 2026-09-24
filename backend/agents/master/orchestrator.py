from langgraph.graph import StateGraph, END
from backend.core.state import AgentState

from backend.agents.planner.planner_agent import PlannerAgent
from backend.agents.data.data_agent import DataAgent
from backend.agents.insights.insights_agent import InsightsAgent
from backend.agents.visualization.viz_agent import VisualizationAgent
from backend.agents.report.report_builder_agent import ReportBuilderAgent
from backend.agents.report.report_generator import ReportGeneratorAgent
from backend.agents.profile.dataset_profile_agent import DatasetProfileAgent

# NEW: ML Agents
from backend.agents.model_selection.model_selection_agent import ModelSelectionAgent
from backend.ml.analyzer import MLAnalyzer

from backend.utils.logger import setup_logger

logger = setup_logger("MasterOrchestrator")
ml_analyzer_instance = MLAnalyzer()

def create_workflow():
    print("ENTRY POINT SHOULD BE DATA_AGENT")
    logger.info("Initializing DataWise Workflow Graph...")

    workflow = StateGraph(AgentState)

    planner = PlannerAgent()
    data = DataAgent()
    insights = InsightsAgent()
    viz = VisualizationAgent()
    report_builder = ReportBuilderAgent()
    report_generator = ReportGeneratorAgent()
    profile_agent = DatasetProfileAgent()

    # NEW: ML agents
    model_selection = ModelSelectionAgent()


    workflow.add_node("data_agent", data.run)
    workflow.add_node("dataset_profile", profile_agent.run)

    # NEW: ML nodes
    workflow.add_node("model_selection", model_selection.run)
    workflow.add_node("ml_analyzer", _ml_analyzer_node)

    workflow.add_node("planner", planner.run)
    workflow.add_node("insights", insights.run)
    workflow.add_node("viz", viz.run)
    workflow.add_node("report_builder", report_builder.run)
    workflow.add_node("reporter", report_generator.run)

    workflow.set_entry_point("data_agent")

    # Original flow with ML inserted between profile and planner
    workflow.add_edge("data_agent", "dataset_profile")
    workflow.add_edge("dataset_profile", "model_selection")
    workflow.add_edge("model_selection", "ml_analyzer")
    workflow.add_edge("ml_analyzer", "planner")
    workflow.add_edge("planner", "insights")
    workflow.add_edge("insights", "viz")
    workflow.add_edge("viz", "report_builder")
    workflow.add_edge("report_builder", "reporter") 

    logger.info("Workflow graph compiled successfully.")

    return workflow.compile()


def _ml_analyzer_node(state: AgentState) -> AgentState:
    """Wrapper node to run MLAnalyzer with state data."""
    ml_results_state = state.ml_results

    if not ml_results_state or ml_results_state.status == "skipped":
        logger.info("ML skipped by ModelSelectionAgent.")
        return state

    df = state.get_df()
    target = state.target_detection.get("target_column") if state.target_detection else None

    if df is None or not target:
        logger.warning("MLAnalyzer: Missing df or target. Skipping.")
        from backend.ml.schemas import MLResults
        state.ml_results = MLResults(status="skipped", reason="Missing df or target")
        return state

    try:
        results = ml_analyzer_instance.run(
            df=df,
            target=target,
            selected_model=ml_results_state.selected_model,
            fallback_model=ml_results_state.fallback_model,
            problem_type=ml_results_state.problem_type or "classification",
            profile=state.dataset_profile or {},
        )
        state.ml_results = results
        logger.info(f"MLAnalyzer completed with status: {results.status}")
    except Exception as e:
        logger.error(f"MLAnalyzer failed: {e}")
        from backend.ml.schemas import MLResults
        state.ml_results = MLResults(
            status="failed",
            reason=f"MLAnalyzer execution error: {str(e)}",
            selected_model=ml_results_state.selected_model,
        )

    return state