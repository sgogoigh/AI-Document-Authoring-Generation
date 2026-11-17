from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.user import _utcnow, _uuid


class AuditEventLog(Base):
    """Append-only structured audit event log for filtering, analytics, and replay."""

    __tablename__ = "audit_event_logs"
    __table_args__ = (
        Index("ix_audit_project_created", "project_id", "created_at"),
        Index("ix_audit_user_created", "user_id", "created_at"),
        Index("ix_audit_event_created", "event_type", "created_at"),
    )

    seq_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(36), unique=True, default=_uuid, nullable=False)
    trace_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="SET NULL"), index=True, nullable=True
    )
    section_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("document_sections.id", ondelete="SET NULL"), index=True, nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="INFO", index=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    http_method: Mapped[str | None] = mapped_column(String(16), nullable=True)
    endpoint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    before_state_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_state_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False
    )


class ProjectSnapshot(Base):
    """Materialized version checkpoint enabling O(1) + delta state reconstruction."""

    __tablename__ = "project_snapshots"
    __table_args__ = (Index("ix_snapshot_project_version", "project_id", "version_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    trigger_event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    trigger_event_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False
    )

    project = relationship("Project", back_populates="snapshots")
