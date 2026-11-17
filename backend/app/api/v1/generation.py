from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.project import DocumentAsset, Project
from app.models.section import DocumentSection, FeedbackEvent, SectionComment, SectionRevision
from app.models.user import User
from app.schemas.generation import (
    CommentCreateRequest,
    FeedbackRequest,
    GenerateProjectRequest,
    RefineSectionRequest,
    RegenerateImageRequest,
    SectionRevisionResponse,
    SuggestOutlineRequest,
    SuggestOutlineResponse,
)
from app.schemas.project import AssetResponse, CommentResponse, ProjectDetailResponse, SectionDetailResponse
from app.services.audit_service import AuditService
from app.services.auth_service import get_current_user
from app.services.gemini_service import GeminiService
from app.services.project_service import ProjectService
from app.services.reconstruction_service import (
    ReconstructionService,
    compute_content_diff,
    render_content_to_text,
)

router = APIRouter(tags=["generation & refinement"])


def get_gemini_service() -> GeminiService:
    """Dependency provider for GeminiService (overridable in tests)."""
    return GeminiService()


def _get_owned_section(db: Session, section_id: str, user_id: str) -> tuple[DocumentSection, Project]:
    section = db.get(DocumentSection, section_id)
    if not section or section.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found.")
    project = ProjectService.get_owned_project(db, section.project_id, user_id)
    return section, project


def _build_section_detail(db: Session, sec: DocumentSection) -> SectionDetailResponse:
    comments = list(
        db.scalars(
            select(SectionComment)
            .where(SectionComment.section_id == sec.id, SectionComment.deleted_at.is_(None))
            .order_by(SectionComment.created_at)
        ).all()
    )
    assets = list(
        db.scalars(
            select(DocumentAsset)
            .where(DocumentAsset.section_id == sec.id, DocumentAsset.is_active.is_(True))
            .order_by(DocumentAsset.created_at)
        ).all()
    )
    revs = list(
        db.scalars(select(SectionRevision.id).where(SectionRevision.section_id == sec.id)).all()
    )
    return SectionDetailResponse(
        id=sec.id,
        project_id=sec.project_id,
        order_index=sec.order_index,
        title=sec.title,
        section_kind=sec.section_kind,
        current_revision_id=sec.current_revision_id,
        current_content_json=sec.current_content_json,
        current_content_text=sec.current_content_text,
        like_status=sec.like_status,
        revision_count=len(revs),
        comments=[CommentResponse.model_validate(c) for c in comments],
        assets=[AssetResponse.model_validate(a) for a in assets],
        created_at=sec.created_at,
        updated_at=sec.updated_at,
    )


@router.post("/projects/suggest-outline", response_model=SuggestOutlineResponse)
def suggest_outline(
    payload: SuggestOutlineRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    gemini: GeminiService = Depends(get_gemini_service),
):
    """Bonus feature: AI-Suggest Outline from a main topic."""
    if payload.project_id:
        ProjectService.get_owned_project(db, payload.project_id, current_user.id)

    suggestion, metric_id = gemini.suggest_outline(
        db,
        doc_type=payload.doc_type,
        main_topic=payload.main_topic,
        target_count=payload.target_count,
        user_id=current_user.id,
        project_id=payload.project_id,
    )
    AuditService.record_event(
        db,
        event_type="OUTLINE_SUGGEST",
        entity_type="project",
        entity_id=payload.project_id,
        user_id=current_user.id,
        project_id=payload.project_id,
        after_state={"recommended_title": suggestion.recommended_title, "items": suggestion.items},
        metadata={"doc_type": payload.doc_type, "llm_metric_id": metric_id},
    )
    db.commit()
    return SuggestOutlineResponse(
        recommended_title=suggestion.recommended_title,
        rationale=suggestion.rationale,
        items=suggestion.items,
    )


