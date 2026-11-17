import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from docx import Document
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from app.api.v1.generation import get_gemini_service
from app.core.config import get_settings
from app.models.audit import AuditEventLog
from app.models.metrics import LLMCallMetric
from app.models.section import FeedbackEvent
from app.schemas.llm_structured import DocxSectionSchema, PptxSlideSchema
from app.services.gemini_service import GeminiService


def _png_bytes(size=(300, 200)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color=(20, 80, 120)).save(buf, format="PNG")
    return buf.getvalue()


def _resp(obj, text_override: str | None = None):
    return SimpleNamespace(
        parsed=None if text_override is not None else obj,
        text=text_override if text_override is not None else obj.model_dump_json(),
        usage_metadata=SimpleNamespace(prompt_token_count=25, candidates_token_count=55, total_token_count=80),
    )


def _img_resp():
    return SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[SimpleNamespace(inline_data=SimpleNamespace(mime_type="image/png", data=_png_bytes()))]
                )
            )
        ],
        usage_metadata=SimpleNamespace(prompt_token_count=10, candidates_token_count=0, total_token_count=10),
    )


def _register(client: TestClient, email: str) -> dict[str, str]:
    res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Scenario User", "password": "Password123!"},
    )
    assert res.status_code == 201
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_scenario_only_missing_preserves_refined_sections_after_outline_edit(client: TestClient):
    mock_client = MagicMock()
    sec_a = DocxSectionSchema(summary_callout="Initial A", paragraphs=["Para A"], should_generate_image=False)
    sec_b = DocxSectionSchema(summary_callout="Initial B", paragraphs=["Para B"], should_generate_image=False)
    ref_a = DocxSectionSchema(
        summary_callout="REFINED_A_KEEP", paragraphs=["Refined A"], should_generate_image=False
    )
    sec_c = DocxSectionSchema(summary_callout="NEW_C", paragraphs=["Para C"], should_generate_image=False)
    mock_client.models.generate_content.side_effect = [
        _resp(sec_a),
        _resp(sec_b),
        _resp(ref_a),
        _resp(sec_c),
    ]
    svc = GeminiService(client=mock_client)
    client.app.dependency_overrides[get_gemini_service] = lambda: svc

    try:
        headers = _register(client, "onlymissing@example.com")
        proj = client.post(
            "/api/v1/projects",
            headers=headers,
            json={
                "title": "Incremental Doc",
                "doc_type": "docx",
                "main_topic": "Incremental test",
                "theme_config": {"include_images": False},
                "sections": [{"title": "Alpha"}, {"title": "Beta"}],
            },
        ).json()

        gen1 = client.post(f"/api/v1/projects/{proj['id']}/generate", headers=headers).json()
        sec_a_id = gen1["sections"][0]["id"]
        client.post(
            f"/api/v1/sections/{sec_a_id}/refine",
            headers=headers,
            json={"refinement_prompt": "Keep refined A"},
        )

        # Reorder Alpha after new section Gamma, remove Beta
        client.put(
            f"/api/v1/projects/{proj['id']}/outline",
            headers=headers,
            json={"sections": [{"title": "Gamma"}, {"id": sec_a_id, "title": "Alpha"}]},
        )

        # Generate only missing (Gamma) -> Alpha must remain REFINED_A_KEEP
        gen2 = client.post(
            f"/api/v1/projects/{proj['id']}/generate",
            headers=headers,
            json={"generate_images": False, "only_missing": True},
        ).json()
        assert [s["title"] for s in gen2["sections"]] == ["Gamma", "Alpha"]
        assert gen2["sections"][0]["current_content_json"]["summary_callout"] == "NEW_C"
        assert gen2["sections"][1]["current_content_json"]["summary_callout"] == "REFINED_A_KEEP"

        # Export order matches Gamma then Alpha
        exp = client.get(f"/api/v1/projects/{proj['id']}/export", headers=headers)
        doc = Document(io.BytesIO(exp.content))
        txt = "\n".join(p.text for p in doc.paragraphs)
        assert txt.index("Gamma") < txt.index("Alpha")
    finally:
        client.app.dependency_overrides.pop(get_gemini_service, None)


