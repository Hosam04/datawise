"""Favorites API — persist user-saved datasets and reports."""
from __future__ import annotations

import uuid
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.auth.dependencies import get_current_user
from backend.database.database import get_db
from backend.database.models import Dataset, Favorite, Report, User

router = APIRouter(prefix="/favorites", tags=["Favorites"])


class FavoriteIn(BaseModel):
    id: str = Field(..., description="Frontend item id (usually session_id for datasets)")
    name: str
    type: Literal["dataset", "report"]
    description: str = ""


class FavoriteOut(BaseModel):
    id: str
    name: str
    type: str
    description: str

    class Config:
        from_attributes = True


def _to_out(row: Favorite) -> FavoriteOut:
    return FavoriteOut(
        id=row.item_id,
        name=row.name,
        type=row.item_type,
        description=row.description or "",
    )


def _resolve_dataset_id(db: Session, item_id: str) -> Optional[uuid.UUID]:
    """Map FE id (session_id or dataset UUID) to datasets.id if it exists."""
    # Prefer session_id — that is what the frontend stores as Dataset.id
    ds = db.query(Dataset).filter(Dataset.session_id == item_id).first()
    if ds:
        return ds.id
    try:
        uid = uuid.UUID(item_id)
    except ValueError:
        return None
    ds = db.query(Dataset).filter(Dataset.id == uid).first()
    return ds.id if ds else None


def _resolve_report_id(db: Session, item_id: str) -> Optional[uuid.UUID]:
    try:
        uid = uuid.UUID(item_id)
    except ValueError:
        return None
    rep = db.query(Report).filter(Report.id == uid).first()
    return rep.id if rep else None


@router.get("", response_model=List[FavoriteOut])
@router.get("/", response_model=List[FavoriteOut], include_in_schema=False)
def list_favorites(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Favorite)
        .filter(Favorite.user_id == current_user.id)
        .order_by(Favorite.created_at.desc())
        .all()
    )
    return [_to_out(r) for r in rows]


@router.post("", response_model=FavoriteOut, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=FavoriteOut, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def add_favorite(
    body: FavoriteIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = (
        db.query(Favorite)
        .filter(
            Favorite.user_id == current_user.id,
            Favorite.item_id == body.id,
        )
        .first()
    )
    if existing:
        existing.name = body.name[:255]
        existing.description = body.description or None
        existing.item_type = body.type
        db.commit()
        db.refresh(existing)
        return _to_out(existing)

    dataset_id = None
    report_id = None
    if body.type == "dataset":
        dataset_id = _resolve_dataset_id(db, body.id)
    elif body.type == "report":
        report_id = _resolve_report_id(db, body.id)

    row = Favorite(
        user_id=current_user.id,
        item_id=body.id,
        item_type=body.type,
        name=body.name[:255],
        description=body.description or None,
        dataset_id=dataset_id,  # only set when row exists — avoids FK violation
        report_id=report_id,
    )
    db.add(row)
    try:
        db.commit()
        db.refresh(row)
    except Exception as exc:
        db.rollback()
        # Most common failure was FK: item_id was session_id forced into dataset_id
        raise HTTPException(
            status_code=400,
            detail=f"Could not save favorite: {exc}",
        ) from exc
    return _to_out(row)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(
    item_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(Favorite)
        .filter(
            Favorite.user_id == current_user.id,
            Favorite.item_id == item_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Favorite not found")
    db.delete(row)
    db.commit()
    return None
