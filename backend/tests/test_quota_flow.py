"""Gemini 429 through the whole stack, using the REAL GeminiProvider with a scripted client (no network)."""

import pytest

from app.agents import runtime
from app.agents.gemini_provider import GeminiProvider
from app.models.answer import Answer
from app.models.evaluation import Evaluation
from app.models.feedback import Feedback
from app.models.followup import FollowUp
from tests.conftest import GOOD_ANSWER, start
from tests.fakes import Clock, FakeClient, FakeResponse, eval_output, feedback_output
from tests.ratelimit_helpers import DAILY, PER_MINUTE, RateLimitError, quota_details
from tests.test_ai_interview_flow import POST, answer, complete, nxt

KEY = "SENTINEL-SECRET-KEY-0123456789"


def ev_ok(score=8.0, follow_up=""):
    return FakeResponse(eval_output(score, follow_up=follow_up).model_dump_json())


def fb_ok():
    return FakeResponse(feedback_output().model_dump_json())


def daily_429(message="You exceeded your current quota"):
    return RateLimitError(quota_details(quota_id=DAILY, retry_delay="17244s"), message)


@pytest.fixture()
def gemini(monkeypatch):
    """Install a real GeminiProvider whose client plays back `script`; returns (provider, client, clock)."""

    def build(script):
        clock = Clock()
        fake = FakeClient(script)
        provider = GeminiProvider(KEY, "gemini-test", client=fake, sleep=clock.sleep, clock=clock, quota_cooldown_cap_seconds=900)
        monkeypatch.setattr(runtime, "get_provider", lambda: provider)
        return provider, fake, clock

    return build


def test_daily_quota_during_an_interview_is_labelled_and_costs_one_request(client, user_a, gemini):
    _, fake, _ = gemini([daily_429()])
    iid = start(client, user_a, n=2)["interview"]["id"]

    first = answer(client, user_a, iid).json()
    assert first["evaluation_source"] == "dev_heuristic" and first["is_ai_generated"] is False
    assert first["fallback_reason"] == "quota_exhausted"
    assert "quota" in first["ai_notice"] and "NOT by an AI" in first["ai_notice"]
    assert len(fake.calls) == 1  # one request: no retries against an exhausted daily quota

    nxt(client, user_a, iid)
    second = answer(client, user_a, iid).json()
    assert second["fallback_reason"] == "quota_exhausted"  # the real cause, not a generic "cooldown"
    assert len(fake.calls) == 1  # fast: nothing was sent to Google again

    rep = complete(client, user_a, iid).json()
    assert len(fake.calls) == 1  # feedback did not call Google either
    assert rep["evaluation_source"] == "dev_heuristic" and rep["is_ai_generated"] is False
    assert rep["feedback_source"] == "dev_rules" and rep["feedback_is_ai_generated"] is False
    assert rep["evaluation_model"] is None and "NOT by an AI" in rep["notice"]
    assert all(q["evaluation_source"] == "dev_heuristic" and not q["is_ai_generated"] for q in rep["questions"])


def test_quota_running_out_part_way_gives_a_mixed_report_and_keeps_the_good_evaluation(client, user_a, gemini, db_session):
    _, fake, _ = gemini([ev_ok(9.0), daily_429()])
    iid = start(client, user_a, n=2)["interview"]["id"]

    a1 = answer(client, user_a, iid).json()
    assert a1["evaluation_source"] == "gemini" and a1["is_ai_generated"] and a1["ai_notice"] is None
    nxt(client, user_a, iid)
    a2 = answer(client, user_a, iid).json()
    assert a2["evaluation_source"] == "dev_heuristic" and a2["fallback_reason"] == "quota_exhausted"

    rep = complete(client, user_a, iid).json()
    assert rep["evaluation_source"] == "mixed" and rep["is_ai_generated"] is False
    assert "Mixed evaluation" in rep["notice"] and "NOT AI" in rep["notice"]
    assert [q["evaluation_source"] for q in rep["questions"]] == ["gemini", "dev_heuristic"]
    assert rep["feedback_source"] == "dev_rules"
    with db_session() as db:
        first = db.query(Answer).filter_by(interview_id=iid, order_index=0).one().evaluation
        assert first.source == "gemini" and first.is_ai_generated and first.overall == 90.0  # the 429 did not touch it
        assert db.query(Evaluation).count() == 2
        assert db.query(Feedback).one().source == "dev_rules"


