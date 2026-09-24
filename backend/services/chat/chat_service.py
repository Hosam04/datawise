"""Chat service for the DataWise API.

Handles dataset retrieval, context building, and chat orchestration.
"""
import os
import json
import traceback
from typing import Optional

from backend.agents.chat.chat_agent import ChatAgent
from backend.core.storage import analysis_repository
from backend.tools.dataframe_exploration import dataset_info
from backend.database.models import (
    User,
    Dataset,
    Analysis,
    ChatConversation,
    ChatMessage,
)
from sqlalchemy.orm import Session

from backend.core.config import Config


chat_agent = ChatAgent()


def _resolve_df_path(dataset_id: str, df_path: Optional[str]) -> Optional[str]:
    """Resolve dataset file path to absolute path."""
    if not df_path:
        return None
    
    if os.path.isabs(df_path):
        return df_path if os.path.exists(df_path) else None
    
    from backend.core.config import Config
    # Try the path relative to storage
    full_path = os.path.join(Config.STORAGE_PATH, "sessions", dataset_id, os.path.basename(df_path))
    if os.path.exists(full_path):
        return full_path
    
    # Try alternate location
    alt_path = os.path.join(Config.STORAGE_PATH, "sessions", dataset_id, "df.pkl")
    if os.path.exists(alt_path):
        return alt_path
    
    return None


def _fetch_real_data_facts(df_path: Optional[str]) -> dict:
    """Fetch dataset info using the dataset_info tool."""
    if not df_path or not os.path.exists(df_path):
        return {"error": f"Dataset file not found at path: '{df_path}'. Using stored analysis data."}
    
    try:
        real_data_facts = dataset_info.invoke({"df_path": df_path})
        if not isinstance(real_data_facts, dict):
            return {"error": f"Unexpected response type: {type(real_data_facts)}"}
        return real_data_facts
    except Exception as e:
        return {"error": f"Failed to fetch dataset info: {str(e)}"}


def _build_evidence(dataset: dict) -> dict:
    """Build unified evidence object from dataset analysis results."""
    ml_analysis = dataset.get("ml_analysis") or {}
    
    return {
        "dataset_profile": dataset.get("dataset_profile", {}),
        "statistics": dataset.get("statistics", {}),
        "correlations": dataset.get("correlations", {}),
        "ml_results": ml_analysis.get("results"),
        "insights": dataset.get("insights", {}),
        "target_detection": (
            dataset.get("target_detection")
            or ml_analysis.get("target_detection", {})
        ),
    }


def _build_context(dataset_id: str, df_path: Optional[str], dataset: dict, real_data_facts: dict) -> dict:
    """Build context dictionary for the chat agent."""
    ml_analysis = dataset.get("ml_analysis") or {}
    
    return {
        "dataset_id": dataset_id,
        "df_path": df_path if (df_path and os.path.exists(df_path)) else None,
        "REAL_DATA_FACTS": real_data_facts,
        "dataset_overview": dataset.get("preview", {}),
        "evidence": _build_evidence(dataset),
        "ml_available": bool(ml_analysis.get("results")),
    }


def _persist_chat(
    db: Session,
    current_user: Optional[User],
    dataset_id: str,
    message: str,
    answer: str,
    dataset: dict,
) -> None:
    """Persist chat messages to PostgreSQL (best-effort)."""
    if not current_user:
        return
    
    try:
        # Find Dataset / Analysis by session_id
        db_dataset = (
            db.query(Dataset)
            .filter(Dataset.session_id == dataset_id)
            .first()
        )
        analysis_id = None
        dataset_uuid = None
        if db_dataset is not None:
            dataset_uuid = db_dataset.id
            latest_analysis = (
                db.query(Analysis)
                .filter(Analysis.dataset_id == db_dataset.id)
                .order_by(Analysis.created_at.desc())
                .first()
            )
            if latest_analysis is not None:
                analysis_id = latest_analysis.id

        # Reuse existing conversation or create new
        conversation = None
        if dataset_uuid is not None:
            conversation = (
                db.query(ChatConversation)
                .filter(
                    ChatConversation.user_id == current_user.id,
                    ChatConversation.dataset_id == dataset_uuid,
                )
                .order_by(ChatConversation.created_at.desc())
                .first()
            )
        if conversation is None:
            conversation = ChatConversation(
                user_id=current_user.id,
                dataset_id=dataset_uuid,
                analysis_id=analysis_id,
                title=(message[:100] if message else "Chat")[:255],
            )
            db.add(conversation)
            db.flush()

        # User message
        db.add(
            ChatMessage(
                conversation_id=conversation.id,
                role="user",
                content=message,
            )
        )
        # Assistant reply
        db.add(
            ChatMessage(
                conversation_id=conversation.id,
                role="assistant",
                content=answer,
            )
        )
        db.commit()
    except Exception as persist_err:
        db.rollback()
        traceback.print_exc()
        print(f"Chat persistence failed (non-fatal): {persist_err}")


async def chat_with_dataset(
    dataset_id: str,
    message: str,
    current_user: Optional[User],
    db: Session,
):
    """Main chat endpoint logic."""
    from fastapi.responses import JSONResponse
    
    dataset_id = dataset_id.strip()
    message = message.strip()
    
    if not dataset_id:
        return JSONResponse(status_code=422, content={"detail": "dataset_id is required."})
    if not message:
        return JSONResponse(status_code=422, content={"detail": "message cannot be empty."})
    
    try:
        dataset = analysis_repository.get(dataset_id)
        if dataset is None:
            return JSONResponse(status_code=404, content={"detail": "Dataset not found. Use the session_id returned by /analyze-data/."})
        
        if dataset["status"] == "processing":
            return JSONResponse(status_code=409, content={"detail": "Dataset analysis is still in progress."})
        
        if dataset["status"] != "completed":
            return JSONResponse(status_code=409, content={"detail": f"Dataset analysis failed: {dataset.get('error', 'Unknown error')}"})
        
        # Resolve and fetch data
        df_path = _resolve_df_path(dataset_id, dataset.get("df_path"))
        real_data_facts = _fetch_real_data_facts(df_path)
        context = _build_context(dataset_id, df_path, dataset, real_data_facts)
        
        # Run chat agent
        answer = chat_agent.run(question=message, context=context)
        
        if not isinstance(answer, str):
            answer = str(answer)
        
        # Persist chat (best-effort)
        _persist_chat(db, current_user, dataset_id, message, answer, dataset)
        
        return JSONResponse(content={"answer": answer, "status": "completed", "session_id": dataset_id})
    
    except Exception as error:
        traceback.print_exc()
        return JSONResponse(
            status_code=500, 
            content={
                "detail": f"Unable to process chat request: {str(error)}",
                "error_type": type(error).__name__
            }
        )