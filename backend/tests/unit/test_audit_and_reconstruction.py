from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.models import (
    DocumentSection,
    FeedbackEvent,
    Project,
    SectionComment,
    SectionRevision,
    User,
)
from app.services.audit_service import AuditService
from app.services.reconstruction_service import (
    ReconstructionService,
    compute_content_diff,
    render_content_to_text,
)


def test_trace_id_middleware_headers(client: TestClient):
    res = client.get("/api/v1/health", headers={"X-Trace-Id": "custom-trace-123"})
    assert res.status_code == 200
    assert res.headers["X-Trace-Id"] == "custom-trace-123"
    assert float(res.headers["X-Response-Time-Ms"]) >= 0.0


def test_audit_logging_filtering_and_analytics(db_session):
    user = User(email="obs@example.com", full_name="Obs User", password_hash="x", auth_provider="local")
    db_session.add(user)
    db_session.flush()

    proj = Project(
        user_id=user.id,
        title="Observability Deck",
        doc_type="pptx",
        main_topic="AI Governance",
        status="ready",
    )
    db_session.add(proj)
    db_session.flush()

    sec1 = DocumentSection(
        project_id=proj.id, order_index=0, title="Slide 1", section_kind="slide", like_status="like"
    )
    sec2 = DocumentSection(
        project_id=proj.id, order_index=1, title="Slide 2", section_kind="slide", like_status="dislike"
    )
    db_session.add_all([sec1, sec2])
    db_session.flush()

    AuditService.record_event(
        db_session,
        event_type="PROJECT_CREATE",
        entity_type="project",
        entity_id=proj.id,
        user_id=user.id,
        project_id=proj.id,
        trace_id="tr-a",
        after_state={"title": proj.title},
    )
    AuditService.record_event(
        db_session,
        event_type="SECTION_REFINE",
        entity_type="section",
        entity_id=sec1.id,
        user_id=user.id,
        project_id=proj.id,
        section_id=sec1.id,
        severity="WARN",
        trace_id="tr-b",
        endpoint="/api/v1/sections/refine",
    )

    AuditService.record_llm_metric(
        db_session,
        operation="section_generate",
        model_name="gemini-2.5-flash",
        user_id=user.id,
        project_id=proj.id,
        section_id=sec1.id,
        input_tokens=100,
        output_tokens=200,
        latency_ms=420.0,
        status="success",
        trace_id="tr-a",
    )
    AuditService.record_llm_metric(
        db_session,
        operation="section_refine",
        model_name="gemini-2.5-flash",
        user_id=user.id,
        project_id=proj.id,
        section_id=sec1.id,
        input_tokens=150,
        output_tokens=120,
        latency_ms=980.0,
        status="error",
        error_message="Rate limit",
        trace_id="tr-b",
    )
    db_session.commit()

    logs_proj, total_proj = AuditService.query_logs(db_session, project_id=proj.id)
    assert total_proj == 2
    assert len(logs_proj) == 2

    logs_warn, total_warn = AuditService.query_logs(db_session, severity="WARN", search="refine")
    assert total_warn == 1
    assert logs_warn[0].trace_id == "tr-b"

    logs_trace, _ = AuditService.query_logs(db_session, trace_id="tr-a")
    assert len(logs_trace) == 1
    assert logs_trace[0].event_type == "PROJECT_CREATE"

    analytics = AuditService.compute_analytics(db_session, user_id=user.id)
    assert analytics["llm"]["total_calls"] == 2
    assert analytics["llm"]["successful_calls"] == 1
    assert analytics["llm"]["failed_calls"] == 1
    assert analytics["llm"]["error_rate"] == 50.0
    assert analytics["llm"]["total_tokens"] == 570
    assert analytics["llm"]["p50_latency_ms"] == 420.0
    assert analytics["llm"]["p95_latency_ms"] == 980.0
    assert analytics["feedback"]["like_count"] == 1
    assert analytics["feedback"]["dislike_count"] == 1
    assert analytics["feedback"]["satisfaction_rate_pct"] == 50.0
    assert analytics["audit"]["total_events"] == 2