def test_a_429_on_the_follow_up_reply_never_touches_the_original_ai_evaluation(client, user_a, gemini, db_session):
    _, _, _ = gemini([ev_ok(9.0, follow_up="Which article made it binding?"), daily_429()])
    iid = start(client, user_a, n=1)["interview"]["id"]
    assert answer(client, user_a, iid).json()["follow_up_question"] == "Which article made it binding?"

    r = client.post(f"{POST}/follow-up", json={"interview_id": iid, "answer_text": "Article 2A."}, headers=user_a)
    assert r.status_code == 200
    body = r.json()
    assert body["evaluation_source"] == "dev_heuristic" and body["is_ai_generated"] is False  # the REPLY's own label
    assert body["fallback_reason"] == "quota_exhausted" and "quota" in body["ai_notice"]
    with db_session() as db:
        ev = db.query(Evaluation).one()
        assert ev.source == "gemini" and ev.overall == 90.0 and ev.is_ai_generated
        fu = db.query(FollowUp).one()
        assert fu.answer_text == "Article 2A." and fu.source == "dev_heuristic"  # reply saved + honestly labelled


def test_operations_resume_independently_once_the_cooldown_has_passed(client, user_a, gemini):
    """The pause is not permanent: after it expires, evaluation AND feedback can use Gemini again."""
    _, fake, clock = gemini([daily_429(), ev_ok(8.0), fb_ok()])
    iid = start(client, user_a, n=2)["interview"]["id"]
    assert answer(client, user_a, iid).json()["fallback_reason"] == "quota_exhausted"
    nxt(client, user_a, iid)

    clock.now += 901  # past the capped quota cooldown
    second = answer(client, user_a, iid).json()
    assert second["evaluation_source"] == "gemini" and second["ai_notice"] is None

    rep = complete(client, user_a, iid).json()
    assert rep["feedback_source"] == "gemini" and rep["feedback_is_ai_generated"] is True
    assert rep["evaluation_source"] == "mixed"
    assert len(fake.calls) == 3


def test_a_per_minute_limit_is_waited_out_using_googles_delay(client, user_a, gemini):
    _, fake, clock = gemini([RateLimitError(quota_details(quota_id=PER_MINUTE, retry_delay="3s")), ev_ok(7.0)])
    iid = start(client, user_a, n=1)["interview"]["id"]
    ack = answer(client, user_a, iid).json()
    assert ack["evaluation_source"] == "gemini" and ack["ai_notice"] is None
    assert clock.sleeps == [3.0] and len(fake.calls) == 2  # waited what Google asked, then succeeded


def test_health_reports_whether_gemini_is_usable_right_now(client, user_a, gemini):
    provider, _, clock = gemini([daily_429()])
    assert client.get("/api/health").json()["ai_availability"] == {"available": True, "reason": None, "retry_after_seconds": None}
    iid = start(client, user_a, n=1)["interview"]["id"]
    answer(client, user_a, iid)
    h = client.get("/api/health").json()
    assert h["ai_availability"]["available"] is False and h["ai_availability"]["reason"] == "quota_exhausted"
    assert 0 < h["ai_availability"]["retry_after_seconds"] <= 901
    assert KEY not in str(h)
    clock.now += 901
    assert client.get("/api/health").json()["ai_availability"]["available"] is True


def test_health_without_a_provider_has_no_availability(client):
    assert client.get("/api/health").json()["ai_availability"] is None  # no key configured: nothing to be (un)available


def test_the_key_is_never_in_responses_or_logs_when_google_rejects_us(client, user_a, gemini, caplog):
    caplog.set_level("DEBUG")
    gemini([daily_429(message=f"quota exceeded for api key {KEY}")])
    iid = start(client, user_a, n=1)["interview"]["id"]
    texts = [answer(client, user_a, iid).text, complete(client, user_a, iid).text, client.get("/api/health").text,
             client.get(f"{POST}/{iid}", headers=user_a).text]
    assert all(KEY not in t for t in texts) and KEY not in caplog.text
