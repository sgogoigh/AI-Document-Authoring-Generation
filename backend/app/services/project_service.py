from collections import defaultdict
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.project import DocumentAsset, ExportRecord, Project
from app.models.section import DocumentSection, SectionComment, SectionRevision
from app.models.user import User
from app.schemas.project import (
    AssetResponse,
    CommentResponse,
    OutlineUpdateRequest,
    ProjectCreateRequest,
    ProjectDetailResponse,
    ProjectSummaryResponse,
    ProjectUpdateRequest,
    SectionDetailResponse,
)
from app.services.audit_service import AuditService
from app.services.reconstruction_service import ReconstructionService


class ProjectService:
    """CRUD and outline configuration service for Word & PowerPoint projects."""

    @staticmethod
    def get_owned_project(db: Session, project_id: str, user_id: str) -> Project:
        project = db.get(Project, project_id)
        if not project or project.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
        if project.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this project.",
            )
        return project

    @staticmethod
    def create_project(db: Session, user: User, payload: ProjectCreateRequest) -> ProjectDetailResponse:
        section_kind = "slide" if payload.doc_type == "pptx" else "section"
        initial_status = "configured" if payload.sections else "draft"

        project = Project(
            user_id=user.id,
            title=payload.title.strip(),
            doc_type=payload.doc_type,
            main_topic=payload.main_topic.strip(),
            status=initial_status,
            theme_config_json=payload.theme_config.model_dump(),
            ai_outline_suggested=payload.ai_outline_suggested,
            current_version=1,
        )
        db.add(project)
        db.flush()

        for idx, item in enumerate(payload.sections):
            db.add(
                DocumentSection(
                    project_id=project.id,
                    order_index=idx,
                    title=item.title.strip(),
                    section_kind=section_kind,
                )
            )
        db.flush()

        ev = AuditService.record_event(
            db,
            event_type="PROJECT_CREATE",
            entity_type="project",
            entity_id=project.id,
            user_id=user.id,
            project_id=project.id,
            after_state={
                "title": project.title,
                "doc_type": project.doc_type,
                "section_count": len(payload.sections),
                "ai_outline_suggested": project.ai_outline_suggested,
            },
        )
        ReconstructionService.capture_snapshot(
            db, project, trigger_event_type="PROJECT_CREATE", trigger_event_id=ev.event_id
        )
        db.commit()
        return ProjectService.build_project_detail(db, project)

    @staticmethod
    def list_projects(
        db: Session,
        user_id: str,
        *,
        doc_type: str | None = None,
        project_status: str | None = None,
        search: str | None = None,
    ) -> list[ProjectSummaryResponse]:
        stmt = select(Project).where(Project.user_id == user_id, Project.deleted_at.is_(None))
        if doc_type:
            stmt = stmt.where(Project.doc_type == doc_type)
        if project_status:
            stmt = stmt.where(Project.status == project_status)
        if search:
            pat = f"%{search.strip()}%"
            stmt = stmt.where((Project.title.ilike(pat)) | (Project.main_topic.ilike(pat)))

        projects = list(db.scalars(stmt.order_by(Project.updated_at.desc())).all())
        if not projects:
            return []

        project_ids = [p.id for p in projects]

        sec_rows = db.execute(
            select(
                DocumentSection.project_id,
                func.count(DocumentSection.id),
                func.sum(case((DocumentSection.like_status == "like", 1), else_=0)),
                func.sum(case((DocumentSection.like_status == "dislike", 1), else_=0)),
            )
            .where(
                DocumentSection.project_id.in_(project_ids),
                DocumentSection.is_deleted.is_(False),
            )
            .group_by(DocumentSection.project_id)
        ).all()
        sec_stats = {
            pid: (int(cnt or 0), int(likes or 0), int(dislikes or 0))
            for pid, cnt, likes, dislikes in sec_rows
        }

        exp_rows = db.execute(
            select(ExportRecord.project_id, func.count(ExportRecord.id))
            .where(ExportRecord.project_id.in_(project_ids))
            .group_by(ExportRecord.project_id)
        ).all()
        exp_counts = {pid: int(cnt or 0) for pid, cnt in exp_rows}

        summaries: list[ProjectSummaryResponse] = []
        for proj in projects:
            sec_cnt, like_cnt, dislike_cnt = sec_stats.get(proj.id, (0, 0, 0))
            summaries.append(
                ProjectSummaryResponse(
                    id=proj.id,
                    title=proj.title,
                    doc_type=proj.doc_type,
                    main_topic=proj.main_topic,
                    status=proj.status,
                    theme_config_json=proj.theme_config_json,
                    ai_outline_suggested=proj.ai_outline_suggested,
                    current_version=proj.current_version,
                    section_count=sec_cnt,
                    like_count=like_cnt,
                    dislike_count=dislike_cnt,
                    export_count=exp_counts.get(proj.id, 0),
                    created_at=proj.created_at,
                    updated_at=proj.updated_at,
                )
            )
        return summaries

    @staticmethod
    def build_project_detail(db: Session, project: Project) -> ProjectDetailResponse:
        sections = list(
            db.scalars(
                select(DocumentSection)
                .where(DocumentSection.project_id == project.id, DocumentSection.is_deleted.is_(False))
                .order_by(DocumentSection.order_index)
            ).all()
        )
        section_ids = [s.id for s in sections]

        comments_by_sec: dict[str, list[SectionComment]] = defaultdict(list)
        assets_by_sec: dict[str, list[DocumentAsset]] = defaultdict(list)
        rev_counts: dict[str, int] = {}

        if section_ids:
            for c in db.scalars(
                select(SectionComment)
                .where(
                    SectionComment.section_id.in_(section_ids),
                    SectionComment.deleted_at.is_(None),
                )
                .order_by(SectionComment.created_at)
            ).all():
                comments_by_sec[c.section_id].append(c)

            for a in db.scalars(
                select(DocumentAsset)
                .where(
                    DocumentAsset.section_id.in_(section_ids),
                    DocumentAsset.is_active.is_(True),
                )
                .order_by(DocumentAsset.created_at)
            ).all():
                if a.section_id:
                    assets_by_sec[a.section_id].append(a)

            for sid, cnt in db.execute(
                select(SectionRevision.section_id, func.count(SectionRevision.id))
                .where(SectionRevision.section_id.in_(section_ids))
                .group_by(SectionRevision.section_id)
            ).all():
                rev_counts[sid] = int(cnt or 0)

        section_responses: list[SectionDetailResponse] = []
        for sec in sections:
            section_responses.append(
                SectionDetailResponse(
                    id=sec.id,
                    project_id=sec.project_id,
                    order_index=sec.order_index,
                    title=sec.title,
                    section_kind=sec.section_kind,
                    current_revision_id=sec.current_revision_id,
                    current_content_json=sec.current_content_json,
                    current_content_text=sec.current_content_text,
                    like_status=sec.like_status,
                    revision_count=rev_counts.get(sec.id, 0),
                    comments=[CommentResponse.model_validate(c) for c in comments_by_sec.get(sec.id, [])],
                    assets=[AssetResponse.model_validate(a) for a in assets_by_sec.get(sec.id, [])],
                    created_at=sec.created_at,
                    updated_at=sec.updated_at,
                )
            )

        return ProjectDetailResponse(
            id=project.id,
            user_id=project.user_id,
            title=project.title,
            doc_type=project.doc_type,
            main_topic=project.main_topic,
            status=project.status,
            theme_config_json=project.theme_config_json,
            ai_outline_suggested=project.ai_outline_suggested,
            current_version=project.current_version,
            sections=section_responses,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    @staticmethod
    def update_project(
        db: Session, project_id: str, user_id: str, payload: ProjectUpdateRequest
    ) -> ProjectDetailResponse:
        project = ProjectService.get_owned_project(db, project_id, user_id)
        before_state = {
            "title": project.title,
            "main_topic": project.main_topic,
            "theme_config_json": project.theme_config_json,
        }

        if payload.title is not None:
            project.title = payload.title.strip()
        if payload.main_topic is not None:
            project.main_topic = payload.main_topic.strip()
        if payload.theme_config is not None:
            project.theme_config_json = payload.theme_config.model_dump()

        project.current_version += 1
        after_state = {
            "title": project.title,
            "main_topic": project.main_topic,
            "theme_config_json": project.theme_config_json,
        }

        ev = AuditService.record_event(
            db,
            event_type="PROJECT_UPDATE",
            entity_type="project",
            entity_id=project.id,
            user_id=user_id,
            project_id=project.id,
            before_state=before_state,
            after_state=after_state,
        )
        ReconstructionService.capture_snapshot(
            db, project, trigger_event_type="PROJECT_UPDATE", trigger_event_id=ev.event_id
        )
        db.commit()
        db.refresh(project)
        return ProjectService.build_project_detail(db, project)

    @staticmethod
    def delete_project(db: Session, project_id: str, user_id: str) -> None:
        project = ProjectService.get_owned_project(db, project_id, user_id)
        project.deleted_at = datetime.now(timezone.utc)
        AuditService.record_event(
            db,
            event_type="PROJECT_DELETE",
            entity_type="project",
            entity_id=project.id,
            user_id=user_id,
            project_id=project.id,
            before_state={"title": project.title, "status": project.status},
        )
        db.commit()

    @staticmethod
    def configure_outline(
        db: Session, project_id: str, user_id: str, payload: OutlineUpdateRequest
    ) -> ProjectDetailResponse:
        project = ProjectService.get_owned_project(db, project_id, user_id)
        section_kind = "slide" if project.doc_type == "pptx" else "section"

        existing_sections = list(
            db.scalars(
                select(DocumentSection)
                .where(DocumentSection.project_id == project.id, DocumentSection.is_deleted.is_(False))
                .order_by(DocumentSection.order_index)
            ).all()
        )
        before_outline = [
            {"id": s.id, "order_index": s.order_index, "title": s.title} for s in existing_sections
        ]
        existing_by_id = {s.id: s for s in existing_sections}
        kept_ids: set[str] = set()

        for idx, item in enumerate(payload.sections):
            clean_title = item.title.strip()
            if item.id and item.id in existing_by_id:
                sec = existing_by_id[item.id]
                sec.order_index = idx
                sec.title = clean_title
                kept_ids.add(sec.id)
            else:
                new_sec = DocumentSection(
                    project_id=project.id,
                    order_index=idx,
                    title=clean_title,
                    section_kind=section_kind,
                )
                db.add(new_sec)
                db.flush()
                kept_ids.add(new_sec.id)

        for sec in existing_sections:
            if sec.id not in kept_ids:
                sec.is_deleted = True

        if payload.ai_outline_suggested is not None:
            project.ai_outline_suggested = payload.ai_outline_suggested

        if project.status == "draft":
            project.status = "configured"
        project.current_version += 1
        db.flush()

        after_outline = [
            {"order_index": idx, "title": item.title.strip()}
            for idx, item in enumerate(payload.sections)
        ]
        ev = AuditService.record_event(
            db,
            event_type="OUTLINE_CONFIGURE",
            entity_type="project",
            entity_id=project.id,
            user_id=user_id,
            project_id=project.id,
            before_state={"outline": before_outline},
            after_state={"outline": after_outline},
        )
        ReconstructionService.capture_snapshot(
            db, project, trigger_event_type="OUTLINE_CONFIGURE", trigger_event_id=ev.event_id
        )
        db.commit()
        db.refresh(project)
        return ProjectService.build_project_detail(db, project)