def test_point_in_time_reconstruction_and_non_destructive_restore(db_session):
    user = User(email="rec@example.com", full_name="Rec User", password_hash="x", auth_provider="local")
    db_session.add(user)
    db_session.flush()

    proj = Project(
        user_id=user.id,
        title="EV Market Report",
        doc_type="docx",
        main_topic="EV 2025",
        status="ready",
        current_version=1,
    )
    db_session.add(proj)
    db_session.flush()

    t0 = datetime.now(timezone.utc) - timedelta(minutes=10)
    t1 = datetime.now(timezone.utc) - timedelta(minutes=5)

    sec = DocumentSection(
        project_id=proj.id,
        order_index=0,
        title="Market Overview",
        section_kind="section",
        created_at=t0,
    )
    db_session.add(sec)
    db_session.flush()

    v1_content = {"summary_callout": "Initial summary", "paragraphs": ["First draft text here."]}
    rev1 = SectionRevision(
        section_id=sec.id,
        project_id=proj.id,
        revision_number=1,
        project_version=1,
        source="initial_generation",
        new_content_json=v1_content,
        created_by=user.id,
        created_at=t0,
    )
    db_session.add(rev1)
    db_session.flush()

    sec.current_revision_id = rev1.id
    sec.current_content_json = v1_content
    sec.current_content_text = render_content_to_text(v1_content)

    ev1 = AuditService.record_event(
        db_session,
        event_type="CONTENT_GENERATE",
        entity_type="project",
        entity_id=proj.id,
        user_id=user.id,
        project_id=proj.id,
    )
    ReconstructionService.capture_snapshot(db_session, proj, "CONTENT_GENERATE", ev1.event_id)

    # Version 2: refinement + like + comment
    proj.current_version = 2
    v2_content = {"summary_callout": "Refined executive summary", "paragraphs": ["Concise formal text."]}
    rev2 = SectionRevision(
        section_id=sec.id,
        project_id=proj.id,
        revision_number=2,
        project_version=2,
        source="ai_refinement",
        refinement_prompt="Make this more formal",
        previous_content_json=v1_content,
        new_content_json=v2_content,
        diff_summary_json=compute_content_diff(v1_content, v2_content),
        created_by=user.id,
        created_at=t1,
    )
    db_session.add(rev2)
    db_session.flush()
    sec.current_revision_id = rev2.id
    sec.current_content_json = v2_content
    sec.current_content_text = render_content_to_text(v2_content)
    sec.like_status = "like"

    db_session.add(
        FeedbackEvent(
            section_id=sec.id,
            project_id=proj.id,
            user_id=user.id,
            revision_id=rev2.id,
            rating="like",
            created_at=t1,
        )
    )
    db_session.add(
        SectionComment(
            section_id=sec.id,
            project_id=proj.id,
            user_id=user.id,
            body="Approved by VP",
            created_at=t1,
        )
    )
    ev2 = AuditService.record_event(
        db_session,
        event_type="SECTION_REFINE",
        entity_type="section",
        entity_id=sec.id,
        user_id=user.id,
        project_id=proj.id,
        section_id=sec.id,
    )
    ReconstructionService.capture_snapshot(db_session, proj, "SECTION_REFINE", ev2.event_id)
    db_session.commit()

    # Reconstruct v1 and compare against live v2
    rec_v1 = ReconstructionService.reconstruct_project(db_session, proj, version=1)
    assert rec_v1["reconstruction_mode"] == "snapshot_v1"
    assert rec_v1["reconstructed_state"]["sections"][0]["current_content_json"] == v1_content
    assert len(rec_v1["diff_against_live"]) == 1
    assert rec_v1["diff_against_live"][0]["change"] == "modified"

    # Reconstruct by timestamp between t0 and t1
    rec_ts = ReconstructionService.reconstruct_project(
        db_session, proj, at_timestamp=t0 + timedelta(minutes=1)
    )
    assert rec_ts["reconstructed_state"]["sections"][0]["current_content_json"] == v1_content
    assert rec_ts["reconstructed_state"]["sections"][0]["like_status"] == "none"
    assert rec_ts["reconstructed_state"]["sections"][0]["comments"] == []

    # Restore to v1 non-destructively -> becomes v3 with revision_number=3
    restore_res = ReconstructionService.restore_project_to_version(db_session, proj, 1, user.id)
    db_session.commit()

    assert restore_res["new_version"] == 3
    assert restore_res["restored_sections"] == 1
    db_session.refresh(sec)
    assert sec.current_content_json == v1_content
    assert len(sec.revisions) == 3
    assert sec.revisions[-1].source == "restore"
