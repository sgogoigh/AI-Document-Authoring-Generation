from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Application settings loaded from backend/.env or root .env."""

    model_config = SettingsConfigDict(
        env_file=(str(BACKEND_DIR / ".env"), str(REPO_ROOT_DIR / ".env")),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "AI Document Authoring & Generation API"
    environment: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    database_url: str = f"sqlite:///{(BACKEND_DIR / 'storage' / 'app.db').as_posix()}"

    jwt_secret_key: str = "dev-insecure-secret-change-in-production-64-bytes-minimum-key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    gemini_api_key: str = ""
    gemini_text_model: str = "gemini-2.5-flash"
    gemini_image_model: str = "gemini-2.5-flash-image"
    enable_image_generation: bool = True

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:3000/auth/google/callback"

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    storage_dir: str = str(BACKEND_DIR / "storage")

    @field_validator("storage_dir", mode="before")
    @classmethod
    def resolve_storage_dir(cls, value: str) -> str:
        path = Path(value)
        if not path.is_absolute():
            path = (BACKEND_DIR / path).resolve()
        return str(path)

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def assets_dir(self) -> Path:
        path = Path(self.storage_dir) / "assets"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def exports_dir(self) -> Path:
        path = Path(self.storage_dir) / "exports"
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    settings = Settings()
    Path(settings.storage_dir).mkdir(parents=True, exist_ok=True)
    return settings
