"""Errors raised by the LLM layer. `code` is a short, safe identifier (never contains secrets)."""


class LLMError(Exception):
    code = "llm_error"

    def __init__(self, message: str = "", code: str | None = None):
        super().__init__(message or self.code)
        if code:
            self.code = code


class LLMUnavailable(LLMError):
    """No provider configured, or the provider is in a short cooldown after repeated failures."""

    code = "unavailable"


class LLMTransientError(LLMError):
    """Timeouts / 5xx / rate limits that persisted through the allowed retries."""

    code = "transient_error"


class LLMRequestError(LLMError):
    """A non-retryable error (bad key, forbidden, unknown model, ...)."""

    code = "request_error"


class LLMInvalidOutput(LLMError):
    """The model answered, but not with valid JSON in the requested shape."""

    code = "invalid_output"
