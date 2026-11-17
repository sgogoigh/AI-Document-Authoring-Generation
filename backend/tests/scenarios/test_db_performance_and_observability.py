import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import event

from app.models import (
    AuditEventLog,
    DocumentAsset,
    DocumentSection,
    ExportRecord,
    LLMCallMetric,
    Project,
    ProjectSnapshot,
    SectionComment,
    SectionRevision,
    User,
)
from app.services.audit_service import AuditService
from app.services.project_service import ProjectService
from app.services.reconstruction_service import ReconstructionService


def _count_queries(engine, fn):
    count = 0

    def _listener(_conn, _cursor, _statement, _parameters, _context, _executemany):
        nonlocal count
        count += 1

    event.listen(engine, "before_cursor_execute", _listener)
    t0 = time.perf_counter()
    try:
        result = fn()
    finally:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        event.remove(engine, "before_cursor_execute", _listener)
    return result, count, round(elapsed_ms, 2)


def _seed_heavy_workspace(db_session, *, num_projects=25, sections_per_proj=6, events_per_proj=20):
    user = User(email="perf@example.com", full_name="Perf User", password_hash="x", auth_provider="local")
    db_session.add(user)
    db_session.flush()

    base_ts = datetime.now(timezone.utc) - timedelta(hours=2)
    project_ids: list[str] = []
    first_project = None

    for p_i in range(num_projects):
        proj = Project(
            user_id=user.id,
            title=f"Benchmark Document {p_i + 1:02d}",
            doc_type="docx" if p_i % 2 == 0 else "pptx",
            main_topic=f"Enterprise topic analysis batch {p_i + 1}",
            status="ready",
            current_version=3,
        )
        db_session.add(proj)
        db_session.flush()
        project_ids.append(proj.id)
        if first_project is None:
            first_project = proj

        for s_i in range(sections_per_proj):
            sec = DocumentSection(
                project_id=proj.id,
                order_index=s_i,
                title=f"Section {s_i + 1}",
                section_kind="section" if proj.doc_type == "docx" else "slide",
                current_content_json={"summary_callout": f"Callout {s_i}", "paragraphs": ["Text."]},
                current_content_text=f"Summary text for {p_i}-{s_i}",
                like_status="like" if s_i % 3 == 0 else ("dislike" if s_i % 3 == 1 else "none"),
            )
            db_session.add(sec)
            db_session.flush()

            for r_i in range(1, 3):
                rev = SectionRevision(
                    section_id=sec.id,
                    project_id=proj.id,
                    revision_number=r_i,
                    project_version=r_i + 1,
                    source="initial_generation" if r_i == 1 else "ai_refinement",
                    new_content_json={"summary_callout": f"Rev {r_i}", "paragraphs": ["Text."]},
                    created_by=user.id,
                )
                db_session.add(rev)
                db_session.flush()
                sec.current_revision_id = rev.id

            db_session.add(
                SectionComment(
                    section_id=sec.id, project_id=proj.id, user_id=user.id, body=f"Note {s_i}"
                )
            )
            db_session.add(
                DocumentAsset(
                    project_id=proj.id,
                    section_id=sec.id,
                    prompt="Diagram",
                    storage_path=f"assets/p{p_i}_s{s_i}.png",
                    width=512,
                    height=512,
                )
            )

        db_session.add(
            ExportRecord(
                project_id=proj.id,
                user_id=user.id,
                doc_type=proj.doc_type,
                project_version=3,
                file_name=f"doc_{p_i}.{proj.doc_type}",
                file_size_bytes=25000,
                section_count=sections_per_proj,
                asset_count=sections_per_proj,
            )
        )

        for e_i in range(events_per_proj):
            ev_ts = base_ts + timedelta(seconds=p_i * 30 + e_i)
            op = ["section_generate", "section_refine", "outline_suggest", "image_generate"][e_i % 4]
            status = "error" if e_i == 19 else "success"
            db_session.add(
                LLMCallMetric(
                    trace_id=f"tr-{p_i}-{e_i // 4}",
                    user_id=user.id,
                    project_id=proj.id,
                    operation=op,
                    model_name="gemini-2.5-flash",
                    input_tokens=150,
                    output_tokens=250,
                    total_tokens=400,
                    latency_ms=200.0 + (e_i * 35.0),
                    status=status,
                    created_at=ev_ts,
                )
            )
            db_session.add(
                AuditEventLog(
                    event_id=str(uuid.uuid4()),
                    trace_id=f"tr-{p_i}-{e_i // 4}",
                    user_id=user.id,
                    project_id=proj.id,
                    event_type="SECTION_REFINE" if e_i % 2 == 0 else "CONTENT_GENERATE",
                    severity="ERROR" if status == "error" else "INFO",
                    entity_type="section" if e_i % 2 == 0 else "project",
                    before_state_json={"version": 1, "blob": "x" * 200},
                    after_state_json={"version": 2, "blob": "y" * 200},
                    metadata_json={"idx": e_i},
                    created_at=ev_ts,
                )
            )

        db_session.add(
            ProjectSnapshot(
                project_id=proj.id,
                version_number=1,
                trigger_event_type="PROJECT_CREATE",
                snapshot_json={"title": proj.title, "sections": []},
            )
        )

    db_session.commit()
    return user, first_project, project_ids


