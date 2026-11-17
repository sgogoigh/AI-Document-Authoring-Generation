from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.schemas.project import (
    OutlineUpdateRequest,
    ProjectCreateRequest,
    ProjectDetailResponse,
    ProjectSummaryResponse,
    ProjectUpdateRequest,
)
from app.services.auth_service import get_current_user
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectDetailResponse, status_code=201)
def create_project(
    payload: ProjectCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new .docx or .pptx document project with optional initial outline."""
    return ProjectService.create_project(db, current_user, payload)


@router.get("", response_model=list[ProjectSummaryResponse])
def list_projects(
    doc_type: str | None = Query(default=None, pattern="^(docx|pptx)$"),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all active projects belonging to the authenticated user."""
    return ProjectService.list_projects(
        db, current_user.id, doc_type=doc_type, project_status=status, search=search
    )


@router.get("/{project_id}", response_model=ProjectDetailResponse)
def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch full project configuration, sections, latest content, comments, and assets."""
    project = ProjectService.get_owned_project(db, project_id, current_user.id)
    return ProjectService.build_project_detail(db, project)


@router.patch("/{project_id}", response_model=ProjectDetailResponse)
def update_project(
    project_id: str,
    payload: ProjectUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update project title, main topic, or theme configuration."""
    return ProjectService.update_project(db, project_id, current_user.id, payload)


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft-delete a project owned by the authenticated user."""
    ProjectService.delete_project(db, project_id, current_user.id)


@router.put("/{project_id}/outline", response_model=ProjectDetailResponse)
def update_project_outline(
    project_id: str,
    payload: OutlineUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add, remove, rename, or reorder Word section headers or PowerPoint slide titles."""
    return ProjectService.configure_outline(db, project_id, current_user.id, payload)
