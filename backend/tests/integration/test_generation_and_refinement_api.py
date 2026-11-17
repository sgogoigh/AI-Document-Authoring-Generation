import io
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from PIL import Image

from app.api.v1.generation import get_gemini_service
from app.core.config import get_settings
from app.schemas.llm_structured import DocxSectionSchema, OutlineSuggestionSchema
from app.services.gemini_service import GeminiService


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (400, 300), color=(30, 80, 140)).save(buf, format="PNG")
    return buf.getvalue()


def _mock_gemini_client() -> MagicMock:
    mock_client = MagicMock()
    outline = OutlineSuggestionSchema(
        recommended_title="EV Market 2025",
        rationale="Logical strategic flow.",
        items=["Executive Summary", "Charging Infrastructure", "Battery Outlook"],
    )
    sec0 = DocxSectionSchema(
        summary_callout="EV penetration grew 28% YoY.",
        paragraphs=["Global demand expanded rapidly across key regions."],
        bullet_points=[],
        should_generate_image=True,
        image_prompt="EV charging station clean vector",
        image_caption="Figure 1: EV Charging Growth",
    )
    sec1 = DocxSectionSchema(
        summary_callout="Fast charging corridors doubled.",
        paragraphs=["Public fast chargers expanded across highways."],
        bullet_points=[],
        should_generate_image=False,
    )
    sec2 = DocxSectionSchema(
        summary_callout="Battery prices fell 18%.",
        paragraphs=["LFP and solid-state pipelines improved unit economics."],
        bullet_points=[],
        should_generate_image=False,
    )
    refined_sec0 = DocxSectionSchema(
        summary_callout="Formal: Global EV market penetration achieved 28% YoY growth.",
        paragraphs=["Institutional and consumer demand expanded across primary automotive markets."],
        bullet_points=[],
        should_generate_image=True,
        image_prompt="EV charging station clean vector",
        image_caption="Figure 1: EV Charging Growth",
    )
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
        usage_metadata=SimpleNamespace(prompt_token_count=20, candidates_token_count=0, total_token_count=20),
    )

    def _resp(obj):
        return SimpleNamespace(
            parsed=obj,
            text=obj.model_dump_json(),
            usage_metadata=SimpleNamespace(
                prompt_token_count=50, candidates_token_count=100, total_token_count=150
            ),
        )

    mock_client.models.generate_content.side_effect = [
        _resp(outline),
        _resp(sec0),
        img_resp,
        _resp(sec1),
        _resp(sec2),
        _resp(refined_sec0),
    ]
    return mock_client


def test_suggest_outline_generate_refine_feedback_and_comments(
    client: TestClient, tmp_path, monkeypatch
):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    get_settings.cache_clear()

    mock_svc = GeminiService(client=_mock_gemini_client())
    client.app.dependency_overrides[get_gemini_service] = lambda: mock_svc

    try:
        reg = client.post(
            "/api/v1/auth/register",
            json={"email": "gen@example.com", "full_name": "Gen User", "password": "Password123!"},
        )
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        # 1. Bonus: AI-Suggest Outline
        sug_res = client.post(
            "/api/v1/projects/suggest-outline",
            headers=headers,
            json={"doc_type": "docx", "main_topic": "EV Market Analysis 2025"},
        )
        assert sug_res.status_code == 200
        sug_data = sug_res.json()
        assert sug_data["items"] == [
            "Executive Summary",
            "Charging Infrastructure",
            "Battery Outlook",
        ]

        # 2. Create project using suggested outline
        proj_res = client.post(
            "/api/v1/projects",
            headers=headers,
            json={
                "title": sug_data["recommended_title"],
                "doc_type": "docx",
                "main_topic": "EV Market Analysis 2025",
                "sections": [{"title": t} for t in sug_data["items"]],
                "ai_outline_suggested": True,
            },
        )
        assert proj_res.status_code == 201
        proj = proj_res.json()

        # 3. Generate section-by-section (+ image on section 0)
        gen_res = client.post(
            f"/api/v1/projects/{proj['id']}/generate",
            headers=headers,
            json={"generate_images": True},
        )
        assert gen_res.status_code == 200
        generated = gen_res.json()
        assert generated["status"] == "ready"
        sec0 = generated["sections"][0]
        sec1 = generated["sections"][1]
        assert sec0["revision_count"] == 1
        assert len(sec0["assets"]) == 1
        assert sec1["current_content_json"]["summary_callout"] == "Fast charging corridors doubled."

        # 4. Refine ONLY section 0; section 1 must remain untouched
        ref_res = client.post(
            f"/api/v1/sections/{sec0['id']}/refine",
            headers=headers,
            json={"refinement_prompt": "Make this more formal"},
        )
        assert ref_res.status_code == 200
        refined = ref_res.json()
        assert refined["revision_count"] == 2
        assert "Formal:" in refined["current_content_json"]["summary_callout"]

        # Verify section 1 unchanged
        reloaded = client.get(f"/api/v1/projects/{proj['id']}", headers=headers).json()
        assert reloaded["sections"][1]["revision_count"] == 1

        # 5. Revisions list
        revs = client.get(f"/api/v1/sections/{sec0['id']}/revisions", headers=headers).json()
        assert len(revs) == 2
        assert revs[0]["source"] == "ai_refinement"
        assert revs[0]["refinement_prompt"] == "Make this more formal"

        # 6. Feedback Like / Dislike
        fb_res = client.post(
            f"/api/v1/sections/{sec0['id']}/feedback",
            headers=headers,
            json={"rating": "like", "note": "Great executive tone"},
        )
        assert fb_res.status_code == 200
        assert fb_res.json()["like_status"] == "like"

        fb_res2 = client.post(
            f"/api/v1/sections/{sec1['id']}/feedback",
            headers=headers,
            json={"rating": "dislike"},
        )
        assert fb_res2.json()["like_status"] == "dislike"

        # 7. Comments add, list, delete
        c_res = client.post(
            f"/api/v1/sections/{sec0['id']}/comments",
            headers=headers,
            json={"body": "Double check Q4 numbers"},
        )
        assert c_res.status_code == 201
        comment_id = c_res.json()["id"]

        comments = client.get(f"/api/v1/sections/{sec0['id']}/comments", headers=headers).json()
        assert len(comments) == 1
        assert comments[0]["body"] == "Double check Q4 numbers"

        del_c = client.delete(f"/api/v1/comments/{comment_id}", headers=headers)
        assert del_c.status_code == 204
        assert client.get(f"/api/v1/sections/{sec0['id']}/comments", headers=headers).json() == []
    finally:
        client.app.dependency_overrides.pop(get_gemini_service, None)
        get_settings.cache_clear()
