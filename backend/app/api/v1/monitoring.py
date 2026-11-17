from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.audit import AuditEventLog, ProjectSnapshot
from app.models.user import User
from app.schemas.monitoring import (
    AuditLogItemResponse,
    LLMMetricItemResponse,
    MonitoringMetricsResponse,
    PaginatedAuditLogsResponse,
    ProjectTimelineResponse,
    ReconstructionResponse,
    RestoreVersionResponse,
    SnapshotSummaryResponse,
)
from app.services.audit_service import AuditService
from app.services.auth_service import get_current_user
from app.services.project_service import ProjectService
from app.services.reconstruction_service import ReconstructionService

router = APIRouter(tags=["monitoring & reconstruction"])


@router.get("/monitoring/logs", response_model=PaginatedAuditLogsResponse)
def get_audit_logs(
    project_id: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    trace_id: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Filterable audit event stream scoped to the authenticated user."""
    if project_id:
        ProjectService.get_owned_project(db, project_id, current_user.id)

    items, total = AuditService.query_logs(
        db,
        user_id=current_user.id,
        project_id=project_id,
        event_type=event_type,
        severity=severity,
        trace_id=trace_id,
        entity_type=entity_type,
        date_from=date_from,
        date_to=date_to,
        search=search,
        limit=limit,
        offset=offset,
    )
    return PaginatedAuditLogsResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[AuditLogItemResponse.model_validate(item) for item in items],
    )


@router.get("/monitoring/metrics", response_model=MonitoringMetricsResponse)
def get_monitoring_metrics(
    project_id: str | None = Query(default=None),
    operation: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aggregated LLM latency/token/error analytics + satisfaction metrics + recent calls."""
    if project_id:
        ProjectService.get_owned_project(db, project_id, current_user.id)

    analytics = AuditService.compute_analytics(
        db, user_id=current_user.id, project_id=project_id
    )
    llm_items, total_llm = AuditService.query_llm_metrics(
        db,
        user_id=current_user.id,
        project_id=project_id,
        operation=operation,
        status=status,
        limit=limit,
    )
    return MonitoringMetricsResponse(
        analytics=analytics,
        recent_llm_calls=[LLMMetricItemResponse.model_validate(m) for m in llm_items],
        total_llm_records=total_llm,
    )


@router.get("/projects/{project_id}/timeline", response_model=ProjectTimelineResponse)
def get_project_timeline(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return chronological snapshots and audit events for a specific project."""
    project = ProjectService.get_owned_project(db, project_id, current_user.id)
    snapshots = list(
        db.scalars(
            select(ProjectSnapshot)
            .where(ProjectSnapshot.project_id == project.id)
            .order_by(ProjectSnapshot.version_number.desc(), ProjectSnapshot.created_at.desc())
        ).all()
    )
    events = list(
        db.scalars(
            select(AuditEventLog)
            .where(AuditEventLog.project_id == project.id)
            .order_by(AuditEventLog.seq_id.desc())
            .limit(200)
        ).all()
    )
    return ProjectTimelineResponse(
        project_id=project.id,
        current_version=project.current_version,
        snapshots=[SnapshotSummaryResponse.model_validate(s) for s in snapshots],
        events=[AuditLogItemResponse.model_validate(e) for e in events],
    )


@router.get("/projects/{project_id}/reconstruct", response_model=ReconstructionResponse)
def reconstruct_project_state(
    project_id: str,
    version: int | None = Query(default=None, ge=1),
    at_timestamp: datetime | None = Query(default=None),
    event_seq_id: int | None = Query(default=None, ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reconstruct historical project state by version, timestamp, or audit seq_id with diffs."""
    project = ProjectService.get_owned_project(db, project_id, current_user.id)
    result = ReconstructionService.reconstruct_project(
        db,
        project,
        version=version,
        at_timestamp=at_timestamp,
        event_seq_id=event_seq_id,
    )
    return ReconstructionResponse(**result)


@router.post("/projects/{project_id}/restore/{version}", response_model=RestoreVersionResponse)
def restore_project_version(
    project_id: str,
    version: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Non-destructively restore project content to a prior historical version."""
    project = ProjectService.get_owned_project(db, project_id, current_user.id)
    result = ReconstructionService.restore_project_to_version(
        db, project, version, current_user.id
    )
    db.commit()
    return RestoreVersionResponse(**result)
