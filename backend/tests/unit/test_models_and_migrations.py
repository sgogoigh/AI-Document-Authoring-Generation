from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command
from app.core.database import Base
from app.models import (
    AuditEventLog,
    DocumentAsset,
    DocumentSection,
    ExportRecord,
    FeedbackEvent,
    LLMCallMetric,
    Project,
    ProjectSnapshot,
    SectionComment,
    SectionRevision,
    User,
)


def test_all_tables_registered_in_metadata():
    expected_tables = {
        "users",
        "projects",
        "document_sections",
        "section_revisions",
        "section_comments",
        "feedback_events",
        "document_assets",
        "export_records",
        "audit_event_logs",
        "llm_call_metrics",
        "project_snapshots",
    }
    assert expected_tables.issubset(set(Base.metadata.tables.keys()))


def test_orm_relationships_and_persistence(db_session):
    user = User(email="alice@example.com", full_name="Alice", password_hash="hashed", auth_provider="local")
    db_session.add(user)
    db_session.flush()

    project = Project(
        user_id=user.id,
        title="EV Market 2025",
        doc_type="docx",
        main_topic="A market analysis of the EV industry in 2025",
        status="configured",
    )
    db_session.add(project)
    db_session.flush()

    section = DocumentSection(
        project_id=project.id,
        order_index=0,
        title="Executive Summary",
        section_kind="section",
    )
    db_session.add(section)
    db_session.flush()

    metric = LLMCallMetric(
        trace_id="trace-1",
        user_id=user.id,
        project_id=project.id,
        section_id=section.id,
        operation="section_generate",
        model_name="gemini-2.5-flash",
        input_tokens=120,
        output_tokens=240,
        total_tokens=360,
        latency_ms=850.5,
        status="success",
    )
    db_session.add(metric)
    db_session.flush()

    revision = SectionRevision(
        section_id=section.id,
        project_id=project.id,
        revision_number=1,
        project_version=1,
        source="initial_generation",
        new_content_json={"paragraphs": ["EV adoption accelerated."]},
        llm_metric_id=metric.id,
        created_by=user.id,
    )
    db_session.add(revision)
    db_session.flush()

    section.current_revision_id = revision.id
    section.current_content_json = revision.new_content_json
    section.current_content_text = "EV adoption accelerated."

    comment = SectionComment(section_id=section.id, project_id=project.id, user_id=user.id, body="Looks strong")
    feedback = FeedbackEvent(
        section_id=section.id,
        project_id=project.id,
        user_id=user.id,
        revision_id=revision.id,
        rating="like",
    )
    asset = DocumentAsset(
        project_id=project.id,
        section_id=section.id,
        prompt="EV market growth chart",
        storage_path="assets/ev.png",
        width=1024,
        height=768,
        llm_metric_id=metric.id,
    )
    export = ExportRecord(
        project_id=project.id,
        user_id=user.id,
        doc_type="docx",
        project_version=1,
        file_name="ev_market.docx",
        file_size_bytes=42000,
        section_count=1,
        asset_count=1,
    )
    audit = AuditEventLog(
        trace_id="trace-1",
        user_id=user.id,
        project_id=project.id,
        section_id=section.id,
        event_type="SECTION_GENERATE",
        entity_type="section",
        entity_id=section.id,
        after_state_json={"revision_number": 1},
    )
    snapshot = ProjectSnapshot(
        project_id=project.id,
        version_number=1,
        trigger_event_type="SECTION_GENERATE",
        trigger_event_id=audit.event_id,
        snapshot_json={"title": project.title, "sections": [{"id": section.id}]},
    )

    db_session.add_all([comment, feedback, asset, export, audit, snapshot])
    db_session.commit()

    reloaded_project = db_session.get(Project, project.id)
    assert reloaded_project is not None
    assert len(reloaded_project.sections) == 1
    assert reloaded_project.sections[0].current_revision_id == revision.id
    assert len(reloaded_project.sections[0].comments) == 1
    assert len(reloaded_project.sections[0].feedback_events) == 1
    assert len(reloaded_project.assets) == 1
    assert len(reloaded_project.exports) == 1
    assert len(reloaded_project.snapshots) == 1


def test_alembic_upgrade_and_downgrade_on_fresh_sqlite(tmp_path: Path):
    backend_dir = Path(__file__).resolve().parents[2]
    db_file = tmp_path / "migration_test.db"
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_file.as_posix()}")

    command.upgrade(alembic_cfg, "head")
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")
    tables_after_upgrade = set(inspect(engine).get_table_names())
    assert "users" in tables_after_upgrade
    assert "audit_event_logs" in tables_after_upgrade
    assert "project_snapshots" in tables_after_upgrade
    engine.dispose()

    command.downgrade(alembic_cfg, "base")
    engine2 = create_engine(f"sqlite:///{db_file.as_posix()}")
    tables_after_downgrade = set(inspect(engine2).get_table_names())
    assert "users" not in tables_after_downgrade
    assert "audit_event_logs" not in tables_after_downgrade
    engine2.dispose()
