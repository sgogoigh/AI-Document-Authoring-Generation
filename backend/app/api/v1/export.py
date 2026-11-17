import io
import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.project import DocumentAsset, ExportRecord
from app.models.section import DocumentSection
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.auth_service import get_current_user
from app.services.doc_builder import build_docx_bytes, build_pptx_bytes
from app.services.project_service import ProjectService

router = APIRouter(tags=["export & assets"])


class ExportRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    doc_type: str
    project_version: int
    file_name: str
    file_size_bytes: int
    section_count: int
    asset_count: int
    status: str
    created_at: datetime


def _safe_filename(title: str, doc_type: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", title.strip()).strip("_") or "document"
    return f"{slug[:80]}.{doc_type}"


@router.get("/projects/{project_id}/export")
def export_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch latest refined content and assemble a downloadable .docx or .pptx file."""
    settings = get_settings()
    project = ProjectService.get_owned_project(db, project_id, current_user.id)

    sections = list(
        db.scalars(
            select(DocumentSection)
            .where(DocumentSection.project_id == project.id, DocumentSection.is_deleted.is_(False))
            .order_by(DocumentSection.order_index)
        ).all()
    )
    if not sections:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has no sections or slides to export.",
        )

    storage_root = Path(settings.storage_dir)
    export_sections: list[dict] = []
    asset_count = 0

    for sec in sections:
        asset = db.scalar(
            select(DocumentAsset)
            .where(DocumentAsset.section_id == sec.id, DocumentAsset.is_active.is_(True))
            .order_by(DocumentAsset.created_at.desc())
            .limit(1)
        )
        image_path: Path | None = None
        image_caption = ""
        if asset:
            candidate = storage_root / asset.storage_path
            if candidate.exists():
                image_path = candidate
                image_caption = asset.caption
                asset_count += 1

        export_sections.append(
            {
                "id": sec.id,
                "title": sec.title,
                "content_json": sec.current_content_json,
                "content_text": sec.current_content_text,
                "image_path": image_path,
                "image_caption": image_caption,
            }
        )

    if project.doc_type == "pptx":
        content_bytes = build_pptx_bytes(
            title=project.title,
            main_topic=project.main_topic,
            author_name=current_user.full_name,
            theme_config=project.theme_config_json,
            version=project.current_version,
            sections=export_sections,
        )
        media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    else:
        content_bytes = build_docx_bytes(
            title=project.title,
            main_topic=project.main_topic,
            author_name=current_user.full_name,
            theme_config=project.theme_config_json,
            version=project.current_version,
            sections=export_sections,
        )
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    file_name = _safe_filename(project.title, project.doc_type)

    record = ExportRecord(
        project_id=project.id,
        user_id=current_user.id,
        doc_type=project.doc_type,
        project_version=project.current_version,
        file_name=file_name,
        file_size_bytes=len(content_bytes),
        section_count=len(export_sections),
        asset_count=asset_count,
        status="success",
    )
    db.add(record)
    db.flush()

    AuditService.record_event(
        db,
        event_type="DOC_EXPORT",
        entity_type="export",
        entity_id=record.id,
        user_id=current_user.id,
        project_id=project.id,
        after_state={
            "file_name": file_name,
            "file_size_bytes": len(content_bytes),
            "project_version": project.current_version,
            "section_count": len(export_sections),
            "asset_count": asset_count,
        },
    )
    db.commit()

    return StreamingResponse(
        io.BytesIO(content_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


@router.get("/projects/{project_id}/exports", response_model=list[ExportRecordResponse])
def list_project_exports(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List export history records for a project."""
    project = ProjectService.get_owned_project(db, project_id, current_user.id)
    records = list(
        db.scalars(
            select(ExportRecord)
            .where(ExportRecord.project_id == project.id)
            .order_by(ExportRecord.created_at.desc())
        ).all()
    )
    return [ExportRecordResponse.model_validate(r) for r in records]


@router.get("/assets/{asset_id}")
def get_asset_file(
    asset_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Serve an authenticated project's generated visual asset."""
    asset = db.get(DocumentAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    ProjectService.get_owned_project(db, asset.project_id, current_user.id)
    file_path = Path(get_settings().storage_dir) / asset.storage_path
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset file missing on disk.")
    return FileResponse(path=str(file_path), media_type=asset.mime_type)
