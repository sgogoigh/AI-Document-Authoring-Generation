from pathlib import Path

import pytest

from app.core.config import get_settings
from app.models.project import Project
from app.models.section import DocumentSection
from app.models.user import User
from app.services.gemini_service import GeminiService


@pytest.mark.live_ai
def test_live_gemini_outline_generation_refinement_and_image(db_session, tmp_path, monkeypatch):
    get_settings.cache_clear()
    settings = get_settings()
    if not settings.gemini_api_key:
        pytest.skip("GEMINI_API_KEY not configured")

    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "live_storage"))
    get_settings.cache_clear()

    user = User(email="live@example.com", full_name="Live Tester", password_hash="x", auth_provider="local")
    db_session.add(user)
    db_session.flush()

    svc = GeminiService()

    # 1. Live Outline Suggestion
    outline, _ = svc.suggest_outline(
        db_session,
        doc_type="docx",
        main_topic="A market analysis of the EV industry in 2025",
        target_count=4,
        user_id=user.id,
    )
    assert len(outline.items) >= 3

    # 2. Live Section Generation
    proj = Project(
        user_id=user.id,
        title=outline.recommended_title,
        doc_type="docx",
        main_topic="A market analysis of the EV industry in 2025",
        theme_config_json={"tone": "executive", "include_images": True, "palette": "executive_navy"},
    )
    db_session.add(proj)
    db_session.flush()

    sec = DocumentSection(
        project_id=proj.id, order_index=0, title=outline.items[0], section_kind="section"
    )
    db_session.add(sec)
    db_session.flush()

    gen_content, _ = svc.generate_section_content(
        db_session, project=proj, section=sec, sibling_titles=outline.items, user_id=user.id
    )
    assert gen_content["summary_callout"]
    assert len(gen_content["paragraphs"]) >= 1

    # 3. Live Iterative Refinement
    refined_content, _ = svc.refine_section_content(
        db_session,
        project=proj,
        section=sec,
        current_content_json=gen_content,
        refinement_prompt="Shorten to concise executive language under 90 words total.",
        user_id=user.id,
    )
    assert refined_content["summary_callout"]

    # 4. Live Image Generation
    asset = svc.generate_section_image(
        db_session,
        image_prompt=(
            "Minimalist editorial isometric illustration of an electric vehicle charging hub, "
            "clean navy and teal palette, white background"
        ),
        caption="EV Infrastructure Concept",
        project_id=proj.id,
        section_id=sec.id,
        user_id=user.id,
    )
    assert asset is not None
    saved_path = Path(get_settings().storage_dir) / asset.storage_path
    assert saved_path.exists()
    assert asset.width > 100 and asset.height > 100
    get_settings.cache_clear()
