"""HTTP 429 from Gemini: daily quota vs per-minute rate limit, and what the app does about each.

Background (real, observed on this project): the free tier allows 20 requests/day/model. Google answers 429
immediately with QuotaFailure.quotaId '...PerDay...' and a RetryInfo.retryDelay of hours. Retrying within seconds
can never help, and the old code did exactly that."""

import pytest
from google.genai import errors as genai_errors

from app.agents import runtime
from app.agents.errors import LLMQuotaExceeded, LLMRateLimited, LLMTransientError, LLMUnavailable
from app.agents.evaluation_agent import EvaluationAgent
from app.agents.feedback_agent import FeedbackAgent
from app.agents.gemini_provider import GeminiProvider, parse_rate_limit
from app.agents.schemas import EvaluationLLMOutput
from app.models.question import Question
from tests.fakes import Clock, FakeApiError, FakeClient, FakeProvider, FakeResponse, eval_output
from tests.ratelimit_helpers import DAILY, PER_MINUTE, RateLimitError, quota_details

KEY = "SENTINEL-SECRET-KEY-0123456789"


def make(script, **kw):
    clock = Clock()
    client = FakeClient(script)
    opts = dict(timeout_seconds=10, max_retries=2, retry_delay_seconds=2, budget_seconds=100, cooldown_seconds=30, quota_cooldown_cap_seconds=900)
    opts.update(kw)
    return GeminiProvider(KEY, "gemini-test", client=client, sleep=clock.sleep, clock=clock, **opts), client, clock


def call(p):
    return p.generate_json(system="s", prompt="p", schema=EvaluationLLMOutput)


def ok():
    return FakeResponse(eval_output().model_dump_json())


# ---- reading Google's 429 details ---------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "details,daily,retry",
    [
        (quota_details(quota_id=DAILY, retry_delay="17244s"), True, 17244.0),
        (quota_details(quota_id=DAILY, retry_delay="17244.5s"), True, 17244.5),
        (quota_details(quota_id=PER_MINUTE, retry_delay="37s"), False, 37.0),
        (quota_details(quota_id=PER_MINUTE, retry_delay=None), False, None),
        (quota_details(quota_id="generate_requests_per_day_per_project", retry_delay="60s"), True, 60.0),
        (None, False, None),
        ({}, False, None),
        ("not a dict", False, None),
        ({"error": {"details": "garbage"}}, False, None),
        ({"error": {"details": [{"@type": "x.RetryInfo", "retryDelay": "soon"}]}}, False, None),
    ],
)
def test_parse_rate_limit(details, daily, retry):
    info = parse_rate_limit(RateLimitError(details))
    assert info.daily_quota is daily and info.retry_after == retry


def test_parse_works_on_the_real_sdk_exception_class():
    err = genai_errors.ClientError(429, quota_details(quota_id=DAILY, retry_delay="17244s"))
    info = parse_rate_limit(err)
    assert info.daily_quota is True and info.retry_after == 17244.0


# ---- daily quota: never retry, fail fast, real cause -------------------------------------------------------------------
def test_daily_quota_is_not_retried():
    p, client, clock = make([RateLimitError(quota_details(quota_id=DAILY)), ok()])
    with pytest.raises(LLMQuotaExceeded) as exc:
        call(p)
    assert exc.value.code == "quota_exhausted"
    assert len(client.calls) == 1 and clock.sleeps == []  # not a single retry, not a single sleep


def test_daily_quota_with_the_real_sdk_exception():
    p, client, _ = make([genai_errors.ClientError(429, quota_details(quota_id=DAILY)), ok()])
    with pytest.raises(LLMQuotaExceeded):
        call(p)
    assert len(client.calls) == 1


def test_later_calls_fail_fast_with_the_same_real_cause_and_send_nothing():
    p, client, _ = make([RateLimitError(quota_details(quota_id=DAILY)), ok()])
    with pytest.raises(LLMQuotaExceeded):
        call(p)
    for _ in range(3):
        with pytest.raises(LLMQuotaExceeded) as exc:  # not a generic "cooldown": the user is told the real reason
            call(p)
        assert exc.value.code == "quota_exhausted"
    assert len(client.calls) == 1


def test_cooldown_follows_googles_delay_but_is_capped_then_recovers():
    p, client, clock = make([RateLimitError(quota_details(quota_id=DAILY, retry_delay="17244s")), ok()], quota_cooldown_cap_seconds=900)
    with pytest.raises(LLMQuotaExceeded):
        call(p)
    clock.now += 899
    with pytest.raises(LLMQuotaExceeded):
        call(p)
    clock.now += 2  # past the 900 s cap: probe again (a 429 costs nothing, and the quota may have been raised)
    assert call(p).relevance == 8
    assert len(client.calls) == 2


