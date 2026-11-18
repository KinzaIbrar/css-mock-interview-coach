"""Task 17 -- targeted tests for multi-key Gemini support: config parsing, GeminiProviderPool fallback
behavior, runtime.get_provider() construction, health/status, and secret redaction.

Pool-level tests use lightweight fake inner providers (not GeminiProvider + FakeClient) deliberately:
GeminiProvider's own 429/timeout/cooldown classification is already tested elsewhere
(test_gemini_provider.py, test_gemini_rate_limits.py, test_quota_flow.py) -- this file tests only what
the pool itself adds (choosing which provider to call, when to fall through, which error to surface),
per the task's instruction not to duplicate that existing implementation/tests.
"""

import pytest

from app.agents.errors import (
    LLMError,
    LLMInvalidOutput,
    LLMQuotaExceeded,
    LLMRateLimited,
    LLMRequestError,
    LLMTransientError,
    LLMUnavailable,
)
from app.agents import runtime
from app.agents.gemini_provider import GeminiProviderPool
from app.core.config import Settings

RESULT = object()  # sentinel: the pool must return exactly what the winning provider returned

# conftest.py's autouse `no_real_llm` fixture monkeypatches runtime.get_provider to `lambda: None` for
# every test (hermetic by default). Captured here, at import time, before that happens, so the runtime-
# construction tests below can restore the real implementation just for themselves.
_REAL_GET_PROVIDER = runtime.get_provider


class FakeInnerProvider:
    """Stand-in for a GeminiProvider -- raises a scripted error or returns RESULT, nothing more."""

    def __init__(self, *, model="gemini-3.8-flash", raises: Exception | None = None, available=True, reason=None, retry_after=None):
        self.model = model
        self._raises = raises
        self._available = available
        self._reason = reason
        self._retry_after = retry_after
        self.calls = 0

    def generate_json(self, *, system, prompt, schema):
        self.calls += 1
        if self._raises:
            raise self._raises
        return RESULT

    def status(self):
        return {"available": self._available, "reason": self._reason, "retry_after_seconds": self._retry_after}


# ===================================================================== 1-5: config parsing (merged)
def test_single_key_backward_compatibility():
    s = Settings(gemini_api_key="only-key", gemini_api_keys="")
    assert s.gemini_api_key_list == ["only-key"]
    assert s.ai_configured is True
    assert s.ai_key_count == 1


def test_multiple_key_parsing():
    s = Settings(gemini_api_key="k1", gemini_api_keys="k2,k3,k4")
    assert s.gemini_api_key_list == ["k1", "k2", "k3", "k4"]
    assert s.ai_key_count == 4


def test_whitespace_is_trimmed():
    s = Settings(gemini_api_key="  k1  ", gemini_api_keys=" k2 , k3,  k4  ")
    assert s.gemini_api_key_list == ["k1", "k2", "k3", "k4"]


def test_duplicate_keys_removed():
    s = Settings(gemini_api_key="k1", gemini_api_keys="k2,k1,k2,k3")
    assert s.gemini_api_key_list == ["k1", "k2", "k3"]


def test_configuration_order_preserved():
    s = Settings(gemini_api_key="z", gemini_api_keys="a,m,b")
    assert s.gemini_api_key_list == ["z", "a", "m", "b"]  # singular first, then plural in listed order


def test_empty_configuration():
    s = Settings(gemini_api_key="", gemini_api_keys="")
    assert s.gemini_api_key_list == []
    assert s.ai_configured is False
    assert s.ai_key_count == 0


def test_blank_entries_in_plural_list_ignored():
    s = Settings(gemini_api_key="k1", gemini_api_keys="k2,,  ,k3")
    assert s.gemini_api_key_list == ["k1", "k2", "k3"]


# ===================================================================== 6-9: pool fallback
def test_fallback_after_daily_quota_exhaustion():
    p0 = FakeInnerProvider(raises=LLMQuotaExceeded("quota used up", "quota_exhausted"))
    p1 = FakeInnerProvider()
    pool = GeminiProviderPool([p0, p1])
    assert pool.generate_json(system="s", prompt="p", schema=object) is RESULT
    assert p0.calls == 1 and p1.calls == 1
    assert pool.last_success_index == 1
    assert pool.model == p1.model


