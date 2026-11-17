from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import check_db_health, get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(db: Session = Depends(get_db)) -> dict:
    """Verify API availability, database connectivity, and configuration readiness."""
    settings = get_settings()
    db_ok = check_db_health(db)
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "error",
        "environment": settings.environment,
        "gemini_configured": bool(settings.gemini_api_key),
        "google_oauth_configured": bool(settings.google_client_id),
    }