@router.post("/projects/{project_id}/generate", response_model=ProjectDetailResponse)
def generate_project_content(
    project_id: str,
    payload: GenerateProjectRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    gemini: GeminiService = Depends(get_gemini_service),
):
    """Generate context-aware content section-by-section (or slide-by-slide) using Gemini."""
    opts = payload or GenerateProjectRequest()
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
            detail="Configure at least one section or slide before generating content.",
        )

    project.status = "generating"
    project.current_version += 1
    db.flush()

    sibling_titles = [s.title for s in sections]
    include_images = bool((project.theme_config_json or {}).get("include_images", True))
    generated_count = 0

    for sec in sections:
        if opts.only_missing and sec.current_content_json is not None:
            continue

        content_json, metric_id = gemini.generate_section_content(
            db,
            project=project,
            section=sec,
            sibling_titles=sibling_titles,
            user_id=current_user.id,
        )

        latest_rev_num = (
            db.scalar(
                select(SectionRevision.revision_number)
                .where(SectionRevision.section_id == sec.id)
                .order_by(SectionRevision.revision_number.desc())
                .limit(1)
            )
            or 0
        )
        rev = SectionRevision(
            section_id=sec.id,
            project_id=project.id,
            revision_number=latest_rev_num + 1,
            project_version=project.current_version,
            source="initial_generation",
            previous_content_json=sec.current_content_json,
            new_content_json=content_json,
            diff_summary_json=compute_content_diff(sec.current_content_json, content_json),
            llm_metric_id=metric_id,
            created_by=current_user.id,
        )
        db.add(rev)
        db.flush()

        sec.current_revision_id = rev.id
        sec.current_content_json = content_json
        sec.current_content_text = render_content_to_text(content_json)
        generated_count += 1

        if opts.generate_images and include_images and content_json.get("should_generate_image"):
            img_prompt = content_json.get("image_prompt") or f"Editorial visual for {sec.title}"
            caption = content_json.get("image_caption") or sec.title
            # Deactivate old active assets when regenerating full project
            for old_asset in db.scalars(
                select(DocumentAsset).where(
                    DocumentAsset.section_id == sec.id, DocumentAsset.is_active.is_(True)
                )
            ).all():
                old_asset.is_active = False

            gemini.generate_section_image(
                db,
                image_prompt=img_prompt,
                caption=caption,
                project_id=project.id,
                section_id=sec.id,
                user_id=current_user.id,
            )

    project.status = "ready"
    ev = AuditService.record_event(
        db,
        event_type="CONTENT_GENERATE",
        entity_type="project",
        entity_id=project.id,
        user_id=current_user.id,
        project_id=project.id,
        after_state={"generated_sections": generated_count, "version": project.current_version},
    )
    ReconstructionService.capture_snapshot(
        db, project, trigger_event_type="CONTENT_GENERATE", trigger_event_id=ev.event_id
    )
    db.commit()
    db.refresh(project)
    return ProjectService.build_project_detail(db, project)


@router.post("/sections/{section_id}/refine", response_model=SectionDetailResponse)
def refine_section(
    section_id: str,
    payload: RefineSectionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    gemini: GeminiService = Depends(get_gemini_service),
):
    """Iteratively refine a single section or slide with a user prompt."""
    sec, project = _get_owned_section(db, section_id, current_user.id)
    if sec.current_content_json is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Generate initial content before refining this section.",
        )

    before_json = sec.current_content_json
    refined_json, metric_id = gemini.refine_section_content(
        db,
        project=project,
        section=sec,
        current_content_json=before_json,
        refinement_prompt=payload.refinement_prompt.strip(),
        user_id=current_user.id,
    )

    project.current_version += 1
    latest_rev_num = (
        db.scalar(
            select(SectionRevision.revision_number)
            .where(SectionRevision.section_id == sec.id)
            .order_by(SectionRevision.revision_number.desc())
            .limit(1)
        )
        or 0
    )
    rev = SectionRevision(
        section_id=sec.id,
        project_id=project.id,
        revision_number=latest_rev_num + 1,
        project_version=project.current_version,
        source="ai_refinement",
        refinement_prompt=payload.refinement_prompt.strip(),
        previous_content_json=before_json,
        new_content_json=refined_json,
        diff_summary_json=compute_content_diff(before_json, refined_json),
        llm_metric_id=metric_id,
        created_by=current_user.id,
    )
    db.add(rev)
    db.flush()

    sec.current_revision_id = rev.id
    sec.current_content_json = refined_json
    sec.current_content_text = render_content_to_text(refined_json)

    if payload.regenerate_image and refined_json.get("image_prompt"):
        for old_asset in db.scalars(
            select(DocumentAsset).where(
                DocumentAsset.section_id == sec.id, DocumentAsset.is_active.is_(True)
            )
        ).all():
            old_asset.is_active = False
        gemini.generate_section_image(
            db,
            image_prompt=refined_json["image_prompt"],
            caption=refined_json.get("image_caption") or sec.title,
            project_id=project.id,
            section_id=sec.id,
            user_id=current_user.id,
        )

    ev = AuditService.record_event(
        db,
        event_type="SECTION_REFINE",
        entity_type="section",
        entity_id=sec.id,
        user_id=current_user.id,
        project_id=project.id,
        section_id=sec.id,
        before_state={"revision_number": latest_rev_num, "content": before_json},
        after_state={"revision_number": rev.revision_number, "content": refined_json},
        metadata={"refinement_prompt": payload.refinement_prompt.strip()},
    )
    ReconstructionService.capture_snapshot(
        db, project, trigger_event_type="SECTION_REFINE", trigger_event_id=ev.event_id
    )
    db.commit()
    db.refresh(sec)
    return _build_section_detail(db, sec)


