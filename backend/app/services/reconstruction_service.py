from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditEventLog, ProjectSnapshot
from app.models.project import DocumentAsset, Project
from app.models.section import DocumentSection, FeedbackEvent, SectionComment, SectionRevision
from app.services.audit_service import AuditService


def _extract_text_word_count(content_json: dict | None) -> int:
    if not content_json:
        return 0
    words = 0

    def _walk(val) -> None:
        nonlocal words
        if isinstance(val, str):
            words += len(val.split())
        elif isinstance(val, list):
            for item in val:
                _walk(item)
        elif isinstance(val, dict):
            for v in val.values():
                _walk(v)

    _walk(content_json)
    return words


def compute_content_diff(before_json: dict | None, after_json: dict | None) -> dict:
    """Compute structured diff summary between two section content JSON payloads."""
    before = before_json or {}
    after = after_json or {}
    all_keys = sorted(set(before.keys()) | set(after.keys()))
    changed_fields = [k for k in all_keys if before.get(k) != after.get(k)]
    before_words = _extract_text_word_count(before)
    after_words = _extract_text_word_count(after)
    return {
        "changed_fields": changed_fields,
        "before_word_count": before_words,
        "after_word_count": after_words,
        "word_count_delta": after_words - before_words,
    }


def render_content_to_text(content_json: dict | None) -> str:
    """Convert structured section/slide JSON into readable plain/markdown summary."""
    if not content_json:
        return ""
    lines: list[str] = []
    if summary := content_json.get("summary_callout"):
        lines.append(f"> {summary}")
    if subtitle := content_json.get("subtitle"):
        lines.append(subtitle)
    for para in content_json.get("paragraphs", []):
        if isinstance(para, str) and para.strip():
            lines.append(para.strip())
    for bullet in content_json.get("bullet_points", []):
        if isinstance(bullet, dict):
            label = bullet.get("label", "").strip()
            detail = bullet.get("detail", "").strip()
            lines.append(f"- **{label}**: {detail}" if label else f"- {detail}")
        elif isinstance(bullet, str):
            lines.append(f"- {bullet}")
    for bullet in content_json.get("bullets", []):
        if isinstance(bullet, str):
            lines.append(f"- {bullet}")
        elif isinstance(bullet, dict):
            label = bullet.get("label", "").strip()
            detail = bullet.get("detail", "").strip()
            lines.append(f"- **{label}**: {detail}" if label else f"- {detail}")
    return "\n\n".join(lines)


