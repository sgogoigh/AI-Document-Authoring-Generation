from fastapi import APIRouter

from app.api.v1 import auth, export, generation, health, monitoring, projects

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(projects.router)
api_router.include_router(generation.router)
api_router.include_router(monitoring.router)
api_router.include_router(export.router)
