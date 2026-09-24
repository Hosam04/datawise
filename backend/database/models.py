from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    BigInteger,
    Numeric,
    String,
    Text,
    Float,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database.base import Base


# ────────────────────────────────────────────────────────────
# USERS
# ────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Schema was VARCHAR(100); expand to 255 via ALTER (see notes).
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    # Nullable so Google/OAuth accounts can exist without a local password.
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    picture: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=False,
        server_default=func.now(),
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    datasets: Mapped[List["Dataset"]] = relationship(
        "Dataset",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    chat_conversations: Mapped[List["ChatConversation"]] = relationship(
        "ChatConversation",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    favorites: Mapped[List["Favorite"]] = relationship(
        "Favorite",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="Favorite.user_id",
    )


# ────────────────────────────────────────────────────────────
# DATASETS
# ────────────────────────────────────────────────────────────

class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    # Nullable to match deployed schema (size/mime may be filled after upload).
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    schema_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Requires ALTER on live DB if column is missing (see notes).
    dataset_fingerprint: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    row_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    column_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=False,
        server_default=func.now(),
    )

    owner: Mapped["User"] = relationship("User", back_populates="datasets")
    analyses: Mapped[List["Analysis"]] = relationship(
        "Analysis",
        back_populates="dataset",
        cascade="all, delete-orphan",
    )
    
    chat_conversations: Mapped[List["ChatConversation"]] = relationship(
        "ChatConversation",
        back_populates="dataset",
        passive_deletes=True,
    )


# ────────────────────────────────────────────────────────────
# ANALYSES
# ────────────────────────────────────────────────────────────

class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_query: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    analysis_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # Match schema VARCHAR(30).
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending", index=True
    )
    target_column: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target_detection: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    plan_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    statistics_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    evidence_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=False,
        server_default=func.now(),
    )

    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="analyses")
    profile: Mapped[Optional["DatasetProfile"]] = relationship(
        "DatasetProfile",
        back_populates="analysis",
        uselist=False,
        cascade="all, delete-orphan",
    )
    cleaning_run: Mapped[Optional["CleaningRun"]] = relationship(
        "CleaningRun",
        back_populates="analysis",
        uselist=False,
        cascade="all, delete-orphan",
    )
    ml_result: Mapped[Optional["MLResult"]] = relationship(
        "MLResult",
        back_populates="analysis",
        uselist=False,
        cascade="all, delete-orphan",
    )
    insights: Mapped[List["Insight"]] = relationship(
        "Insight",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )
    visualizations: Mapped[List["Visualization"]] = relationship(
        "Visualization",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )
    # Reports survive analysis/dataset deletion (FK is ON DELETE SET NULL).
    reports: Mapped[List["Report"]] = relationship(
        "Report",
        back_populates="analysis",
        passive_deletes=True,
    )
    # FK is ON DELETE SET NULL — do NOT use delete-orphan.
    chat_conversations: Mapped[List["ChatConversation"]] = relationship(
        "ChatConversation",
        back_populates="analysis",
        passive_deletes=True,
    )


# ────────────────────────────────────────────────────────────
# DATASET PROFILE
# ────────────────────────────────────────────────────────────

class DatasetProfile(Base):
    __tablename__ = "dataset_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )
    row_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    column_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    target_column: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target_confidence: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    columns_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    profile_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="profile")


# ────────────────────────────────────────────────────────────
# CLEANING
# ────────────────────────────────────────────────────────────

class CleaningRun(Base):
    __tablename__ = "cleaning_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending", index=True
    )
    initial_rows: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    final_rows: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    initial_columns: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    final_columns: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    summary_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    analysis: Mapped["Analysis"] = relationship(
        "Analysis", back_populates="cleaning_run"
    )
    actions: Mapped[List["CleaningAction"]] = relationship(
        "CleaningAction",
        back_populates="cleaning_run",
        cascade="all, delete-orphan",
    )


class CleaningAction(Base):
    __tablename__ = "cleaning_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cleaning_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cleaning_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    column_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decision: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending", index=True
    )
    before_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    after_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    evidence_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    cleaning_run: Mapped["CleaningRun"] = relationship(
        "CleaningRun", back_populates="actions"
    )


# ────────────────────────────────────────────────────────────
# ML RESULTS
# ────────────────────────────────────────────────────────────

class MLResult(Base):
    __tablename__ = "ml_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending", index=True
    )
    problem_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    target_column: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    selected_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    fallback_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    metrics_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    feature_importance: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    model_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    training_time_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rows_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="ml_result")


