"""Gemini implementation of `LLMProvider` (google-genai SDK).

Failure policy: every attempt has a timeout; transient errors (timeouts, connection errors, HTTP 408/429/5xx)
are retried a limited number of times within an overall time budget; non-transient errors (auth, unknown
model, ...) fail immediately. After retries are exhausted the provider enters a short cooldown during which
calls fail fast, so an outage does not make every request wait. The API key is never logged or included
in error text.
"""

import logging
import re
import time
from typing import Any, Callable

from pydantic import ValidationError

from app.agents.errors import LLMInvalidOutput, LLMRequestError, LLMTransientError, LLMUnavailable
from app.agents.llm_provider import T

logger = logging.getLogger("app.llm")

_TRANSIENT_NAMES = ("timeout", "connect", "network", "protocol", "readerror")
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


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
        self._temperature = temperature
        self._client = client
        self._sleep = sleep
        self._clock = clock
        self._cooldown_until = 0.0

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

    # -- public API ----------------------------------------------------------------------------
    def generate_json(self, *, system: str, prompt: str, schema: type[T]) -> T:
        started = self._clock()
        if started < self._cooldown_until:
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
                if not self._is_transient(exc):
                    msg = self._redact(str(getattr(exc, "message", None) or exc))
                    logger.warning("Gemini request failed (non-retryable, status=%s)", code)
                    raise LLMRequestError(
                        f"Gemini rejected the request (status {code}): {msg}", f"http_{code or 'error'}"
                    ) from None
                over_budget = (self._clock() - started) + self._delay + self._timeout > self._budget
                if attempt >= self._max_retries or over_budget:
                    self._cooldown_until = self._clock() + self._cooldown
                    label = f"status {code}" if code else type(exc).__name__
                    logger.warning("Gemini unavailable after %d attempt(s) (%s)", attempt + 1, label)
                    raise LLMTransientError(
                        f"Gemini did not respond successfully after {attempt + 1} attempt(s) ({label})",
                        "timeout" if (code in (408, 504) or code is None) else f"http_{code}",
                    ) from None
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
