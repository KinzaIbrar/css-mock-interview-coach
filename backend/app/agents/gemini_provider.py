"""Gemini implementation of `LLMProvider` (google-genai SDK).

Failure policy
- Every attempt has a timeout.
- Transient errors (timeouts, connection errors, HTTP 408/5xx) are retried a limited number of times within an
  overall time budget, then the provider enters a short cooldown during which calls fail fast.
- HTTP 429 is NOT treated like a flaky network: Google says why and for how long.
    * Daily quota exhausted (e.g. free tier "...PerDay..." limit): never retried. The provider stays in cooldown
      for the retry delay Google gave (capped), and every call in that window fails fast with the real cause.
    * Per-minute rate limit: waits the delay Google asked for, once per retry, only if it fits in the time budget;
      otherwise fails fast and cools down for that delay.
- Non-transient errors (auth, unknown model, ...) fail immediately.
The API key is never logged or included in error text.
"""

import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import ValidationError

from app.agents.errors import (
    LLMError,
    LLMInvalidOutput,
    LLMQuotaExceeded,
    LLMRateLimited,
    LLMRequestError,
    LLMTransientError,
    LLMUnavailable,
)
from app.agents.llm_provider import T

logger = logging.getLogger("app.llm")

_TRANSIENT_NAMES = ("timeout", "connect", "network", "protocol", "readerror")
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_SECONDS = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*s?\s*$")


@dataclass(frozen=True)
class RateLimitInfo:
    """What Google told us about a 429."""

    daily_quota: bool  # a per-day quota is exhausted: waiting minutes will not help
    retry_after: float | None  # seconds, from RetryInfo.retryDelay (None if absent)


def parse_rate_limit(exc: Exception) -> RateLimitInfo:
    """Read the structured details of a 429 (QuotaFailure.quotaId, RetryInfo.retryDelay). Tolerates any shape."""
    daily, retry_after = False, None

    def walk(node: Any) -> None:
        nonlocal daily, retry_after
        if isinstance(node, dict):
            kind = str(node.get("@type", ""))
            if "QuotaFailure" in kind:
                for v in node.get("violations", []) or []:
                    if isinstance(v, dict) and "perday" in str(v.get("quotaId", "")).replace("_", "").lower():
                        daily = True
            elif "RetryInfo" in kind:
                m = _SECONDS.match(str(node.get("retryDelay", "")))
                if m:
                    retry_after = float(m.group(1))
            for v in node.values():
                if isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(getattr(exc, "details", None))
    return RateLimitInfo(daily, retry_after)