def test_short_daily_delay_is_not_stretched_to_the_cap():
    p, client, clock = make([RateLimitError(quota_details(quota_id=DAILY, retry_delay="45s")), ok()])
    with pytest.raises(LLMQuotaExceeded):
        call(p)
    clock.now += 46
    assert call(p).relevance == 8


def test_status_reports_availability_for_the_health_endpoint():
    p, _, clock = make([RateLimitError(quota_details(quota_id=DAILY, retry_delay="600s")), ok()])
    assert p.status() == {"available": True, "reason": None, "retry_after_seconds": None}
    with pytest.raises(LLMQuotaExceeded):
        call(p)
    s = p.status()
    assert s["available"] is False and s["reason"] == "quota_exhausted" and 595 <= s["retry_after_seconds"] <= 601
    clock.now += 601
    assert p.status()["available"] is True


# ---- per-minute rate limit: wait as long as Google says, only if it fits -----------------------------------------------
def test_per_minute_limit_waits_the_delay_google_asked_for_not_a_blind_2_seconds():
    p, client, clock = make([RateLimitError(quota_details(quota_id=PER_MINUTE, retry_delay="7s")), ok()])
    assert call(p).relevance == 8
    assert clock.sleeps == [7.0] and len(client.calls) == 2


def test_delay_that_does_not_fit_the_budget_fails_fast_without_waiting():
    p, client, clock = make([RateLimitError(quota_details(quota_id=PER_MINUTE, retry_delay="120s")), ok()], budget_seconds=65)
    with pytest.raises(LLMRateLimited) as exc:
        call(p)
    assert exc.value.code == "rate_limited" and clock.sleeps == [] and len(client.calls) == 1
    assert p.status()["reason"] == "rate_limited"
    with pytest.raises(LLMRateLimited):  # and it stays quiet for Google's delay
        call(p)
    assert len(client.calls) == 1


def test_429_without_details_is_still_bounded():
    p, client, clock = make([RateLimitError(None)] * 5)
    with pytest.raises(LLMRateLimited):
        call(p)
    assert len(client.calls) == 3  # first try + max 2 retries, never more
    assert clock.sleeps == [2, 4]


def test_per_minute_cooldown_uses_googles_delay():
    p, client, clock = make([RateLimitError(quota_details(quota_id=PER_MINUTE, retry_delay="90s")), ok()], budget_seconds=60)
    with pytest.raises(LLMRateLimited):
        call(p)
    clock.now += 89
    with pytest.raises(LLMRateLimited):
        call(p)
    clock.now += 2
    assert call(p).relevance == 8


def test_server_errors_keep_the_generic_cooldown_and_do_not_claim_a_new_timeout():
    p, client, _ = make([FakeApiError(503)] * 5)
    with pytest.raises(LLMTransientError):
        call(p)
    with pytest.raises(LLMUnavailable) as exc:
        call(p)
    assert exc.value.code == "cooldown"


def test_the_key_never_appears_in_429_errors_or_status():
    p, _, _ = make([RateLimitError(quota_details(quota_id=DAILY), message=f"quota exceeded for key {KEY}")])
    with pytest.raises(LLMQuotaExceeded) as exc:
        call(p)
    assert KEY not in str(exc.value) and KEY not in str(p.status())


# ---- the agents turn these into labelled fallbacks with the real reason -----------------------------------------------------
@pytest.fixture()
def question(db_session):
    with db_session() as db:
        yield db.query(Question).filter_by(source_id="pa-002").one()


@pytest.mark.parametrize(
    "error,reason",
    [(LLMQuotaExceeded("x", "quota_exhausted"), "quota_exhausted"), (LLMRateLimited("x", "rate_limited"), "rate_limited")],
)
def test_evaluation_and_feedback_fall_back_with_the_real_reason(question, monkeypatch, error, reason):
    monkeypatch.setattr(runtime, "get_provider", lambda: FakeProvider([error, error]))
    ev = EvaluationAgent().evaluate(question, "The Objectives Resolution declared sovereignty belongs to Allah.")
    assert ev.source == "dev_heuristic" and ev.is_ai_generated is False and ev.fallback_reason == reason
    results = [{"n": 1, "topic": "t", "question": "q", "skipped": False, "answer": "a", "overall": 1.0, "weaknesses": [], "missing_info": []}]
    fb = FeedbackAgent().generate(
        subject="x", overall_score=1.0, results=results,
        fallback=lambda: {"summary": "s", "improvements": ["i"], "revision_topics": []},
    )
    assert fb.source == "dev_rules" and fb.fallback_reason == reason
