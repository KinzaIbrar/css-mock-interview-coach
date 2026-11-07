"""Process-wide access to the configured LLM provider.

Services/agents call `runtime.get_provider()` (via the module, so tests can monkeypatch it). It returns
None when no API key is configured, which switches the application into its clearly labelled development
fallback.
"""

from app.agents.gemini_provider import GeminiProvider
from app.agents.llm_provider import LLMProvider
from app.core.config import settings

_provider: GeminiProvider | None = None


def get_provider() -> LLMProvider | None:
    global _provider
    if not settings.ai_configured:
        return None
    if _provider is None or _provider.model != settings.gemini_model:
        _provider = GeminiProvider(
            settings.gemini_api_key,
            settings.gemini_model,
            timeout_seconds=settings.gemini_timeout_seconds,
            max_retries=settings.gemini_max_retries,
            retry_delay_seconds=settings.gemini_retry_delay_seconds,
            budget_seconds=settings.gemini_budget_seconds,
            cooldown_seconds=settings.gemini_cooldown_seconds,
        )
    return _provider
