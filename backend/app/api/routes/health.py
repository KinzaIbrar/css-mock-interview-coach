from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "environment": settings.app_env,
        "ai_mode": "gemini" if settings.ai_configured else "development (no GEMINI_API_KEY; AI features limited)",
    }
