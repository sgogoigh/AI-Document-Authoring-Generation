from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.user import _utcnow, _uuid


class DocumentSection(Base):
    """Individual section (Word) or slide (PowerPoint) within a project."""

    __tablename__ = "document_sections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    section_kind: Mapped[str] = mapped_column(String(32), default="section", nullable=False)
    current_revision_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "section_revisions.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_section_current_revision",
        ),
        nullable=True,
    )
    current_content_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    current_content_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    like_status: Mapped[str] = mapped_column(String(16), default="none", nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    project = relationship("Project", back_populates="sections")
    revisions = relationship(
        "SectionRevision",
        back_populates="section",
        foreign_keys="SectionRevision.section_id",
        order_by="SectionRevision.revision_number",
        cascade="all, delete-orphan",
    )
    comments = relationship(
        "SectionComment",
        back_populates="section",
        order_by="SectionComment.created_at",
        cascade="all, delete-orphan",
    )
    feedback_events = relationship(
        "FeedbackEvent",
        back_populates="section",
        order_by="FeedbackEvent.created_at",
        cascade="all, delete-orphan",
    )


class SectionRevision(Base):
    """Immutable revision history for initial generation, AI refinements, and restores."""

    __tablename__ = "section_revisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    section_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("document_sections.id", ondelete="CASCADE"), index=True, nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    project_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    refinement_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_content_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_content_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    diff_summary_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    llm_metric_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("llm_call_metrics.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False
    )

    section = relationship("DocumentSection", back_populates="revisions", foreign_keys=[section_id])


class SectionComment(Base):
    """User comments attached to a section or slide."""

    __tablename__ = "section_comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    section_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("document_sections.id", ondelete="CASCADE"), index=True, nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    section = relationship("DocumentSection", back_populates="comments")


class FeedbackEvent(Base):
    """Immutable log of every Like/Dislike satisfaction toggle per section."""

    __tablename__ = "feedback_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    section_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("document_sections.id", ondelete="CASCADE"), index=True, nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    revision_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("section_revisions.id", ondelete="SET NULL"), nullable=True
    )
    rating: Mapped[str] = mapped_column(String(16), nullable=False)  # like | dislike | none
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False
    )

    section = relationship("DocumentSection", back_populates="feedback_events")
