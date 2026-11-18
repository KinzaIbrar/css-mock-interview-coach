"""Process-wide access to the configured LLM provider.

Services/agents call `runtime.get_provider()` (via the module, so tests can monkeypatch it). It returns
None when no API key is configured, which switches the application into its clearly labelled development
fallback.
"""

from app.agents.gemini_provider import GeminiProvider, GeminiProviderPool
from app.agents.llm_provider import LLMProvider
from app.core.config import settings

_provider: GeminiProvider | GeminiProviderPool | None = None
_provider_fingerprint: tuple | None = None  # (keys tuple, model) the cached provider(s) were built from


def _build_provider(api_key: str) -> GeminiProvider:
    return GeminiProvider(
        api_key,
        settings.gemini_model,
        timeout_seconds=settings.gemini_timeout_seconds,
        max_retries=settings.gemini_max_retries,
        retry_delay_seconds=settings.gemini_retry_delay_seconds,
        budget_seconds=settings.gemini_budget_seconds,
        cooldown_seconds=settings.gemini_cooldown_seconds,
        quota_cooldown_cap_seconds=settings.gemini_quota_cooldown_cap_seconds,
    )


def get_provider() -> LLMProvider | None:
    """The single construction point for the configured Gemini provider(s).

    Zero keys -> None (unconfigured/dev-fallback, unchanged). One key -> a plain `GeminiProvider`,
    behaviorally identical to before multi-key support existed. Two or more keys -> a
    `GeminiProviderPool` that falls back across them, implementing the same `LLMProvider` protocol, so
    no caller needs to know how many keys are configured.
    """
    global _provider, _provider_fingerprint
    keys = settings.gemini_api_key_list
    if not keys:
        _provider = None
        _provider_fingerprint = None
        return None
    fingerprint = (tuple(keys), settings.gemini_model)
    if _provider is None or _provider_fingerprint != fingerprint:
        providers = [_build_provider(k) for k in keys]
        _provider = providers[0] if len(providers) == 1 else GeminiProviderPool(providers)
        _provider_fingerprint = fingerprint
    return _provider
