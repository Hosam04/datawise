"""Authenticated user resources — datasets list for post-login rehydration."""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from backend.auth.dependencies import get_current_user
from backend.database.database import get_db
from backend.database.models import Dataset, User

router = APIRouter(prefix="/me", tags=["Me"])


class DatasetOut(BaseModel):
    id: str  # session_id used by the frontend artifact routes
    dataset_uuid: str
    name: str
    original_filename: str
    size: Optional[int] = None
    type: Optional[str] = None
    rows: Optional[int] = None
    status: str
    uploaded_at: Optional[str] = None
    analysis_id: Optional[str] = None


@router.get("/datasets", response_model=List[DatasetOut])
def list_my_datasets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return datasets owned by the current user (newest first)."""
    rows = (
        db.query(Dataset)
        .options(joinedload(Dataset.analyses))
        .filter(Dataset.user_id == current_user.id)
        .order_by(Dataset.created_at.desc())
        .all()
    )
    out: list[DatasetOut] = []
    for ds in rows:
        analyses = sorted(
            ds.analyses or [],
            key=lambda a: a.created_at or a.started_at,
            reverse=True,
        )
        latest = analyses[0] if analyses else None
        status = (latest.status if latest else "unknown") or "unknown"
        session_key = ds.session_id or str(ds.id)
        out.append(
            DatasetOut(
                id=session_key,
                dataset_uuid=str(ds.id),
                name=ds.name or ds.original_filename,
                original_filename=ds.original_filename,
                size=ds.file_size,
                type=ds.mime_type,
                rows=ds.row_count,
                status=status,
                uploaded_at=ds.created_at.isoformat() if ds.created_at else None,
                analysis_id=str(latest.id) if latest else None,
            )
        )
    return out


@router.delete("/datasets/{dataset_id}")
def delete_dataset(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Permanently delete a dataset owned by the current user.

    Accepts either the session_id (used by the frontend) or the UUID primary key.
    Cascades to related analyses via ORM relationship. Reports are preserved
    (analysis_id is SET NULL; ownership stays on Report.user_id).
    """
    from backend.database.models import Analysis, Report

    q = db.query(Dataset).filter(Dataset.user_id == current_user.id)

    # Prefer session_id (what the frontend stores as dataset.id)
    ds = q.filter(Dataset.session_id == dataset_id).first()

    if ds is None:
        # Fallback: treat path param as UUID primary key
        try:
            uuid_val = UUID(dataset_id)
            ds = q.filter(Dataset.id == uuid_val).first()
        except (ValueError, TypeError):
            ds = None

    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Backfill report ownership/label so they remain listed after cascade SET NULL.
    analyses = (
        db.query(Analysis).filter(Analysis.dataset_id == ds.id).all()
    )
    for analysis in analyses:
        for report in analysis.reports or []:
            if report.user_id is None:
                report.user_id = current_user.id
            if not getattr(report, "dataset_label", None):
                report.dataset_label = (
                    ds.original_filename or ds.name or "Dataset"
                )[:255]

    db.delete(ds)
    db.commit()
    return {"ok": True, "deleted_id": dataset_id}


class ReportOut(BaseModel):
    id: str
    title: str
    dataset: str
    type: str
    date: str
    created_at: Optional[str] = None
    dataset_id: Optional[str] = None
    status: str


@router.get("/reports", response_model=List[ReportOut])
def list_my_reports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return reports owned by the current user, newest first.

    Ownership is primarily ``Report.user_id`` so reports survive
    Clean Datasets (dataset/analysis deletion). Fallback for legacy rows:
    Report -> Analysis -> Dataset -> User.
    """
    from backend.database.models import Analysis, Report
    from sqlalchemy import or_

    rows = (
        db.query(Report)
        .outerjoin(Analysis, Report.analysis_id == Analysis.id)
        .outerjoin(Dataset, Analysis.dataset_id == Dataset.id)
        .filter(
            or_(
                Report.user_id == current_user.id,
                Dataset.user_id == current_user.id,
            )
        )
        .order_by(Report.created_at.desc())
        .all()
    )

    out: list[ReportOut] = []
    for report in rows:
        analysis = report.analysis
        dataset = analysis.dataset if analysis else None
        dataset_name = (
            (dataset.original_filename if dataset else None)
            or getattr(report, "dataset_label", None)
            or "Dataset"
        )
        out.append(
            ReportOut(
                id=str(report.id),
                title=report.title,
                dataset=dataset_name,
                type="AI Analysis",
                date=report.created_at.isoformat() if report.created_at else "",
                created_at=report.created_at.isoformat() if report.created_at else None,
                dataset_id=(dataset.session_id or str(dataset.id)) if dataset else None,
                status=report.status,
            )
        )
    return out


@router.delete("/reports/{report_id}")
def delete_my_report(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete one of the current user's reports."""
    from backend.database.models import Analysis, Report
    from sqlalchemy import or_

    try:
        report_uuid = UUID(report_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=404, detail="Report not found")

    report = (
        db.query(Report)
        .outerjoin(Analysis, Report.analysis_id == Analysis.id)
        .outerjoin(Dataset, Analysis.dataset_id == Dataset.id)
        .filter(
            Report.id == report_uuid,
            or_(
                Report.user_id == current_user.id,
                Dataset.user_id == current_user.id,
            ),
        )
        .first()
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    db.delete(report)
    db.commit()
    return {"ok": True, "deleted_id": report_id}