class GeminiProvider:
    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        timeout_seconds: float = 20.0,
        max_retries: int = 2,
        retry_delay_seconds: float = 2.0,
        budget_seconds: float = 50.0,
        cooldown_seconds: float = 30.0,
        quota_cooldown_cap_seconds: float = 900.0,
        temperature: float = 0.2,
        client: Any = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.model = model
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._delay = retry_delay_seconds
        self._budget = budget_seconds
        self._cooldown = cooldown_seconds
        self._quota_cap = quota_cooldown_cap_seconds
        self._temperature = temperature
        self._client = client
        self._sleep = sleep
        self._clock = clock
        self._cooldown_until = 0.0
        self._cooldown_error: tuple[type[LLMError], str, str] | None = None  # (class, message, code) of the cause

    # -- helpers -------------------------------------------------------------------------------
    def _get_client(self):
        if self._client is None:
            from google import genai
            from google.genai import types

            self._client = genai.Client(
                api_key=self._api_key,
                http_options=types.HttpOptions(
                    timeout=int(self._timeout * 1000),
                    retry_options=types.HttpRetryOptions(attempts=1),  # we own the retry policy
                ),
            )
        return self._client

    def _redact(self, text: str) -> str:
        if self._api_key:
            text = text.replace(self._api_key, "[REDACTED]")
        return text.splitlines()[0][:200] if text else ""

    @staticmethod
    def _status_code(exc: Exception) -> int | None:
        code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        return code if isinstance(code, int) else None

    def _is_transient(self, exc: Exception) -> bool:
        code = self._status_code(exc)
        if code is not None:
            return code in (408, 429) or code >= 500
        names = " ".join(c.__name__.lower() for c in type(exc).__mro__)
        return isinstance(exc, (TimeoutError, ConnectionError)) or any(n in names for n in _TRANSIENT_NAMES)

    def _config(self, system: str, schema: type[T]):
        from google.genai import types

        return types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=self._temperature,
        )

    def _open_cooldown(self, seconds: float, error: tuple[type[LLMError], str, str] | None) -> None:
        self._cooldown_until = self._clock() + seconds
        self._cooldown_error = error

    def status(self) -> dict:
        """Current availability, for the health endpoint. Does not call Google."""
        remaining = self._cooldown_until - self._clock()
        if remaining > 0:
            reason = self._cooldown_error[2] if self._cooldown_error else "cooldown"
            return {"available": False, "reason": reason, "retry_after_seconds": int(remaining) + 1}
        return {"available": True, "reason": None, "retry_after_seconds": None}

    # -- public API ----------------------------------------------------------------------------
    def generate_json(self, *, system: str, prompt: str, schema: type[T]) -> T:
        started = self._clock()
        if started < self._cooldown_until:
            # Fail fast, and report the REAL cause (e.g. quota exhausted), not a generic "cooldown".
            if self._cooldown_error:
                cls, message, code = self._cooldown_error
                raise cls(message, code)
            raise LLMUnavailable("Gemini is temporarily unavailable (cooling down after repeated failures)", "cooldown")

        attempt = 0
        while True:
            try:
                response = self._get_client().models.generate_content(
                    model=self.model, contents=prompt, config=self._config(system, schema)
                )
                break
            except Exception as exc:  # noqa: BLE001 - classified below
                code = self._status_code(exc)
                wait = self._delay * (attempt + 1)

                if code == 429:
                    info = parse_rate_limit(exc)
                    if info.daily_quota:
                        # Waiting minutes cannot help: stop immediately and stay quiet until Google's reset time.
                        cooldown = min(info.retry_after or self._quota_cap, self._quota_cap)
                        error = (LLMQuotaExceeded, "The Gemini API quota for this key is exhausted (daily limit)", "quota_exhausted")
                        self._open_cooldown(cooldown, error)
                        logger.warning(
                            "Gemini daily quota exhausted (model=%s); no retries; calls paused for %ds (Google retry delay: %s)",
                            self.model, int(cooldown), f"{int(info.retry_after)}s" if info.retry_after else "n/a",
                        )
                        raise LLMQuotaExceeded(error[1], error[2]) from None
                    # Per-minute (or unspecified) rate limit: honour Google's delay instead of a blind fixed one.
                    if info.retry_after is not None:
                        wait = info.retry_after
                    fits = (self._clock() - started) + wait + self._timeout <= self._budget
                    if attempt >= self._max_retries or not fits:
                        cooldown = info.retry_after if info.retry_after is not None else self._cooldown
                        cooldown = min(cooldown, self._quota_cap)
                        error = (LLMRateLimited, "Gemini is rate-limiting requests right now", "rate_limited")
                        self._open_cooldown(cooldown, error)
                        logger.warning("Gemini rate-limited (model=%s); pausing calls for %ds", self.model, int(cooldown))
                        raise LLMRateLimited(error[1], error[2]) from None
                    logger.info("Gemini 429 (rate limit); waiting %.0fs, retry %d/%d", wait, attempt + 1, self._max_retries)
                    attempt += 1
                    self._sleep(wait)
                    continue

                if not self._is_transient(exc):
                    msg = self._redact(str(getattr(exc, "message", None) or exc))
                    logger.warning("Gemini request failed (non-retryable, status=%s)", code)
                    raise LLMRequestError(
                        f"Gemini rejected the request (status {code}): {msg}", f"http_{code or 'error'}"
                    ) from None
                over_budget = (self._clock() - started) + self._delay + self._timeout > self._budget
                if attempt >= self._max_retries or over_budget:
                    label = f"status {code}" if code else type(exc).__name__
                    reason = "timeout" if (code in (408, 504) or code is None) else f"http_{code}"
                    message = f"Gemini did not respond successfully after {attempt + 1} attempt(s) ({label})"
                    # Generic cooldown: no request is made while it lasts, so later calls say "cooldown" (not "timeout").
                    self._open_cooldown(self._cooldown, None)
                    logger.warning("Gemini unavailable after %d attempt(s) (%s)", attempt + 1, label)
                    raise LLMTransientError(message, reason) from None
                attempt += 1
                logger.info("Gemini transient error (status=%s); retry %d/%d", code, attempt, self._max_retries)
                self._sleep(self._delay)

        text = (getattr(response, "text", None) or "").strip()
        if not text:
            raise LLMInvalidOutput("Gemini returned an empty response")
        try:
            return schema.model_validate_json(_FENCE.sub("", text))
        except ValidationError:
            raise LLMInvalidOutput("Gemini output did not match the required JSON structure") from None
