from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from backend.agents.master.orchestrator import create_workflow
from backend.core.state import AgentState
import shutil
import os
import uuid
import logging
from concurrent.futures import ThreadPoolExecutor
from backend.auth.router import router as auth_router
from backend.database.database import engine
from backend.database.base import Base
from fastapi.middleware.cors import CORSMiddleware
from backend.app.routes.artifacts import router as artifacts_router
from backend.app.routes.chat import router as chat_router
from backend.app.routes.favorites import router as favorites_router
from backend.app.routes.me import router as me_router
from backend.app.routes.profiles import router as profiles_router
from backend.core.storage import analysis_repository
from backend.app.routes import charts
from backend.core.config import Config
from datetime import date, datetime
from backend.auth.dependencies import get_current_user, get_current_user_optional
from backend.database.database import get_db, SessionLocal
from backend.database.models import User, Analysis, Favorite, Dataset  # noqa: F401 — register mapper
import backend.database.models  # noqa: F401 — ensure all tables registered for create_all
from backend.services.analysis_service import (
    create_dataset_and_analysis,
    complete_analysis,
    mark_analysis_failed,
)
from backend.services.workflow_service import _run_workflow_sync
from sqlalchemy.orm import Session
from fastapi import Depends
import numpy as np

logger = logging.getLogger("main")
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["Content-Disposition"],
)

app.include_router(charts.router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(artifacts_router)
app.include_router(favorites_router)
app.include_router(me_router)
app.include_router(profiles_router)

executor = ThreadPoolExecutor(max_workers=3)


@app.post("/analyze-data/")
async def analyze_data(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    query: str,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    session_id = str(uuid.uuid4())
    analysis_repository.create(session_id)
    session_dir = os.path.join(Config.STORAGE_PATH, "sessions", session_id)
    os.makedirs(session_dir, exist_ok=True)

    safe_filename = file.filename.replace(" ", "_") if file.filename else "dataset"
    file_path = os.path.join(session_dir, safe_filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save file: {str(e)}")

    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else None

    dataset, analysis = create_dataset_and_analysis(
        db,
        user_id=current_user.id,
        session_id=session_id,
        original_filename=file.filename or safe_filename,
        file_path=file_path,
        file_size=file_size,
        mime_type=file.content_type,
        user_query=query,
    )

    background_tasks.add_task(
        _run_workflow_sync,
        session_id,
        file_path,
        session_dir,
        query,
        str(analysis.id),
    )

    return {
        "status": "processing",
        "session_id": session_id,
        "dataset_id": str(dataset.id),
        "analysis_id": str(analysis.id),
        "check_status": f"/status/{session_id}",
    }


@app.get("/me/datasets")
def list_my_datasets_inline(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List datasets for the logged-in user (session_id as id for FE artifacts)."""
    from sqlalchemy.orm import joinedload

    rows = (
        db.query(Dataset)
        .options(joinedload(Dataset.analyses))
        .filter(Dataset.user_id == current_user.id)
        .order_by(Dataset.created_at.desc())
        .all()
    )
    out = []
    for ds in rows:
        analyses = sorted(
            ds.analyses or [],
            key=lambda a: (a.created_at or a.started_at or ds.created_at),
            reverse=True,
        )
        latest = analyses[0] if analyses else None
        status = (latest.status if latest else "unknown") or "unknown"
        session_key = ds.session_id or str(ds.id)
        out.append({
            "id": session_key,
            "dataset_uuid": str(ds.id),
            "name": ds.name or ds.original_filename,
            "original_filename": ds.original_filename,
            "size": ds.file_size,
            "type": ds.mime_type,
            "rows": ds.row_count,
            "status": status,
            "uploaded_at": ds.created_at.isoformat() if ds.created_at else None,
            "analysis_id": str(latest.id) if latest else None,
        })
    return out


@app.get("/status/{session_id}")
async def get_status(session_id: str):
    """Check analysis status"""
    result = analysis_repository.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return {"status": result["status"], **({"error": result["error"]} if result.get("error") else {})}


@app.get("/")
async def root():
    return {
        "message": "DataWise API",
        "endpoints": {
            "analyze": "POST /analyze-data/",
            "status": "GET /status/{session_id}",
            "auth": {
                "register": "POST /auth/register",
                "login": "POST /auth/login",
                "google": "POST /auth/google",
                "refresh": "POST /auth/refresh",
                "me": "GET /auth/me",
            },
        },
    }


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)