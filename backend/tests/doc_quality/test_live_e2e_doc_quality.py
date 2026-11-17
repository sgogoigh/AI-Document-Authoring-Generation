import io
import os
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient
from pptx import Presentation

from app.core.config import get_settings
from app.services.doc_builder.pptx_builder import SLIDE_H, SLIDE_W


@pytest.mark.live_ai
def test_live_e2e_docx_and_pptx_structural_and_content_quality(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    get_settings.cache_clear()
    settings = get_settings()
    if not settings.gemini_api_key:
        pytest.skip("GEMINI_API_KEY not configured")

    qa_dir_env = os.environ.get("QA_EXPORT_DIR")
    out_dir = Path(qa_dir_env) if qa_dir_env else (tmp_path / "qa_exports")
    out_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("STORAGE_DIR", str(out_dir / "storage"))
    get_settings.cache_clear()

    try:
        # 1. Register user
        reg = client.post(
            "/api/v1/auth/register",
            json={
                "email": "qa_lead@example.com",
                "full_name": "QA Lead",
                "password": "StrongPassword123!",
            },
        )
        assert reg.status_code == 201
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        # ------------------------------------------------------------------
        # 2. Full Word (.docx) End-to-End Run with AI-Suggest Outline + Images
        # ------------------------------------------------------------------
        docx_topic = (
            "A market analysis of the EV industry in 2025 covering battery supply chains, "
            "charging infrastructure, and regional adoption"
        )
        docx_suggest = client.post(
            "/api/v1/projects/suggest-outline",
            headers=headers,
            json={"doc_type": "docx", "main_topic": docx_topic, "target_count": 4},
        )
        assert docx_suggest.status_code == 200
        sug_docx = docx_suggest.json()
        assert len(sug_docx["items"]) >= 3

        docx_proj = client.post(
            "/api/v1/projects",
            headers=headers,
            json={
                "title": sug_docx["recommended_title"],
                "doc_type": "docx",
                "main_topic": docx_topic,
                "theme_config": {
                    "palette": "executive_navy",
                    "tone": "executive",
                    "audience": "Board & Investment Committee",
                    "include_images": True,
                },
                "sections": [{"title": t} for t in sug_docx["items"][:4]],
                "ai_outline_suggested": True,
            },
        ).json()

        gen_docx = client.post(
            f"/api/v1/projects/{docx_proj['id']}/generate",
            headers=headers,
            json={"generate_images": True},
        )
        assert gen_docx.status_code == 200
        gen_docx_data = gen_docx.json()
        assert gen_docx_data["status"] == "ready"

        # Guarantee at least one Gemini visual asset exists for visual QA
        total_docx_assets = sum(len(s["assets"]) for s in gen_docx_data["sections"])
        if total_docx_assets == 0:
            sec0_id = gen_docx_data["sections"][0]["id"]
            img_res = client.post(
                f"/api/v1/sections/{sec0_id}/regenerate-image",
                headers=headers,
                json={
                    "image_prompt": (
                        "Minimalist isometric illustration of global EV battery and charging "
                        "ecosystem, corporate navy and teal"
                    ),
                    "caption": "Figure 1: 2025 EV Ecosystem Overview",
                },
            )
            assert img_res.status_code == 200

        sec0 = gen_docx_data["sections"][0]
        sec1 = gen_docx_data["sections"][1]

        # Refine Section 0, set Like/Dislike, add Comment
        ref_docx = client.post(
            f"/api/v1/sections/{sec0['id']}/refine",
            headers=headers,
            json={
                "refinement_prompt": (
                    "Make this more formal and executive; keep paragraphs crisp and include "
                    "the phrase 'Strategic Executive Outlook' in the summary callout."
                )
            },
        )
        assert ref_docx.status_code == 200

        client.post(f"/api/v1/sections/{sec0['id']}/feedback", headers=headers, json={"rating": "like"})
        client.post(f"/api/v1/sections/{sec1['id']}/feedback", headers=headers, json={"rating": "dislike"})
        client.post(
            f"/api/v1/sections/{sec0['id']}/comments",
            headers=headers,
            json={"body": "Board-ready executive framing verified."},
        )

        # Export .docx and inspect programmatically
        exp_docx = client.get(f"/api/v1/projects/{docx_proj['id']}/export", headers=headers)
        assert exp_docx.status_code == 200
        docx_path = out_dir / "EV_Market_Analysis_2025.docx"
        docx_path.write_bytes(exp_docx.content)

        doc = Document(io.BytesIO(exp_docx.content))
        all_paras = "\n".join(p.text for p in doc.paragraphs)
        all_tbls = "\n".join(c.text for t in doc.tables for r in t.rows for c in r.cells)
        assert "Document Outline" in all_paras
        for sec in gen_docx_data["sections"]:
            assert sec["title"] in all_paras
        assert "Strategic Executive Outlook" in (all_paras + all_tbls)
        assert len(doc.inline_shapes) >= 1

        # ------------------------------------------------------------------
        # 3. Full PowerPoint (.pptx) End-to-End Run with AI-Suggest + Images
        # ------------------------------------------------------------------
        pptx_topic = "Enterprise AI Transformation Strategy 2026 for Global Operations"
        pptx_suggest = client.post(
            "/api/v1/projects/suggest-outline",
            headers=headers,
            json={"doc_type": "pptx", "main_topic": pptx_topic, "target_count": 4},
        )
        assert pptx_suggest.status_code == 200
        sug_pptx = pptx_suggest.json()

        pptx_proj = client.post(
            "/api/v1/projects",
            headers=headers,
            json={
                "title": sug_pptx["recommended_title"],
                "doc_type": "pptx",
                "main_topic": pptx_topic,
                "theme_config": {
                    "palette": "emerald_slate",
                    "tone": "executive",
                    "audience": "C-Suite & Engineering Leadership",
                    "include_images": True,
                },
                "sections": [{"title": t} for t in sug_pptx["items"][:4]],
                "ai_outline_suggested": True,
            },
        ).json()

        gen_pptx = client.post(
            f"/api/v1/projects/{pptx_proj['id']}/generate",
            headers=headers,
            json={"generate_images": True},
        )
        assert gen_pptx.status_code == 200
        gen_pptx_data = gen_pptx.json()

        total_pptx_assets = sum(len(s["assets"]) for s in gen_pptx_data["sections"])
        if total_pptx_assets == 0:
            s0_id = gen_pptx_data["sections"][0]["id"]
            img_res = client.post(
                f"/api/v1/sections/{s0_id}/regenerate-image",
                headers=headers,
                json={
                    "image_prompt": (
                        "Minimalist modern corporate geometric network graphic representing "
                        "enterprise AI architecture, emerald and slate palette"
                    ),
                    "caption": "Enterprise AI Platform Architecture",
                },
            )
            assert img_res.status_code == 200

        slide0 = gen_pptx_data["sections"][0]
        ref_pptx = client.post(
            f"/api/v1/sections/{slide0['id']}/refine",
            headers=headers,
            json={
                "refinement_prompt": "Sharpen bullets to under 14 words each and highlight measurable ROI impact."
            },
        )
        assert ref_pptx.status_code == 200

        exp_pptx = client.get(f"/api/v1/projects/{pptx_proj['id']}/export", headers=headers)
        assert exp_pptx.status_code == 200
        pptx_path = out_dir / "Enterprise_AI_Strategy_2026.pptx"
        pptx_path.write_bytes(exp_pptx.content)

        prs = Presentation(io.BytesIO(exp_pptx.content))
        assert prs.slide_width == SLIDE_W
        assert prs.slide_height == SLIDE_H
        assert len(prs.slides) == 6  # Cover + Agenda + 4 content slides

        picture_count = 0
        for s_idx, slide in enumerate(prs.slides):
            for shape in slide.shapes:
                assert shape.left >= 0
                assert shape.top >= 0
                assert shape.left + shape.width <= SLIDE_W + 5000
                assert shape.top + shape.height <= SLIDE_H + 5000
                if shape.shape_type == 13:
                    picture_count += 1
            if s_idx >= 2:
                assert slide.notes_slide.notes_text_frame.text.strip() != ""
        assert picture_count >= 1

        # Verify monitoring analytics recorded both live runs cleanly
        metrics = client.get("/api/v1/monitoring/metrics", headers=headers).json()
        assert metrics["analytics"]["llm"]["total_calls"] >= 10
        assert metrics["analytics"]["llm"]["total_tokens"] > 0
        assert metrics["analytics"]["exports"]["total_exports"] == 2
    finally:
        get_settings.cache_clear()