@router.post("/sections/{section_id}/regenerate-image", response_model=SectionDetailResponse)
def regenerate_section_image(
    section_id: str,
    payload: RegenerateImageRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    gemini: GeminiService = Depends(get_gemini_service),
):
    """Generate or regenerate a bespoke Gemini image for a specific section/slide."""
    opts = payload or RegenerateImageRequest()
    sec, project = _get_owned_section(db, section_id, current_user.id)
    content = sec.current_content_json or {}
    prompt = (
        (opts.image_prompt or "").strip()
        or content.get("image_prompt")
        or f"Editorial business visual representing {sec.title} in the context of {project.main_topic}"
    )
    caption = (opts.caption or "").strip() or content.get("image_caption") or sec.title

    for old_asset in db.scalars(
        select(DocumentAsset).where(
            DocumentAsset.section_id == sec.id, DocumentAsset.is_active.is_(True)
        )
    ).all():
        old_asset.is_active = False

    asset = gemini.generate_section_image(
        db,
        image_prompt=prompt,
        caption=caption,
        project_id=project.id,
        section_id=sec.id,
        user_id=current_user.id,
    )
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Image generation did not produce an asset.",
        )

    AuditService.record_event(
        db,
        event_type="IMAGE_GENERATE",
        entity_type="asset",
        entity_id=asset.id,
        user_id=current_user.id,
        project_id=project.id,
        section_id=sec.id,
        after_state={"asset_id": asset.id, "width": asset.width, "height": asset.height},
    )
    db.commit()
    db.refresh(sec)
    return _build_section_detail(db, sec)


@router.post("/sections/{section_id}/feedback", response_model=SectionDetailResponse)
def set_section_feedback(
    section_id: str,
    payload: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record Like / Dislike / None feedback for a section or slide."""
    sec, project = _get_owned_section(db, section_id, current_user.id)
    previous_rating = sec.like_status
    sec.like_status = payload.rating

    fb = FeedbackEvent(
        section_id=sec.id,
        project_id=project.id,
        user_id=current_user.id,
        revision_id=sec.current_revision_id,
        rating=payload.rating,
        note=payload.note,
    )
    db.add(fb)
    db.flush()

    AuditService.record_event(
        db,
        event_type="FEEDBACK_RECORD",
        entity_type="section",
        entity_id=sec.id,
        user_id=current_user.id,
        project_id=project.id,
        section_id=sec.id,
        before_state={"like_status": previous_rating},
        after_state={"like_status": payload.rating},
    )
    db.commit()
    db.refresh(sec)
    return _build_section_detail(db, sec)


@router.get("/sections/{section_id}/comments", response_model=list[CommentResponse])
def list_section_comments(
    section_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sec, _ = _get_owned_section(db, section_id, current_user.id)
    comments = list(
        db.scalars(
            select(SectionComment)
            .where(SectionComment.section_id == sec.id, SectionComment.deleted_at.is_(None))
            .order_by(SectionComment.created_at)
        ).all()
    )
    return [CommentResponse.model_validate(c) for c in comments]


@router.post("/sections/{section_id}/comments", response_model=CommentResponse, status_code=201)
def add_section_comment(
    section_id: str,
    payload: CommentCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sec, project = _get_owned_section(db, section_id, current_user.id)
    comment = SectionComment(
        section_id=sec.id,
        project_id=project.id,
        user_id=current_user.id,
        body=payload.body.strip(),
    )
    db.add(comment)
    db.flush()

    AuditService.record_event(
        db,
        event_type="COMMENT_CREATE",
        entity_type="comment",
        entity_id=comment.id,
        user_id=current_user.id,
        project_id=project.id,
        section_id=sec.id,
        after_state={"body": comment.body},
    )
    db.commit()
    db.refresh(comment)
    return CommentResponse.model_validate(comment)


@router.delete("/comments/{comment_id}", status_code=204)
def delete_comment(
    comment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comment = db.get(SectionComment, comment_id)
    if not comment or comment.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found.")
    ProjectService.get_owned_project(db, comment.project_id, current_user.id)
    comment.deleted_at = datetime.now(timezone.utc)
    AuditService.record_event(
        db,
        event_type="COMMENT_DELETE",
        entity_type="comment",
        entity_id=comment.id,
        user_id=current_user.id,
        project_id=comment.project_id,
        section_id=comment.section_id,
    )
    db.commit()


@router.get("/sections/{section_id}/revisions", response_model=list[SectionRevisionResponse])
def list_section_revisions(
    section_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sec, _ = _get_owned_section(db, section_id, current_user.id)
    revs = list(
        db.scalars(
            select(SectionRevision)
            .where(SectionRevision.section_id == sec.id)
            .order_by(SectionRevision.revision_number.desc())
        ).all()
    )
    return [SectionRevisionResponse.model_validate(r) for r in revs]
