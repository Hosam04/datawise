"""Workflow execution service for the DataWise analysis pipeline."""
import os
import uuid
import traceback
from datetime import date, datetime

from backend.agents.master.orchestrator import create_workflow
from backend.core.state import AgentState
from backend.core.config import Config
from backend.core.storage import analysis_repository
from backend.database.database import SessionLocal
from backend.database.models import Analysis
from backend.services.analysis_service import complete_analysis, mark_analysis_failed
from backend.services.insights_parser import parse_insights_report, _empty_insights


def _sanitize_for_json(obj):
    """Recursively replace NaN, Inf, -Inf with None and handle numpy/pandas types."""
    import math
    if obj is None:
        return None
    if isinstance(obj, (str, int, bool)):
        return obj
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    if hasattr(obj, "item"):  # numpy types
        return _sanitize_for_json(obj.item())
    try:
        if obj != obj:  # NaN check
            return None
    except (TypeError, ValueError):
        pass
    return str(obj)


def _run_workflow_sync(
    session_id: str,
    file_path: str,
    session_dir: str,
    query: str,
    analysis_id: str | None = None,
):
    """Execute the analysis workflow synchronously in a background task."""
    print("START WORKFLOW:", session_id)

    try:
        initial_state = AgentState(
            session_id=session_id,
            session_dir=session_dir,
            file_path=file_path,
            user_query=query,
        )

        print("Creating workflow")
        app_graph = create_workflow()
        print("Invoking workflow")
        result = app_graph.invoke(initial_state)
        print("Workflow finished")

        db = SessionLocal()

        result_state = AgentState.model_validate(result)

        summary = result_state.data_summary

        # ─── SANITIZE EVERYTHING BEFORE STORAGE ───
        # Ensure insights is always a proper dict
        insights = parse_insights_report(result_state.insights)
        if not isinstance(insights, dict):
            insights = _empty_insights()

        # Ensure data_quality is always a dict
        if not isinstance(insights.get("data_quality"), dict):
            insights["data_quality"] = {"issues": [], "score": None}

        # Build chart list safely
        chart_list = []
        viz_paths = result_state.visualization_paths or []
        for index in range(len(viz_paths)):
            chart_list.append({
                "id": index,
                "url": f"/datasets/{session_id}/charts/{index}"
            })

        # ─── ML ANALYSIS ───
        # This was previously computed by the workflow (result_state.ml_results /
        # result_state.target_detection) but never copied into the stored
        # payload, so backend.tools.dataframe_tools.get_ml_analysis() -- the
        # tool the chat agent is instructed to call for prediction/model
        # questions -- always found "ml_analysis" missing and reported ML as
        # unavailable, even when the pipeline had produced real results.
        ml_analysis = {
            "target_detection": result_state.target_detection or {},
            "results": (
                result_state.ml_results.model_dump()
                if result_state.ml_results is not None
                else None
            ),
        }

        payload = {
            "original_filename": os.path.basename(result_state.file_path),
            "df_path": result_state.df_path,
            "preview": {
                "columns": summary.get("columns", []),
                "rows": summary.get("rows", []),
                "total_rows": summary.get("total_rows", 0),
                "total_cols": summary.get("total_cols", 0),
            },
            # Numeric descriptive stats + categorical summaries (kept under
            # one map so the artifacts API / frontend table see every column
            # the StatisticalEngine produced, not only numeric ones).
            "statistics": {
                **(summary.get("statistics") or {}),
                **(summary.get("categorical_statistics") or {}),
            },
            "categorical_statistics": summary.get("categorical_statistics") or {},
            "correlations": summary.get("correlation", {}),
            "outliers": summary.get("outliers", {}),
            "insights": insights,
            "ml_analysis": ml_analysis,
            # ─── EVIDENCE FIELDS ───
            # dataset_profile / target_detection were already computed by the
            # workflow (DatasetProfileAgent / target_detection utils) but were
            # never persisted into the stored payload, so the chat endpoint's
            # evidence object could never surface them. Store them top-level
            # (target_detection is also kept nested under ml_analysis above
            # for backward compatibility with existing readers).
            "dataset_profile": result_state.dataset_profile or {},
            "target_detection": result_state.target_detection or {},
            "charts": chart_list,
            "chartData": result_state.visualizations or [],
            "chart_paths": viz_paths,
            "report": {"url": f"/datasets/{session_id}/report/download"},
            "report_path": result_state.final_report_path,
            "plan": (
                result_state.plan.model_dump()
                if result_state.plan is not None and hasattr(result_state.plan, "model_dump")
                else result_state.plan
            ),
            "cleaning_report": summary.get("cleaning_report") or {},
            "analysis_type": result_state.analysis_type,
        }

        safe_payload = _sanitize_for_json(payload)
        analysis_repository.complete(session_id, safe_payload)

        if analysis_id:
            try:
                # Log what we are about to persist so missing actions are visible in server logs
                cr = safe_payload.get("cleaning_report") or {}
                n_actions = 0
                if isinstance(cr, dict):
                    for k in ("actions", "applied_actions", "actions_applied"):
                        if isinstance(cr.get(k), list):
                            n_actions = max(n_actions, len(cr[k]))
                    steps = cr.get("cleaning_steps") or []
                    if isinstance(steps, list):
                        for step in steps:
                            if isinstance(step, dict) and isinstance(step.get("applied_actions"), list):
                                n_actions = max(n_actions, len(step["applied_actions"]))
                print(
                    f"PERSIST DB analysis_id={analysis_id} "
                    f"cleaning_actions_detected={n_actions} "
                    f"insights={len((safe_payload.get('insights') or {}).get('key_findings') or [])}"
                )
                complete_analysis(
                    db,
                    analysis_id=uuid.UUID(analysis_id),
                    payload=safe_payload,
                )
                print(f"PERSIST DB OK analysis_id={analysis_id}")
            except Exception as persist_err:
                # File/manifest artifacts are already saved; do not fail the whole run
                # if PostgreSQL persistence has a transient error.
                print(f"PERSIST DB FAILED analysis_id={analysis_id}: {persist_err}")
                traceback.print_exc()
                try:
                    db.rollback()
                except Exception:
                    pass

    except Exception as e:
        print("WORKFLOW ERROR:", e)
        traceback.print_exc()
        analysis_repository.fail(session_id, str(e))
        try:
            if analysis_id:
                # db may not exist if failure happened before SessionLocal()
                _db = locals().get("db")
                if _db is not None:
                    mark_analysis_failed(_db, uuid.UUID(analysis_id), str(e))
        except Exception as mark_err:
            print(f"mark_analysis_failed also failed: {mark_err}")
    finally:
        _db = locals().get("db")
        if _db is not None:
            try:
                _db.close()
            except Exception:
                pass