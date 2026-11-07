from fastapi import APIRouter

from app.agents import runtime
from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "environment": settings.app_env,
        "ai_mode": "gemini" if settings.ai_configured else "development (no GEMINI_API_KEY; AI features limited)",
        # Whether Gemini can be used RIGHT NOW (configured is not the same as available): reason is e.g.
        # "quota_exhausted" / "rate_limited" / "timeout"; null when no key is configured. Makes no call to Google.
        "ai_availability": _availability(),
    }


def _availability() -> dict | None:
    provider = runtime.get_provider()
    status = getattr(provider, "status", None)
    return status() if callable(status) else None