# ────────────────────────────────────────────────────────────
# INSIGHTS
# ────────────────────────────────────────────────────────────

class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    finding: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    interpretation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    importance_score: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=False,
        server_default=func.now(),
    )

    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="insights")


# ────────────────────────────────────────────────────────────
# VISUALIZATIONS
# ────────────────────────────────────────────────────────────

class Visualization(Base):
    __tablename__ = "visualizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    config_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    data_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    image_storage_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=False,
        server_default=func.now(),
    )

    analysis: Mapped["Analysis"] = relationship(
        "Analysis", back_populates="visualizations"
    )
    report_links: Mapped[List["ReportVisualization"]] = relationship(
        "ReportVisualization",
        back_populates="visualization",
        cascade="all, delete-orphan",
    )


# ────────────────────────────────────────────────────────────
# REPORTS
# ────────────────────────────────────────────────────────────

class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Owner so the report survives dataset/analysis deletion (Clean Datasets).
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # Nullable + SET NULL so deleting an analysis does not wipe the report.
    analysis_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analyses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        unique=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # Denormalized dataset label so the UI still shows a name after analysis is gone.
    dataset_label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Nullable so a report row can exist before the PDF is written.
    filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    storage_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending", index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=False,
        server_default=func.now(),
    )

    analysis: Mapped[Optional["Analysis"]] = relationship(
        "Analysis", back_populates="reports"
    )
    visualizations_links: Mapped[List["ReportVisualization"]] = relationship(
        "ReportVisualization",
        back_populates="report",
        cascade="all, delete-orphan",
    )


class ReportVisualization(Base):
    __tablename__ = "report_visualizations"

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        primary_key=True,
    )
    visualization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("visualizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    sort_order: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)

    report: Mapped["Report"] = relationship(
        "Report", back_populates="visualizations_links"
    )
    visualization: Mapped["Visualization"] = relationship(
        "Visualization", back_populates="report_links"
    )


# ────────────────────────────────────────────────────────────
# CHAT
# ────────────────────────────────────────────────────────────

class ChatConversation(Base):
    __tablename__ = "chat_conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # ON DELETE SET NULL — conversation survives dataset/analysis deletion.
    dataset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    analysis_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analyses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="chat_conversations")
    dataset: Mapped[Optional["Dataset"]] = relationship(
        "Dataset", back_populates="chat_conversations"
    )
    analysis: Mapped[Optional["Analysis"]] = relationship(
        "Analysis", back_populates="chat_conversations"
    )
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conversation: Mapped["ChatConversation"] = relationship(
        "ChatConversation", back_populates="messages"
    )


# ────────────────────────────────────────────────────────────
# Extra indexes (match schema + fingerprint unique)
# ────────────────────────────────────────────────────────────

Index("ix_dataset_user_created", Dataset.user_id, Dataset.created_at.desc())
# Unique only when fingerprint is present (Postgres treats NULLs as distinct).
Index(
    "uq_dataset_user_fingerprint",
    Dataset.user_id,
    Dataset.dataset_fingerprint,
    unique=True,
)
Index("ix_analyses_dataset_status", Analysis.dataset_id, Analysis.status)
Index(
    "ix_insights_analysis_importance",
    Insight.analysis_id,
    Insight.importance_score.desc(),
)
Index(
    "ix_visualizations_analysis_sort",
    Visualization.analysis_id,
    Visualization.sort_order,
)
Index(
    "ix_chat_message_conversation_created",
    ChatMessage.conversation_id,
    ChatMessage.created_at,
)


# ────────────────────────────────────────────────────────────
# FAVORITES  (user-saved datasets / reports)
# ────────────────────────────────────────────────────────────

class Favorite(Base):
    """Persisted user favorites for datasets and reports.

    Mirrors the frontend FavoriteItem shape (id, name, type, description)
    so the UI can sync across devices instead of relying only on localStorage.
    item_id is the dataset UUID or report UUID depending on item_type.
    """

    __tablename__ = "favorites"
    __table_args__ = (
        Index("ix_favorites_user_item", "user_id", "item_id", unique=True),
        Index("ix_favorites_user_type", "user_id", "item_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[str] = mapped_column(String(64), nullable=False)
    item_type: Mapped[str] = mapped_column(String(30), nullable=False)  # dataset | report
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Optional FKs when the item still exists in DB (SET NULL so history survives deletes)
    dataset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="SET NULL"),
        nullable=True,
    )
    report_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="favorites",
        foreign_keys=[user_id],
    )