def test_scenario_five_round_refinement_chain_and_reconstruction(client: TestClient):
    mock_client = MagicMock()
    slides = [
        PptxSlideSchema(
            layout_variant="bullets_only",
            kicker=f"ROUND {r}",
            subtitle=f"Subtitle round {r}",
            bullets=[f"Bullet {r}.1", f"Bullet {r}.2"],
            speaker_notes=f"Notes round {r}",
            should_generate_image=False,
        )
        for r in range(6)
    ]
    mock_client.models.generate_content.side_effect = [_resp(s) for s in slides]
    svc = GeminiService(client=mock_client)
    client.app.dependency_overrides[get_gemini_service] = lambda: svc

    try:
        headers = _register(client, "chain5@example.com")
        proj = client.post(
            "/api/v1/projects",
            headers=headers,
            json={
                "title": "Iterative Chain",
                "doc_type": "pptx",
                "main_topic": "Refinement chain",
                "theme_config": {"include_images": False},
                "sections": [{"title": "Core Thesis"}],
            },
        ).json()
        gen = client.post(f"/api/v1/projects/{proj['id']}/generate", headers=headers).json()
        sec_id = gen["sections"][0]["id"]

        for r in range(1, 6):
            res = client.post(
                f"/api/v1/sections/{sec_id}/refine",
                headers=headers,
                json={"refinement_prompt": f"Refinement pass {r}"},
            )
            assert res.status_code == 200
            assert res.json()["revision_count"] == r + 1

        revs = client.get(f"/api/v1/sections/{sec_id}/revisions", headers=headers).json()
        assert len(revs) == 6
        assert [r["revision_number"] for r in revs] == [6, 5, 4, 3, 2, 1]
        assert revs[0]["previous_content_json"]["kicker"] == "ROUND 4"
        assert revs[0]["new_content_json"]["kicker"] == "ROUND 5"

        # Reconstruct at v3 (after 1st refinement -> ROUND 1)
        rec_v3 = client.get(
            f"/api/v1/projects/{proj['id']}/reconstruct", headers=headers, params={"version": 3}
        ).json()
        assert rec_v3["reconstructed_state"]["sections"][0]["current_content_json"]["kicker"] == "ROUND 1"
    finally:
        client.app.dependency_overrides.pop(get_gemini_service, None)


def test_scenario_mid_generation_failure_logs_error_metric(client: TestClient, db_session):
    mock_client = MagicMock()
    ok_sec = DocxSectionSchema(summary_callout="OK", paragraphs=["Good text"], should_generate_image=False)
    mock_client.models.generate_content.side_effect = [_resp(ok_sec), RuntimeError("Gemini 503 Timeout")]
    svc = GeminiService(client=mock_client)
    client.app.dependency_overrides[get_gemini_service] = lambda: svc

    try:
        headers = _register(client, "midfail@example.com")
        proj = client.post(
            "/api/v1/projects",
            headers=headers,
            json={
                "title": "Mid Fail Doc",
                "doc_type": "docx",
                "main_topic": "Failure test",
                "theme_config": {"include_images": False},
                "sections": [{"title": "Sec 1"}, {"title": "Sec 2"}],
            },
        ).json()

        res = client.post(f"/api/v1/projects/{proj['id']}/generate", headers=headers)
        assert res.status_code == 502
        err_metric = db_session.scalar(select(LLMCallMetric).where(LLMCallMetric.status == "error"))
        assert err_metric is not None
        assert "503 Timeout" in (err_metric.error_message or "")
    finally:
        client.app.dependency_overrides.pop(get_gemini_service, None)


