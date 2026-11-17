from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings


def test_settings_loads_defaults_and_resolves_paths(tmp_path: Path):
    settings = Settings(storage_dir=str(tmp_path / "custom_storage"))
    assert settings.api_v1_prefix == "/api/v1"
    assert Path(settings.storage_dir).is_absolute()
    assert settings.assets_dir.exists()
    assert settings.exports_dir.exists()
    assert "http://localhost:3000" in settings.cors_origin_list


def test_get_settings_detects_root_env_gemini_key():
    get_settings.cache_clear()
    settings = get_settings()
    assert isinstance(settings.gemini_api_key, str)
    assert len(settings.gemini_api_key) > 0


def test_health_endpoint(client: TestClient):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] == "connected"
    assert "gemini_configured" in payload
    assert "google_oauth_configured" in payload