def test_perf_list_projects_query_count_and_latency(db_session):
    user, _, _ = _seed_heavy_workspace(db_session, num_projects=25, sections_per_proj=6, events_per_proj=10)
    engine = db_session.get_bind()

    summaries, q_count, ms = _count_queries(
        engine, lambda: ProjectService.list_projects(db_session, user.id)
    )
    print(f"\n[PERF list_projects] projects=25 queries={q_count} latency_ms={ms}")
    assert len(summaries) == 25
    assert summaries[0].section_count == 6
    assert summaries[0].export_count == 1
    assert q_count <= 4
    assert ms < 200.0


def test_perf_build_project_detail_query_count_and_latency(db_session):
    user, _, _ = _seed_heavy_workspace(db_session, num_projects=1, sections_per_proj=12, events_per_proj=12)
    proj = db_session.query(Project).filter(Project.user_id == user.id).first()
    engine = db_session.get_bind()

    detail, q_count, ms = _count_queries(
        engine, lambda: ProjectService.build_project_detail(db_session, proj)
    )
    print(f"\n[PERF build_project_detail] sections=12 queries={q_count} latency_ms={ms}")
    assert len(detail.sections) == 12
    assert all(s.revision_count == 2 for s in detail.sections)
    assert all(len(s.comments) == 1 for s in detail.sections)
    assert all(len(s.assets) == 1 for s in detail.sections)
    assert q_count <= 5
    assert ms < 150.0


def test_perf_compute_analytics_sql_aggregation(db_session):
    user, _, _ = _seed_heavy_workspace(db_session, num_projects=25, sections_per_proj=6, events_per_proj=20)
    engine = db_session.get_bind()

    analytics, q_count, ms = _count_queries(
        engine, lambda: AuditService.compute_analytics(db_session, user_id=user.id)
    )
    print(f"\n[PERF compute_analytics] llm_rows=500 audit_rows=500 queries={q_count} latency_ms={ms}")
    assert analytics["llm"]["total_calls"] == 500
    assert analytics["llm"]["failed_calls"] == 25
    assert analytics["llm"]["total_tokens"] == 500 * 400
    assert analytics["audit"]["total_events"] == 500
    assert analytics["exports"]["total_exports"] == 25
    assert analytics["feedback"]["like_count"] == 50
    assert analytics["feedback"]["dislike_count"] == 50
    assert q_count <= 8
    assert ms < 200.0


def test_perf_audit_log_multi_facet_filtering_and_trace_lookup(db_session):
    user, first_proj, _ = _seed_heavy_workspace(
        db_session, num_projects=25, sections_per_proj=4, events_per_proj=20
    )
    engine = db_session.get_bind()

    def _run_filters():
        items_sev, tot_sev = AuditService.query_logs(
            db_session, user_id=user.id, severity="ERROR", limit=50
        )
        items_tr, tot_tr = AuditService.query_logs(
            db_session, user_id=user.id, trace_id="tr-0-1"
        )
        items_proj, tot_proj = AuditService.query_logs(
            db_session, user_id=user.id, project_id=first_proj.id, event_type="SECTION_REFINE"
        )
        return (items_sev, tot_sev, items_tr, tot_tr, items_proj, tot_proj)

    res, q_count, ms = _count_queries(engine, _run_filters)
    items_sev, tot_sev, items_tr, tot_tr, items_proj, tot_proj = res
    print(f"\n[PERF query_logs] 3 filtered queries total_queries={q_count} latency_ms={ms}")
    assert tot_sev == 25
    assert len(items_sev) == 25
    assert tot_tr == 4
    assert tot_proj == 10
    assert ms < 150.0


def test_perf_reconstruction_snapshot_and_replay_latency(db_session):
    user, first_proj, _ = _seed_heavy_workspace(
        db_session, num_projects=5, sections_per_proj=10, events_per_proj=12
    )
    engine = db_session.get_bind()

    rec_snap, q_snap, ms_snap = _count_queries(
        engine, lambda: ReconstructionService.reconstruct_project(db_session, first_proj, version=1)
    )
    rec_replay, q_replay, ms_replay = _count_queries(
        engine,
        lambda: ReconstructionService.reconstruct_project(
            db_session, first_proj, at_timestamp=datetime.now(timezone.utc)
        ),
    )
    print(
        f"\n[PERF reconstruction] snapshot_q={q_snap} ({ms_snap}ms) | "
        f"replay_q={q_replay} ({ms_replay}ms)"
    )
    assert rec_snap["reconstruction_mode"] == "snapshot_v1"
    assert len(rec_replay["reconstructed_state"]["sections"]) == 10
    assert ms_replay < 200.0


def test_observability_trace_correlation_across_audit_and_llm(db_session):
    user, first_proj, _ = _seed_heavy_workspace(
        db_session, num_projects=2, sections_per_proj=3, events_per_proj=8
    )
    trace = "tr-0-0"
    logs, _ = AuditService.query_logs(db_session, user_id=user.id, trace_id=trace)
    metrics, total_m = AuditService.query_llm_metrics(db_session, user_id=user.id, project_id=first_proj.id)
    assert len(logs) == 4
    assert total_m == 8
    assert all(log_item.trace_id == trace for log_item in logs)
    assert len(metrics) == 8