def test_fallback_after_rate_limiting():
    p0 = FakeInnerProvider(raises=LLMRateLimited("rate limited", "rate_limited"))
    p1 = FakeInnerProvider()
    pool = GeminiProviderPool([p0, p1])
    assert pool.generate_json(system="s", prompt="p", schema=object) is RESULT
    assert pool.last_success_index == 1


def test_fallback_after_transient_failure():
    p0 = FakeInnerProvider(raises=LLMTransientError("timed out", "transient_error"))
    p1 = FakeInnerProvider()
    pool = GeminiProviderPool([p0, p1])
    assert pool.generate_json(system="s", prompt="p", schema=object) is RESULT
    assert pool.last_success_index == 1


def test_fallback_after_provider_unavailable_cooldown():
    p0 = FakeInnerProvider(raises=LLMUnavailable("cooling down", "cooldown"))
    p1 = FakeInnerProvider()
    pool = GeminiProviderPool([p0, p1])
    assert pool.generate_json(system="s", prompt="p", schema=object) is RESULT
    assert pool.last_success_index == 1


def test_fallback_after_rejected_key():
    """A bad/revoked key (LLMRequestError) on one provider must not block a working one."""
    p0 = FakeInnerProvider(raises=LLMRequestError("Gemini rejected the request (status 403)", "http_403"))
    p1 = FakeInnerProvider()
    pool = GeminiProviderPool([p0, p1])
    assert pool.generate_json(system="s", prompt="p", schema=object) is RESULT
    assert pool.last_success_index == 1


def test_third_provider_used_when_first_two_fail():
    p0 = FakeInnerProvider(raises=LLMQuotaExceeded())
    p1 = FakeInnerProvider(raises=LLMTransientError())
    p2 = FakeInnerProvider()
    pool = GeminiProviderPool([p0, p1, p2])
    assert pool.generate_json(system="s", prompt="p", schema=object) is RESULT
    assert p0.calls == 1 and p1.calls == 1 and p2.calls == 1
    assert pool.last_success_index == 2


# ===================================================================== 10-11: exhaustion + error priority
def test_all_providers_exhausted_raises_without_infinite_loop():
    p0 = FakeInnerProvider(raises=LLMQuotaExceeded())
    p1 = FakeInnerProvider(raises=LLMTransientError())
    pool = GeminiProviderPool([p0, p1])
    with pytest.raises(LLMError):
        pool.generate_json(system="s", prompt="p", schema=object)
    assert p0.calls == 1 and p1.calls == 1  # each tried exactly once -- bounded, not infinite


def test_most_informative_error_preserved_request_error_wins():
    """A rejected key (LLMRequestError, priority 3) is more actionable than a generic cooldown
    (LLMUnavailable, priority 0) -- the pool should surface the former when all providers fail."""
    p0 = FakeInnerProvider(raises=LLMUnavailable("cooldown", "cooldown"))
    p1 = FakeInnerProvider(raises=LLMRequestError("bad key", "http_403"))
    pool = GeminiProviderPool([p0, p1])
    with pytest.raises(LLMRequestError):
        pool.generate_json(system="s", prompt="p", schema=object)


def test_most_informative_error_quota_over_transient():
    p0 = FakeInnerProvider(raises=LLMTransientError("timeout", "transient_error"))
    p1 = FakeInnerProvider(raises=LLMQuotaExceeded("quota", "quota_exhausted"))
    pool = GeminiProviderPool([p0, p1])
    with pytest.raises(LLMQuotaExceeded):
        pool.generate_json(system="s", prompt="p", schema=object)


def test_invalid_output_does_not_fall_through():
    """The provider DID respond, just with bad content -- another key is no more likely to fix a
    schema mismatch, so the pool must not mask it by trying the next provider."""
    p0 = FakeInnerProvider(raises=LLMInvalidOutput("bad json"))
    p1 = FakeInnerProvider()
    pool = GeminiProviderPool([p0, p1])
    with pytest.raises(LLMInvalidOutput):
        pool.generate_json(system="s", prompt="p", schema=object)
    assert p1.calls == 0  # never even tried


