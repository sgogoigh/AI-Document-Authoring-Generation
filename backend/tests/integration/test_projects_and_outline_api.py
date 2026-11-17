from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.audit import AuditEventLog, ProjectSnapshot


def _register_and_headers(client: TestClient, email: str, name: str = "Test User") -> dict[str, str]:
    res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": name, "password": "Password123!"},
    )
    assert res.status_code == 201
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_project_crud_and_ownership_isolation(client: TestClient):
    headers_a = _register_and_headers(client, "owner_a@example.com", "Owner A")
    headers_b = _register_and_headers(client, "owner_b@example.com", "Owner B")

    # Create .docx project
    create_docx = client.post(
        "/api/v1/projects",
        headers=headers_a,
        json={
            "title": "EV Industry Report 2025",
            "doc_type": "docx",
            "main_topic": "A market analysis of the EV industry in 2025",
            "sections": [
                {"title": "Executive Summary"},
                {"title": "Supply Chain Dynamics"},
            ],
        },
    )
    assert create_docx.status_code == 201
    docx_proj = create_docx.json()
    assert docx_proj["status"] == "configured"
    assert len(docx_proj["sections"]) == 2
    assert docx_proj["sections"][0]["section_kind"] == "section"

    # Create .pptx project
    create_pptx = client.post(
        "/api/v1/projects",
        headers=headers_a,
        json={
            "title": "Q4 Board Pitch",
            "doc_type": "pptx",
            "main_topic": "AI Transformation Strategy",
            "sections": [{"title": "Vision"}, {"title": "Roadmap"}, {"title": "ROI"}],
        },
    )
    assert create_pptx.status_code == 201
    pptx_proj = create_pptx.json()
    assert pptx_proj["sections"][0]["section_kind"] == "slide"

    # Filter list by doc_type & search
    list_pptx = client.get("/api/v1/projects", headers=headers_a, params={"doc_type": "pptx"})
    assert list_pptx.status_code == 200
    assert len(list_pptx.json()) == 1
    assert list_pptx.json()[0]["id"] == pptx_proj["id"]

    search_ev = client.get("/api/v1/projects", headers=headers_a, params={"search": "EV industry"})
    assert len(search_ev.json()) == 1

    # User B cannot see or mutate User A's project
    assert client.get("/api/v1/projects", headers=headers_b).json() == []
    assert client.get(f"/api/v1/projects/{docx_proj['id']}", headers=headers_b).status_code == 403
    assert (
        client.patch(
            f"/api/v1/projects/{docx_proj['id']}",
            headers=headers_b,
            json={"title": "Hijacked"},
        ).status_code
        == 403
    )
    assert client.delete(f"/api/v1/projects/{docx_proj['id']}", headers=headers_b).status_code == 403

    # Update & soft-delete by owner A
    patch_res = client.patch(
        f"/api/v1/projects/{docx_proj['id']}",
        headers=headers_a,
        json={"title": "EV Industry Report 2025 (Final)"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "EV Industry Report 2025 (Final)"
    assert patch_res.json()["current_version"] == 2

    del_res = client.delete(f"/api/v1/projects/{pptx_proj['id']}", headers=headers_a)
    assert del_res.status_code == 204
    assert client.get(f"/api/v1/projects/{pptx_proj['id']}", headers=headers_a).status_code == 404


def test_outline_add_remove_reorder_and_snapshot_capture(client: TestClient, db_session):
    headers = _register_and_headers(client, "outline@example.com")
    res = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "title": "Cloud Migration Blueprint",
            "doc_type": "docx",
            "main_topic": "Enterprise cloud migration",
            "sections": [
                {"title": "Introduction"},
                {"title": "Legacy Audit"},
                {"title": "Target Architecture"},
            ],
        },
    )
    proj = res.json()
    sec_intro = proj["sections"][0]["id"]
    sec_arch = proj["sections"][2]["id"]

    # Reorder (Target Architecture first, Introduction second), remove Legacy Audit, add Cost Plan
    outline_res = client.put(
        f"/api/v1/projects/{proj['id']}/outline",
        headers=headers,
        json={
            "sections": [
                {"id": sec_arch, "title": "Target Cloud Architecture"},
                {"id": sec_intro, "title": "Introduction"},
                {"title": "Cost & Risk Plan"},
            ],
            "ai_outline_suggested": True,
        },
    )
    assert outline_res.status_code == 200
    updated = outline_res.json()
    assert updated["current_version"] == 2
    assert updated["ai_outline_suggested"] is True
    assert [s["title"] for s in updated["sections"]] == [
        "Target Cloud Architecture",
        "Introduction",
        "Cost & Risk Plan",
    ]
    assert updated["sections"][0]["id"] == sec_arch
    assert updated["sections"][1]["id"] == sec_intro
    assert [s["order_index"] for s in updated["sections"]] == [0, 1, 2]

    snapshots = db_session.scalars(
        select(ProjectSnapshot).where(ProjectSnapshot.project_id == proj["id"])
    ).all()
    assert len(snapshots) == 2

    audit_events = db_session.scalars(
        select(AuditEventLog).where(AuditEventLog.project_id == proj["id"])
    ).all()
    assert {e.event_type for e in audit_events} == {"PROJECT_CREATE", "OUTLINE_CONFIGURE"}