class ReconstructionService:
    """Reconstructs historical project states and performs non-destructive rollbacks."""

    @staticmethod
    def build_snapshot_payload(db: Session, project: Project) -> dict:
        sections = list(
            db.scalars(
                select(DocumentSection)
                .where(DocumentSection.project_id == project.id, DocumentSection.is_deleted.is_(False))
                .order_by(DocumentSection.order_index)
            ).all()
        )
        section_entries = []
        for sec in sections:
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
            section_entries.append(
                {
                    "id": sec.id,
                    "order_index": sec.order_index,
                    "title": sec.title,
                    "section_kind": sec.section_kind,
                    "current_revision_id": sec.current_revision_id,
                    "current_content_json": sec.current_content_json,
                    "current_content_text": sec.current_content_text,
                    "like_status": sec.like_status,
                    "comments": [
                        {"id": c.id, "body": c.body, "created_at": c.created_at.isoformat()}
                        for c in comments
                    ],
                    "asset_ids": [a.id for a in assets],
                }
            )
        return {
            "project_id": project.id,
            "title": project.title,
            "doc_type": project.doc_type,
            "main_topic": project.main_topic,
            "status": project.status,
            "theme_config_json": project.theme_config_json,
            "version_number": project.current_version,
            "sections": section_entries,
        }

    @staticmethod
    def capture_snapshot(
        db: Session,
        project: Project,
        trigger_event_type: str,
        trigger_event_id: str | None = None,
    ) -> ProjectSnapshot:
        payload = ReconstructionService.build_snapshot_payload(db, project)
        snapshot = ProjectSnapshot(
            project_id=project.id,
            version_number=project.current_version,
            trigger_event_type=trigger_event_type,
            trigger_event_id=trigger_event_id,
            snapshot_json=payload,
            created_at=datetime.now(timezone.utc),
        )
        db.add(snapshot)
        db.flush()
        return snapshot

    @staticmethod
    def reconstruct_project(
        db: Session,
        project: Project,
        *,
        version: int | None = None,
        at_timestamp: datetime | None = None,
        event_seq_id: int | None = None,
    ) -> dict:
        if version is not None:
            snap = db.scalar(
                select(ProjectSnapshot)
                .where(
                    ProjectSnapshot.project_id == project.id,
                    ProjectSnapshot.version_number <= version,
                )
                .order_by(ProjectSnapshot.version_number.desc(), ProjectSnapshot.created_at.desc())
                .limit(1)
            )
            if snap and snap.version_number == version:
                reconstructed = snap.snapshot_json
                mode = f"snapshot_v{version}"
            else:
                reconstructed = ReconstructionService._replay_until(
                    db, project, max_version=version, max_ts=None
                )
                mode = f"replay_v{version}"
        elif event_seq_id is not None:
            ev = db.scalar(
                select(AuditEventLog).where(
                    AuditEventLog.project_id == project.id,
                    AuditEventLog.seq_id <= event_seq_id,
                ).order_by(AuditEventLog.seq_id.desc()).limit(1)
            )
            cutoff_ts = ev.created_at if ev else datetime.now(timezone.utc)
            reconstructed = ReconstructionService._replay_until(
                db, project, max_version=None, max_ts=cutoff_ts
            )
            mode = f"event_seq_{event_seq_id}"
        elif at_timestamp is not None:
            reconstructed = ReconstructionService._replay_until(
                db, project, max_version=None, max_ts=at_timestamp
            )
            mode = f"timestamp_{at_timestamp.isoformat()}"
        else:
            reconstructed = ReconstructionService.build_snapshot_payload(db, project)
            mode = f"live_v{project.current_version}"

        live_state = ReconstructionService.build_snapshot_payload(db, project)
        diffs = ReconstructionService._diff_project_states(reconstructed, live_state)

        return {
            "project_id": project.id,
            "reconstruction_mode": mode,
            "reconstructed_state": reconstructed,
            "diff_against_live": diffs,
        }

    @staticmethod
    def _replay_until(
        db: Session,
        project: Project,
        *,
        max_version: int | None,
        max_ts: datetime | None,
    ) -> dict:
        sections = list(
            db.scalars(
                select(DocumentSection)
                .where(DocumentSection.project_id == project.id)
                .order_by(DocumentSection.order_index)
            ).all()
        )

        def _norm_dt(dt: datetime) -> datetime:
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt

        cutoff_ts = _norm_dt(max_ts) if max_ts else None
        section_entries = []
        for sec in sections:
            if cutoff_ts and _norm_dt(sec.created_at) > cutoff_ts:
                continue

            rev_stmt = select(SectionRevision).where(SectionRevision.section_id == sec.id)
            if max_version is not None:
                rev_stmt = rev_stmt.where(SectionRevision.project_version <= max_version)
            if cutoff_ts is not None:
                rev_stmt = rev_stmt.where(SectionRevision.created_at <= cutoff_ts)
            latest_rev = db.scalar(
                rev_stmt.order_by(SectionRevision.revision_number.desc()).limit(1)
            )

            fb_stmt = select(FeedbackEvent).where(FeedbackEvent.section_id == sec.id)
            if cutoff_ts is not None:
                fb_stmt = fb_stmt.where(FeedbackEvent.created_at <= cutoff_ts)
            latest_fb = db.scalar(fb_stmt.order_by(FeedbackEvent.created_at.desc()).limit(1))

            comment_stmt = select(SectionComment).where(SectionComment.section_id == sec.id)
            if cutoff_ts is not None:
                comment_stmt = comment_stmt.where(SectionComment.created_at <= cutoff_ts)
            comments = [
                {"id": c.id, "body": c.body, "created_at": c.created_at.isoformat()}
                for c in db.scalars(comment_stmt.order_by(SectionComment.created_at)).all()
                if not c.deleted_at or (cutoff_ts and _norm_dt(c.deleted_at) > cutoff_ts)
            ]

            content_json = latest_rev.new_content_json if latest_rev else None
            section_entries.append(
                {
                    "id": sec.id,
                    "order_index": sec.order_index,
                    "title": sec.title,
                    "section_kind": sec.section_kind,
                    "current_revision_id": latest_rev.id if latest_rev else None,
                    "current_content_json": content_json,
                    "current_content_text": render_content_to_text(content_json),
                    "like_status": latest_fb.rating if latest_fb else "none",
                    "comments": comments,
                    "asset_ids": [],
                }
            )

        return {
            "project_id": project.id,
            "title": project.title,
            "doc_type": project.doc_type,
            "main_topic": project.main_topic,
            "status": project.status,
            "theme_config_json": project.theme_config_json,
            "version_number": max_version or project.current_version,
            "sections": section_entries,
        }

    @staticmethod
    def _diff_project_states(target: dict, live: dict) -> list[dict]:
        target_map = {s["id"]: s for s in target.get("sections", [])}
        live_map = {s["id"]: s for s in live.get("sections", [])}
        diffs: list[dict] = []
        for sec_id in sorted(set(target_map.keys()) | set(live_map.keys())):
            t_sec = target_map.get(sec_id)
            l_sec = live_map.get(sec_id)
            if not t_sec:
                diffs.append({"section_id": sec_id, "title": l_sec["title"], "change": "added_later"})
            elif not l_sec:
                diffs.append({"section_id": sec_id, "title": t_sec["title"], "change": "removed_later"})
            else:
                delta = compute_content_diff(
                    t_sec.get("current_content_json"),
                    l_sec.get("current_content_json"),
                )
                if (
                    delta["changed_fields"]
                    or t_sec.get("like_status") != l_sec.get("like_status")
                    or t_sec.get("title") != l_sec.get("title")
                ):
                    diffs.append(
                        {
                            "section_id": sec_id,
                            "title": l_sec["title"],
                            "change": "modified",
                            "content_diff": delta,
                            "like_changed": t_sec.get("like_status") != l_sec.get("like_status"),
                        }
                    )
        return diffs

    @staticmethod
    def restore_project_to_version(
        db: Session, project: Project, target_version: int, user_id: str
    ) -> dict:
        reconstructed = ReconstructionService.reconstruct_project(
            db, project, version=target_version
        )["reconstructed_state"]

        project.current_version += 1
        target_sections = {s["id"]: s for s in reconstructed.get("sections", [])}
        restored_count = 0

        for sec in db.scalars(
            select(DocumentSection).where(DocumentSection.project_id == project.id)
        ).all():
            target_sec = target_sections.get(sec.id)
            if not target_sec:
                continue
            target_content = target_sec.get("current_content_json")
            if target_content != sec.current_content_json and target_content is not None:
                latest_rev_num = (
                    db.scalar(
                        select(SectionRevision.revision_number)
                        .where(SectionRevision.section_id == sec.id)
                        .order_by(SectionRevision.revision_number.desc())
                        .limit(1)
                    )
                    or 0
                )
                new_rev = SectionRevision(
                    section_id=sec.id,
                    project_id=project.id,
                    revision_number=latest_rev_num + 1,
                    project_version=project.current_version,
                    source="restore",
                    refinement_prompt=f"Restored from project version v{target_version}",
                    previous_content_json=sec.current_content_json,
                    new_content_json=target_content,
                    diff_summary_json=compute_content_diff(
                        sec.current_content_json, target_content
                    ),
                    created_by=user_id,
                )
                db.add(new_rev)
                db.flush()
                sec.current_revision_id = new_rev.id
                sec.current_content_json = target_content
                sec.current_content_text = render_content_to_text(target_content)
                restored_count += 1

        event = AuditService.record_event(
            db,
            event_type="PROJECT_RESTORE",
            entity_type="project",
            entity_id=project.id,
            user_id=user_id,
            project_id=project.id,
            after_state={"restored_from_version": target_version, "new_version": project.current_version},
            metadata={"restored_sections": restored_count},
        )
        ReconstructionService.capture_snapshot(
            db, project, trigger_event_type="PROJECT_RESTORE", trigger_event_id=event.event_id
        )
        db.flush()
        return {
            "project_id": project.id,
            "restored_from_version": target_version,
            "new_version": project.current_version,
            "restored_sections": restored_count,
        }