def test_empty_pool_rejected():
    with pytest.raises(ValueError):
        GeminiProviderPool([])


# ===================================================================== 12: runtime construction
@pytest.fixture(autouse=True)
def _reset_runtime_cache():
    from app.agents import runtime

    runtime._provider = None
    runtime._provider_fingerprint = None
    yield
    runtime._provider = None
    runtime._provider_fingerprint = None


def test_runtime_zero_keys_returns_none(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(runtime, "get_provider", _REAL_GET_PROVIDER)
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_keys", "")
    assert runtime.get_provider() is None


def test_runtime_one_key_returns_plain_provider(monkeypatch):
    from app.agents.gemini_provider import GeminiProvider
    from app.core.config import settings

    monkeypatch.setattr(runtime, "get_provider", _REAL_GET_PROVIDER)
    monkeypatch.setattr(settings, "gemini_api_key", "solo-key")
    monkeypatch.setattr(settings, "gemini_api_keys", "")
    provider = runtime.get_provider()
    assert isinstance(provider, GeminiProvider)
    assert not isinstance(provider, GeminiProviderPool)


def test_runtime_multiple_keys_returns_pool(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(runtime, "get_provider", _REAL_GET_PROVIDER)
    monkeypatch.setattr(settings, "gemini_api_key", "key1")
    monkeypatch.setattr(settings, "gemini_api_keys", "key2,key3")
    provider = runtime.get_provider()
    assert isinstance(provider, GeminiProviderPool)
    assert len(provider._providers) == 3


def test_runtime_caches_and_rebuilds_on_key_change(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(runtime, "get_provider", _REAL_GET_PROVIDER)
    monkeypatch.setattr(settings, "gemini_api_key", "key1")
    monkeypatch.setattr(settings, "gemini_api_keys", "")
    first = runtime.get_provider()
    second = runtime.get_provider()
    assert first is second  # cached, not rebuilt every call

    monkeypatch.setattr(settings, "gemini_api_keys", "key2")
    third = runtime.get_provider()
    assert third is not first  # key list changed -> rebuilt
    assert isinstance(third, GeminiProviderPool)


# ===================================================================== 13: health/status
def test_status_available_if_any_provider_up():
    p0 = FakeInnerProvider(available=False, reason="quota_exhausted", retry_after=500)
    p1 = FakeInnerProvider(available=True)
    pool = GeminiProviderPool([p0, p1])
    st = pool.status()
    assert st["available"] is True
    assert st["reason"] is None


def test_status_unavailable_reports_soonest_retry():
    p0 = FakeInnerProvider(available=False, reason="quota_exhausted", retry_after=900)
    p1 = FakeInnerProvider(available=False, reason="rate_limited", retry_after=30)
    pool = GeminiProviderPool([p0, p1])
    st = pool.status()
    assert st["available"] is False
    assert st["retry_after_seconds"] == 30
    assert st["reason"] == "rate_limited"
    assert st["provider_count"] == 2


# ===================================================================== 14: secret redaction
def test_pool_never_stores_or_logs_raw_keys():
    p0 = FakeInnerProvider(raises=LLMRequestError("Gemini rejected the request (status 403): [REDACTED]", "http_403"))
    p1 = FakeInnerProvider()
    pool = GeminiProviderPool([p0, p1])
    pool.generate_json(system="s", prompt="p", schema=object)
    # The pool holds provider objects only -- never a raw key string anywhere in its own __dict__.
    for value in vars(pool).values():
        assert "AIza" not in str(value) and "SECRET" not in str(value).upper()


def test_health_endpoint_status_shape_unchanged(client):
    """registry.py / health.py read .get('available')/.get('reason') off whatever get_provider()
    returns -- confirm the pool's status() dict satisfies that contract without a live key."""
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert "ai_availability" in body
    assert "AIza" not in str(body)  # no Google API-key-shaped material ever in the response
