from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.user import _utcnow, _uuid


class Project(Base):
    """Document generation project (either .docx report or .pptx presentation deck)."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(16), nullable=False)  # docx | pptx
    main_topic: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    theme_config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    ai_outline_suggested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner = relationship("User", back_populates="projects")
    sections = relationship(
        "DocumentSection",
        back_populates="project",
        order_by="DocumentSection.order_index",
        cascade="all, delete-orphan",
    )
    assets = relationship("DocumentAsset", back_populates="project", cascade="all, delete-orphan")
    exports = relationship("ExportRecord", back_populates="project", cascade="all, delete-orphan")
    snapshots = relationship("ProjectSnapshot", back_populates="project", cascade="all, delete-orphan")


class DocumentAsset(Base):
    """Generated visual assets (e.g., Gemini-generated images) attached to sections/projects."""

    __tablename__ = "document_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    section_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("document_sections.id", ondelete="SET NULL"), index=True, nullable=True
    )
    asset_type: Mapped[str] = mapped_column(String(32), default="generated_image", nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), default="image/png", nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    caption: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    width: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    height: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    llm_metric_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("llm_call_metrics.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    project = relationship("Project", back_populates="assets")


class ExportRecord(Base):
    """Audit record of each .docx or .pptx export assembled and downloaded."""

    __tablename__ = "export_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    doc_type: Mapped[str] = mapped_column(String(16), nullable=False)
    project_version: Mapped[int] = mapped_column(Integer, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    section_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    asset_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="success", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False
    )

    project = relationship("Project", back_populates="exports")
