from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.v1.generation import get_gemini_service
from app.schemas.llm_structured import PptxSlideSchema
from app.services.gemini_service import GeminiService


def _mock_pptx_gemini() -> GeminiService:
    mock_client = MagicMock()
    slide_v1 = PptxSlideSchema(
        layout_variant="bullets_only",
        kicker="OVERVIEW",
        subtitle="Initial slide subtitle",
        bullets=["Point A initial", "Point B initial"],
        speaker_notes="Initial presenter notes.",
        should_generate_image=False,
    )
    slide_v2 = PptxSlideSchema(
        layout_variant="metrics_cards",
        kicker="OVERVIEW",
        subtitle="Refined executive metrics subtitle",
        bullets=["Point A refined", "Point B refined"],
        speaker_notes="Refined presenter notes.",
        should_generate_image=False,
    )

    def _resp(obj):
        return SimpleNamespace(
            parsed=obj,
            text=obj.model_dump_json(),
            usage_metadata=SimpleNamespace(
                prompt_token_count=40, candidates_token_count=80, total_token_count=120
            ),
        )

    mock_client.models.generate_content.side_effect = [_resp(slide_v1), _resp(slide_v2)]
    return GeminiService(client=mock_client)


def test_monitoring_logs_metrics_timeline_reconstruction_and_restore(client: TestClient):
    mock_svc = _mock_pptx_gemini()
    client.app.dependency_overrides[get_gemini_service] = lambda: mock_svc
    try:
        reg = client.post(
            "/api/v1/auth/register",
            json={"email": "mon@example.com", "full_name": "Mon User", "password": "Password123!"},
        )
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        proj = client.post(
            "/api/v1/projects",
            headers=headers,
            json={
                "title": "AI Governance Deck",
                "doc_type": "pptx",
                "main_topic": "Enterprise AI Governance",
                "theme_config": {"include_images": False},
                "sections": [{"title": "Strategic Overview"}],
            },
        ).json()

        # v2: generate
        gen = client.post(
            f"/api/v1/projects/{proj['id']}/generate",
            headers=headers,
            json={"generate_images": False},
        ).json()
        sec_id = gen["sections"][0]["id"]
        v_generated = gen["current_version"]

        # v3: refine
        client.post(
            f"/api/v1/sections/{sec_id}/refine",
            headers=headers,
            json={"refinement_prompt": "Switch to metrics framing"},
        )
        client.post(
            f"/api/v1/sections/{sec_id}/feedback",
            headers=headers,
            json={"rating": "like"},
        )

        # Query filtered audit logs
        logs_res = client.get(
            "/api/v1/monitoring/logs",
            headers=headers,
            params={"project_id": proj["id"], "event_type": "SECTION_REFINE"},
        )
        assert logs_res.status_code == 200
        assert logs_res.json()["total"] == 1
        assert logs_res.json()["items"][0]["metadata_json"]["refinement_prompt"] == "Switch to metrics framing"

        # Query aggregated metrics
        metrics_res = client.get(
            "/api/v1/monitoring/metrics",
            headers=headers,
            params={"project_id": proj["id"]},
        )
        assert metrics_res.status_code == 200
        metrics_data = metrics_res.json()
        assert metrics_data["analytics"]["llm"]["total_calls"] == 2
        assert metrics_data["analytics"]["llm"]["total_tokens"] == 240
        assert metrics_data["analytics"]["feedback"]["like_count"] == 1
        assert metrics_data["analytics"]["feedback"]["satisfaction_rate_pct"] == 100.0

        # Project timeline
        tl_res = client.get(f"/api/v1/projects/{proj['id']}/timeline", headers=headers)
        assert tl_res.status_code == 200
        assert tl_res.json()["current_version"] == 3
        assert len(tl_res.json()["snapshots"]) == 3

        # Reconstruct at generated version (v2)
        rec_res = client.get(
            f"/api/v1/projects/{proj['id']}/reconstruct",
            headers=headers,
            params={"version": v_generated},
        )
        assert rec_res.status_code == 200
        rec = rec_res.json()
        rec_sub = rec["reconstructed_state"]["sections"][0]["current_content_json"]["subtitle"]
        assert rec_sub == "Initial slide subtitle"
        assert len(rec["diff_against_live"]) == 1

        # Non-destructive restore to v2 -> creates v4
        rest_res = client.post(
            f"/api/v1/projects/{proj['id']}/restore/{v_generated}",
            headers=headers,
        )
        assert rest_res.status_code == 200
        assert rest_res.json()["new_version"] == 4
        assert rest_res.json()["restored_sections"] == 1

        live_after = client.get(f"/api/v1/projects/{proj['id']}", headers=headers).json()
        assert live_after["sections"][0]["current_content_json"]["subtitle"] == "Initial slide subtitle"
        assert live_after["sections"][0]["revision_count"] == 3
    finally:
        client.app.dependency_overrides.pop(get_gemini_service, None)
