import io
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PIL import Image
from sqlalchemy import select

from app.core.config import get_settings
from app.models.metrics import LLMCallMetric
from app.models.project import Project
from app.models.section import DocumentSection
from app.models.user import User
from app.schemas.llm_structured import DocxSectionSchema, OutlineSuggestionSchema, PptxSlideSchema
from app.services.gemini_service import GeminiService


def _fake_png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (320, 240), color=(20, 60, 120)).save(buf, format="PNG")
    return buf.getvalue()


def _mock_response(parsed_obj, in_tok=100, out_tok=200):
    return SimpleNamespace(
        parsed=parsed_obj,
        text=parsed_obj.model_dump_json(),
        usage_metadata=SimpleNamespace(
            prompt_token_count=in_tok,
            candidates_token_count=out_tok,
            total_token_count=in_tok + out_tok,
        ),
    )


def test_gemini_service_suggest_generate_refine_and_image_mocked(
    db_session, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    get_settings.cache_clear()

    user = User(email="ai@example.com", full_name="AI Tester", password_hash="x", auth_provider="local")
    db_session.add(user)
    db_session.flush()

    proj = Project(
        user_id=user.id,
        title="EV Market 2025",
        doc_type="docx",
        main_topic="EV Industry Analysis 2025",
        theme_config_json={"tone": "executive", "include_images": True, "palette": "executive_navy"},
    )
    db_session.add(proj)
    db_session.flush()

    sec = DocumentSection(project_id=proj.id, order_index=0, title="Executive Summary", section_kind="section")
    db_session.add(sec)
    db_session.flush()

    mock_client = MagicMock()
    outline_obj = OutlineSuggestionSchema(
        recommended_title="EV Market Outlook 2025",
        rationale="Structured from macro adoption to supply chain.",
        items=["Executive Summary", "Market Growth", "Battery Supply Chain", "Strategic Risks"],
    )
    docx_obj = DocxSectionSchema(
        summary_callout="Global EV penetration reached 22% in 2025.",
        paragraphs=["Electric vehicle adoption accelerated across Asia and Europe."],
        bullet_points=[],
        should_generate_image=True,
        image_prompt="Clean minimalist illustration of EV charging network",
        image_caption="Figure 1: Global EV Infrastructure",
    )
    refined_obj = DocxSectionSchema(
        summary_callout="Formal: Global EV market share reached 22%.",
        paragraphs=["Electric vehicle adoption demonstrated sustained institutional expansion."],
        bullet_points=[],
        should_generate_image=True,
        image_prompt="Clean minimalist illustration of EV charging network",
        image_caption="Figure 1: Global EV Infrastructure",
    )

    img_response = SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[
                        SimpleNamespace(
                            inline_data=SimpleNamespace(mime_type="image/png", data=_fake_png_bytes())
                        )
                    ]
                )
            )
        ],
        usage_metadata=SimpleNamespace(prompt_token_count=40, candidates_token_count=0, total_token_count=40),
    )

    mock_client.models.generate_content.side_effect = [
        _mock_response(outline_obj),
        _mock_response(docx_obj),
        _mock_response(refined_obj),
        img_response,
    ]

    svc = GeminiService(client=mock_client)

    suggested, m1 = svc.suggest_outline(db_session, doc_type="docx", main_topic="EV 2025", user_id=user.id)
    assert len(suggested.items) == 4
    assert m1

    gen_json, m2 = svc.generate_section_content(
        db_session, project=proj, section=sec, sibling_titles=suggested.items, user_id=user.id
    )
    assert gen_json["summary_callout"].startswith("Global EV")

    ref_json, m3 = svc.refine_section_content(
        db_session,
        project=proj,
        section=sec,
        current_content_json=gen_json,
        refinement_prompt="Make this more formal",
        user_id=user.id,
    )
    assert "Formal:" in ref_json["summary_callout"]

    asset = svc.generate_section_image(
        db_session,
        image_prompt=ref_json["image_prompt"],
        caption=ref_json["image_caption"],
        project_id=proj.id,
        section_id=sec.id,
        user_id=user.id,
    )
    db_session.commit()

    assert asset is not None
    assert asset.width == 320
    assert asset.height == 240
    assert (get_settings().assets_dir / asset.storage_path.split("/")[-1]).exists()

    metrics = db_session.scalars(select(LLMCallMetric)).all()
    assert len(metrics) == 4
    assert {m.operation for m in metrics} == {
        "outline_suggest",
        "section_generate",
        "section_refine",
        "image_generate",
    }
    get_settings.cache_clear()


def test_gemini_service_records_error_metric_on_failure(db_session):
    user = User(email="err@example.com", full_name="Err", password_hash="x", auth_provider="local")
    db_session.add(user)
    db_session.flush()

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("Upstream 503")
    svc = GeminiService(client=mock_client)

    with pytest.raises(Exception):
        svc.suggest_outline(db_session, doc_type="pptx", main_topic="AI Deck", user_id=user.id)

    err_metric = db_session.scalar(select(LLMCallMetric).where(LLMCallMetric.status == "error"))
    assert err_metric is not None
    assert "Upstream 503" in (err_metric.error_message or "")
    assert PptxSlideSchema is not None
