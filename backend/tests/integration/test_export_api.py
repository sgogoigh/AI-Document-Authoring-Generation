import io
from types import SimpleNamespace
from unittest.mock import MagicMock

from docx import Document
from fastapi.testclient import TestClient
from PIL import Image
from pptx import Presentation

from app.api.v1.generation import get_gemini_service
from app.core.config import get_settings
from app.schemas.llm_structured import DocxSectionSchema, PptxSlideSchema
from app.services.gemini_service import GeminiService


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (360, 240), color=(20, 70, 110)).save(buf, format="PNG")
    return buf.getvalue()


def _resp(obj):
    return SimpleNamespace(
        parsed=obj,
        text=obj.model_dump_json(),
        usage_metadata=SimpleNamespace(
            prompt_token_count=30, candidates_token_count=60, total_token_count=90
        ),
    )


def test_export_docx_and_pptx_reflect_latest_refinements_and_assets(
    client: TestClient, tmp_path, monkeypatch
):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    get_settings.cache_clear()

    mock_client = MagicMock()
    img_resp = SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[
                        SimpleNamespace(
                            inline_data=SimpleNamespace(mime_type="image/png", data=_png_bytes())
                        )
                    ]
                )
            )
        ],
        usage_metadata=SimpleNamespace(prompt_token_count=10, candidates_token_count=0, total_token_count=10),
    )
    mock_client.models.generate_content.side_effect = [
        # DOCX initial + image + refine
        _resp(
            DocxSectionSchema(
                summary_callout="Initial DOCX callout",
                paragraphs=["Initial draft paragraph."],
                bullet_points=[],
                should_generate_image=True,
                image_prompt="Clean graph",
                image_caption="Figure 1: EV Curve",
            )
        ),
        img_resp,
        _resp(
            DocxSectionSchema(
                summary_callout="REFINED_DOCX_MARKER: Executive takeaway",
                paragraphs=["Refined authoritative paragraph."],
                bullet_points=[],
                should_generate_image=True,
                image_prompt="Clean graph",
                image_caption="Figure 1: EV Curve",
            )
        ),
        # PPTX initial + refine
        _resp(
            PptxSlideSchema(
                layout_variant="bullets_only",
                kicker="SLIDE ONE",
                subtitle="Initial slide subtitle",
                bullets=["Initial bullet one", "Initial bullet two"],
                speaker_notes="Initial notes",
                should_generate_image=False,
            )
        ),
        _resp(
            PptxSlideSchema(
                layout_variant="bullets_only",
                kicker="SLIDE ONE",
                subtitle="REFINED_PPTX_MARKER: Board summary",
                bullets=["Refined bullet alpha", "Refined bullet beta"],
                speaker_notes="Refined notes",
                should_generate_image=False,
            )
        ),
    ]
    svc = GeminiService(client=mock_client)
    client.app.dependency_overrides[get_gemini_service] = lambda: svc

    try:
        reg = client.post(
            "/api/v1/auth/register",
            json={"email": "exp@example.com", "full_name": "Exporter", "password": "Password123!"},
        )
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        # 1. DOCX project -> generate -> refine -> asset check -> export
        docx_proj = client.post(
            "/api/v1/projects",
            headers=headers,
            json={
                "title": "Export Word Report",
                "doc_type": "docx",
                "main_topic": "EV 2025",
                "sections": [{"title": "Market Analysis"}],
            },
        ).json()
        gen_docx = client.post(f"/api/v1/projects/{docx_proj['id']}/generate", headers=headers).json()
        sec_id = gen_docx["sections"][0]["id"]
        asset_id = gen_docx["sections"][0]["assets"][0]["id"]

        # Asset endpoint serves PNG
        asset_resp = client.get(f"/api/v1/assets/{asset_id}", headers=headers)
        assert asset_resp.status_code == 200
        assert asset_resp.headers["content-type"] == "image/png"

        client.post(
            f"/api/v1/sections/{sec_id}/refine",
            headers=headers,
            json={"refinement_prompt": "Refine for board"},
        )

        exp_docx = client.get(f"/api/v1/projects/{docx_proj['id']}/export", headers=headers)
        assert exp_docx.status_code == 200
        assert "wordprocessingml" in exp_docx.headers["content-type"]
        doc = Document(io.BytesIO(exp_docx.content))
        doc_text = "\n".join(p.text for p in doc.paragraphs)
        tbl_text = "\n".join(c.text for t in doc.tables for r in t.rows for c in r.cells)
        assert "REFINED_DOCX_MARKER" in (doc_text + tbl_text)
        assert "Initial draft paragraph." not in doc_text
        assert len(doc.inline_shapes) == 1

        # Export history recorded
        exp_hist = client.get(f"/api/v1/projects/{docx_proj['id']}/exports", headers=headers).json()
        assert len(exp_hist) == 1
        assert exp_hist[0]["asset_count"] == 1

        # 2. PPTX project -> generate -> refine -> export
        pptx_proj = client.post(
            "/api/v1/projects",
            headers=headers,
            json={
                "title": "Export Deck",
                "doc_type": "pptx",
                "main_topic": "EV Strategy",
                "theme_config": {"include_images": False},
                "sections": [{"title": "Executive Pitch"}],
            },
        ).json()
        gen_pptx = client.post(
            f"/api/v1/projects/{pptx_proj['id']}/generate",
            headers=headers,
            json={"generate_images": False},
        ).json()
        slide_id = gen_pptx["sections"][0]["id"]
        client.post(
            f"/api/v1/sections/{slide_id}/refine",
            headers=headers,
            json={"refinement_prompt": "Executive polish"},
        )

        exp_pptx = client.get(f"/api/v1/projects/{pptx_proj['id']}/export", headers=headers)
        assert exp_pptx.status_code == 200
        assert "presentationml" in exp_pptx.headers["content-type"]
        prs = Presentation(io.BytesIO(exp_pptx.content))
        assert len(prs.slides) == 3
        slide_texts = "\n".join(
            sh.text for sh in prs.slides[2].shapes if sh.has_text_frame
        )
        assert "REFINED_PPTX_MARKER" in slide_texts
        assert "Refined bullet alpha" in slide_texts
        assert "Initial bullet one" not in slide_texts
    finally:
        client.app.dependency_overrides.pop(get_gemini_service, None)
        get_settings.cache_clear()
