import json

import pytest
from google.genai import errors as genai_errors

from app.agents.errors import LLMInvalidOutput, LLMRequestError, LLMTransientError, LLMUnavailable
from app.agents.gemini_provider import GeminiProvider
from app.agents.schemas import EvaluationLLMOutput
from tests.fakes import Clock, FakeApiError, FakeClient, FakeResponse, eval_output

KEY = "SENTINEL-SECRET-KEY-0123456789"


def make(script, clock=None, **kw):
    clock = clock or Clock()
    client = FakeClient(script)
    opts = dict(timeout_seconds=10, max_retries=2, retry_delay_seconds=2, budget_seconds=100, cooldown_seconds=30)
    opts.update(kw)
    provider = GeminiProvider(KEY, "gemini-test", client=client, sleep=clock.sleep, clock=clock, **opts)
    return provider, client, clock


def ok_response(**kw):
    return FakeResponse(eval_output(**kw).model_dump_json())


def call(provider):
    return provider.generate_json(system="sys", prompt="hello", schema=EvaluationLLMOutput)


# ---- success ------------------------------------------------------------------------------------
def test_success_returns_validated_schema_and_uses_configured_model():
    provider, client, _ = make([ok_response(score=7)])
    out = call(provider)
    assert isinstance(out, EvaluationLLMOutput) and out.accuracy == 7
    sent = client.calls[0]
    assert sent["model"] == "gemini-test" and sent["contents"] == "hello"
    assert sent["config"].system_instruction == "sys"
    assert sent["config"].response_mime_type == "application/json"
    assert sent["config"].response_schema is EvaluationLLMOutput


def test_markdown_fenced_json_is_accepted():
    fenced = "```json\n" + eval_output().model_dump_json() + "\n```"
    provider, _, _ = make([FakeResponse(fenced)])
    assert call(provider).relevance == 8


def test_response_schema_is_accepted_by_the_real_sdk_types():
    """Guards against shapes the google-genai config model would reject."""
    provider, _, _ = make([])
    cfg = provider._config("system text", EvaluationLLMOutput)
    assert cfg.response_schema is EvaluationLLMOutput and cfg.temperature == 0.2


# ---- retries ------------------------------------------------------------------------------------
def test_transient_504_is_retried_then_succeeds():
    provider, client, clock = make([FakeApiError(504), ok_response()])
    assert call(provider).relevance == 8
    assert len(client.calls) == 2 and clock.sleeps == [2]


def test_retries_are_limited_to_max_retries():
    provider, client, clock = make([FakeApiError(503)] * 5)
    with pytest.raises(LLMTransientError) as exc:
        call(provider)
    assert len(client.calls) == 3  # first try + 2 retries, never more
    assert clock.sleeps == [2, 2]
    assert exc.value.code == "http_503"


@pytest.mark.parametrize("code", [429, 500, 502, 503, 504, 408])
def test_retryable_status_codes(code):
    provider, client, _ = make([FakeApiError(code), ok_response()])
    call(provider)
    assert len(client.calls) == 2


def test_timeout_exception_is_retried():
    provider, client, _ = make([TimeoutError("read timed out"), ok_response()])
    call(provider)
    assert len(client.calls) == 2


def test_connection_error_is_retried_and_reported_as_timeout_code():
    provider, client, _ = make([ConnectionError("reset")] * 5)
    with pytest.raises(LLMTransientError) as exc:
        call(provider)
    assert len(client.calls) == 3 and exc.value.code == "timeout"


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_client_errors_are_not_retried(code):
    provider, client, clock = make([FakeApiError(code), ok_response()])
    with pytest.raises(LLMRequestError) as exc:
        call(provider)
    assert len(client.calls) == 1 and clock.sleeps == [] and exc.value.code == f"http_{code}"


def test_unknown_exception_types_are_not_retried():
    provider, client, _ = make([ValueError("programming error"), ok_response()])
    with pytest.raises(LLMRequestError):
        call(provider)
    assert len(client.calls) == 1


def test_time_budget_stops_retrying_early():
    # Retry n is allowed only if elapsed + delay + timeout <= budget: 0+2+10=12 fits 13s, then 2+2+10=14 does not.
    provider, client, _ = make([FakeApiError(504)] * 5, budget_seconds=13)
    with pytest.raises(LLMTransientError):
        call(provider)
    assert len(client.calls) == 2  # one retry allowed by the budget, although max_retries is 2


def test_real_sdk_exception_classes_are_classified():
    server = genai_errors.ServerError(504, {"error": {"message": "Deadline expired", "status": "DEADLINE_EXCEEDED"}})
    client_err = genai_errors.ClientError(404, {"error": {"message": "model gone", "status": "NOT_FOUND"}})
    provider, client, _ = make([server, ok_response()])
    call(provider)
    assert len(client.calls) == 2  # ServerError(504) retried
    provider, client, _ = make([client_err, ok_response()])
    with pytest.raises(LLMRequestError):
        call(provider)
    assert len(client.calls) == 1  # ClientError(404) not retried


# ---- cooldown -----------------------------------------------------------------------------------
def test_cooldown_after_exhausted_retries_fails_fast_then_recovers():
    provider, client, clock = make([FakeApiError(504)] * 3 + [ok_response()])
    with pytest.raises(LLMTransientError):
        call(provider)
    used = len(client.calls)
    with pytest.raises(LLMUnavailable) as exc:
        call(provider)
    assert len(client.calls) == used and exc.value.code == "cooldown"  # no request was sent
    clock.now += 31
    assert call(provider).relevance == 8  # works again after the cooldown


def test_non_transient_errors_do_not_trigger_cooldown():
    provider, client, _ = make([FakeApiError(401), ok_response()])
    with pytest.raises(LLMRequestError):
        call(provider)
    assert call(provider).relevance == 8


# ---- invalid output -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    ["", "   ", "not json at all", "[]", json.dumps({"relevance": 5}), '{"relevance": "high"}'],
)
def test_invalid_or_incomplete_output_is_rejected(text):
    provider, _, _ = make([FakeResponse(text)])
    with pytest.raises(LLMInvalidOutput):
        call(provider)


def test_none_text_is_rejected():
    provider, _, _ = make([FakeResponse(None)])
    with pytest.raises(LLMInvalidOutput):
        call(provider)


# ---- secrets ------------------------------------------------------------------------------------
def test_api_key_is_never_included_in_errors_or_logs(caplog):
    caplog.set_level("DEBUG")
    provider, _, _ = make([FakeApiError(401, f"API key {KEY} is invalid")])
    with pytest.raises(LLMRequestError) as exc:
        call(provider)
    assert KEY not in str(exc.value) and "[REDACTED]" in str(exc.value)

    provider, _, _ = make([FakeApiError(503, f"upstream said {KEY}")] * 5)
    with pytest.raises(LLMTransientError) as exc:
        call(provider)
    assert KEY not in str(exc.value)
    assert KEY not in caplog.text


def test_exception_chain_does_not_carry_the_raw_error():
    provider, _, _ = make([FakeApiError(401, f"bad {KEY}")])
    with pytest.raises(LLMRequestError) as exc:
        call(provider)
    assert exc.value.__cause__ is None  # raised `from None`