def test_scenario_json_text_fallback_and_malformed_json_error(client: TestClient, db_session):
    valid_obj = DocxSectionSchema(
        summary_callout="Parsed from text", paragraphs=["Body"], should_generate_image=False
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [
        _resp(valid_obj, text_override=valid_obj.model_dump_json()),
        _resp(valid_obj, text_override="{broken-not-json"),
    ]
    svc = GeminiService(client=mock_client)
    client.app.dependency_overrides[get_gemini_service] = lambda: svc

    try:
        headers = _register(client, "jsonfb@example.com")
        proj = client.post(
            "/api/v1/projects",
            headers=headers,
            json={
                "title": "JSON Fallback",
                "doc_type": "docx",
                "main_topic": "JSON test",
                "theme_config": {"include_images": False},
                "sections": [{"title": "S1"}],
            },
        ).json()

        ok_res = client.post(f"/api/v1/projects/{proj['id']}/generate", headers=headers)
        assert ok_res.status_code == 200
        sec_id = ok_res.json()["sections"][0]["id"]

        bad_ref = client.post(
            f"/api/v1/sections/{sec_id}/refine",
            headers=headers,
            json={"refinement_prompt": "Refine"},
        )
        assert bad_ref.status_code == 502
        assert db_session.scalar(select(LLMCallMetric).where(LLMCallMetric.status == "error")) is not None
    finally:
        client.app.dependency_overrides.pop(get_gemini_service, None)


def test_scenario_empty_image_response_and_missing_disk_asset_at_export(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    get_settings.cache_clear()

    sec_with_img = DocxSectionSchema(
        summary_callout="Img section",
        paragraphs=["Content"],
        should_generate_image=True,
        image_prompt="Clean graph",
        image_caption="Chart 1",
    )
    empty_img_resp = SimpleNamespace(candidates=[], usage_metadata=None)

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [
        _resp(sec_with_img),
        empty_img_resp,  # empty image bytes on initial gen -> graceful skip
        _resp(sec_with_img),
        _img_resp(),  # image created on second run
    ]
    svc = GeminiService(client=mock_client)
    client.app.dependency_overrides[get_gemini_service] = lambda: svc

    try:
        headers = _register(client, "imgres@example.com")
        proj = client.post(
            "/api/v1/projects",
            headers=headers,
            json={
                "title": "Q1/Q2 <EV> Report: 2025 & Beyond!",
                "doc_type": "docx",
                "main_topic": "Image resilience",
                "sections": [{"title": "Visuals"}],
            },
        ).json()

        # First generation: empty image response does not fail generation
        gen1 = client.post(f"/api/v1/projects/{proj['id']}/generate", headers=headers)
        assert gen1.status_code == 200
        assert gen1.json()["sections"][0]["assets"] == []

        # Second generation creates image file, then delete file from disk before export
        gen2 = client.post(f"/api/v1/projects/{proj['id']}/generate", headers=headers)
        assert len(gen2.json()["sections"][0]["assets"]) == 1
        for png in get_settings().assets_dir.glob("*.png"):
            png.unlink()

        exp = client.get(f"/api/v1/projects/{proj['id']}/export", headers=headers)
        assert exp.status_code == 200
        assert 'filename="Q1_Q2_EV_Report_2025_Beyond.docx"' in exp.headers["content-disposition"]
    finally:
        client.app.dependency_overrides.pop(get_gemini_service, None)
        get_settings.cache_clear()


@pytest.mark.parametrize("include_images_flag,env_enable_images", [(False, "true"), (True, "false")])
def test_scenario_image_generation_toggles_skip_image_calls(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, include_images_flag: bool, env_enable_images: str
):
    monkeypatch.setenv("ENABLE_IMAGE_GENERATION", env_enable_images)
    get_settings.cache_clear()

    sec_wants_img = DocxSectionSchema(
        summary_callout="Wants img",
        paragraphs=["Body"],
        should_generate_image=True,
        image_prompt="Prompt",
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [_resp(sec_wants_img)]
    svc = GeminiService(client=mock_client)
    client.app.dependency_overrides[get_gemini_service] = lambda: svc

    try:
        headers = _register(client, f"tog_{include_images_flag}_{env_enable_images}@example.com")
        proj = client.post(
            "/api/v1/projects",
            headers=headers,
            json={
                "title": "Toggle Test",
                "doc_type": "docx",
                "main_topic": "Toggle",
                "theme_config": {"include_images": include_images_flag},
                "sections": [{"title": "S1"}],
            },
        ).json()
        gen = client.post(f"/api/v1/projects/{proj['id']}/generate", headers=headers).json()
        assert gen["sections"][0]["assets"] == []
        assert mock_client.models.generate_content.call_count == 1
    finally:
        client.app.dependency_overrides.pop(get_gemini_service, None)
        get_settings.cache_clear()


def test_scenario_feedback_toggle_comment_delete_and_seq_reconstruction(client: TestClient, db_session):
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [
        _resp(DocxSectionSchema(summary_callout="Initial", paragraphs=["Body"], should_generate_image=False)),
        _resp(DocxSectionSchema(summary_callout="Edited", paragraphs=["Body 2"], should_generate_image=False)),
    ]
    svc = GeminiService(client=mock_client)
    client.app.dependency_overrides[get_gemini_service] = lambda: svc

    try:
        headers_owner = _register(client, "owner_fb@example.com")
        headers_other = _register(client, "intruder_fb@example.com")

        proj = client.post(
            "/api/v1/projects",
            headers=headers_owner,
            json={
                "title": "Audit Trail Doc",
                "doc_type": "docx",
                "main_topic": "Trail",
                "theme_config": {"include_images": False},
                "sections": [{"title": "Sec 1"}],
            },
        ).json()
        gen = client.post(f"/api/v1/projects/{proj['id']}/generate", headers=headers_owner).json()
        sec_id = gen["sections"][0]["id"]

        # Feedback toggle cycle
        for rating in ("like", "dislike", "none"):
            r = client.post(
                f"/api/v1/sections/{sec_id}/feedback", headers=headers_owner, json={"rating": rating}
            )
            assert r.json()["like_status"] == rating
        fb_rows = db_session.scalars(
            select(FeedbackEvent).where(FeedbackEvent.section_id == sec_id)
        ).all()
        assert [f.rating for f in fb_rows] == ["like", "dislike", "none"]

        # Comment add + delete
        c = client.post(
            f"/api/v1/sections/{sec_id}/comments",
            headers=headers_owner,
            json={"body": "Temp note"},
        ).json()
        assert client.delete(f"/api/v1/comments/{c['id']}", headers=headers_owner).status_code == 204

        # Seq-id reconstruction before refine
        gen_event = db_session.scalar(
            select(AuditEventLog).where(
                AuditEventLog.project_id == proj["id"],
                AuditEventLog.event_type == "CONTENT_GENERATE",
            )
        )
        assert gen_event is not None

        client.post(
            f"/api/v1/sections/{sec_id}/refine",
            headers=headers_owner,
            json={"refinement_prompt": "Update text"},
        )

        rec_seq = client.get(
            f"/api/v1/projects/{proj['id']}/reconstruct",
            headers=headers_owner,
            params={"event_seq_id": gen_event.seq_id},
        ).json()
        assert rec_seq["reconstruction_mode"] == f"event_seq_{gen_event.seq_id}"
        rec_callout = rec_seq["reconstructed_state"]["sections"][0]["current_content_json"][
            "summary_callout"
        ]
        assert rec_callout == "Initial"

        # Timestamp in future equals live state
        future_ts = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        rec_ts = client.get(
            f"/api/v1/projects/{proj['id']}/reconstruct",
            headers=headers_owner,
            params={"at_timestamp": future_ts},
        ).json()
        assert rec_ts["reconstructed_state"]["sections"][0]["current_content_json"]["summary_callout"] == "Edited"

        # Cross-user 403 checks on every endpoint
        assert client.post(f"/api/v1/projects/{proj['id']}/generate", headers=headers_other).status_code == 403
        assert (
            client.post(
                f"/api/v1/sections/{sec_id}/refine",
                headers=headers_other,
                json={"refinement_prompt": "Hack"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"/api/v1/sections/{sec_id}/feedback", headers=headers_other, json={"rating": "like"}
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"/api/v1/sections/{sec_id}/comments", headers=headers_other, json={"body": "Hack"}
            ).status_code
            == 403
        )
        assert client.get(f"/api/v1/sections/{sec_id}/revisions", headers=headers_other).status_code == 403
        assert client.get(f"/api/v1/projects/{proj['id']}/export", headers=headers_other).status_code == 403
        assert client.get(f"/api/v1/projects/{proj['id']}/timeline", headers=headers_other).status_code == 403
        assert client.get(f"/api/v1/projects/{proj['id']}/reconstruct", headers=headers_other).status_code == 403
        assert client.post(f"/api/v1/projects/{proj['id']}/restore/1", headers=headers_other).status_code == 403
    finally:
        client.app.dependency_overrides.pop(get_gemini_service, None)
