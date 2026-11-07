import json

import pytest

from app.agents import runtime
from app.agents.errors import LLMInvalidOutput, LLMRequestError, LLMTransientError
from app.agents.gemini_provider import GeminiProvider
from app.core.config import settings
from app.models.answer import Answer
from app.models.evaluation import Evaluation
from app.models.feedback import Feedback
from app.models.followup import FollowUp
from app.models.interview import Interview
from app.models.progress import Progress
from tests.conftest import GOOD_ANSWER, auth, register, start
from tests.fakes import Clock, FakeApiError, FakeClient, FakeProvider, FakeResponse, eval_output, feedback_output

POST = "/api/interviews"


@pytest.fixture()
def ai(monkeypatch):
    """Install a scriptable fake Gemini provider."""
    provider = FakeProvider()
    monkeypatch.setattr(runtime, "get_provider", lambda: provider)
    return provider


def answer(client, h, iid, text=GOOD_ANSWER):
    return client.post(f"{POST}/answer", json={"interview_id": iid, "answer_text": text}, headers=h)


def nxt(client, h, iid):
    return client.post(f"{POST}/next", json={"interview_id": iid}, headers=h)


def complete(client, h, iid):
    return client.post(f"{POST}/complete", json={"interview_id": iid}, headers=h)


def run_interview(client, h, n=3):
    iid = start(client, h, n=n)["interview"]["id"]
    acks = []
    for i in range(n):
        acks.append(answer(client, h, iid).json())
        nxt(client, h, iid)
    return iid, acks, complete(client, h, iid)


# ---- success path -------------------------------------------------------------------------------
def test_full_ai_interview_produces_a_labelled_ai_report(client, user_a, ai):
    ai.default_score = 8.0
    iid, acks, resp = run_interview(client, user_a, n=3)
    assert all(a["evaluation_source"] == "gemini" and a["is_ai_generated"] and a["ai_notice"] is None for a in acks)
    assert resp.status_code == 200
    rep = resp.json()
    assert rep["evaluation_source"] == "gemini" and rep["is_ai_generated"] is True
    assert rep["evaluation_model"] == "fake-model-1" and "fake-model-1" in rep["notice"]
    assert "mistakes" in rep["notice"]
    assert rep["overall_score"] == 80.0  # six scores of 8 -> 80, computed by us
    assert rep["feedback_source"] == "gemini" and rep["feedback_is_ai_generated"] is True
    assert rep["summary"].startswith("You gave solid answers")
    assert all(q["evaluation_source"] == "gemini" and q["is_ai_generated"] for q in rep["questions"])
    assert len(ai.eval_calls) == 3 and len(ai.feedback_calls) == 1


def test_answer_ack_reveals_no_scores_or_feedback(client, user_a, ai):
    iid = start(client, user_a, n=2)["interview"]["id"]
    body = answer(client, user_a, iid).json()
    assert not {"overall", "scores", "strengths", "weaknesses", "missing_info", "summary"} & set(body)


def test_scores_come_from_the_model_per_criterion(client, user_a, ai, db_session):
    ai.script = [eval_output(relevance=10, subject_knowledge=6, accuracy=4, reasoning=2, structure=8, clarity=10)]
    iid = start(client, user_a, n=1)["interview"]["id"]
    answer(client, user_a, iid)
    with db_session() as db:
        ev = db.query(Evaluation).one()
        assert (ev.relevance, ev.subject_knowledge, ev.accuracy, ev.reasoning, ev.structure, ev.clarity) == (10, 6, 4, 2, 8, 10)
        assert ev.overall == 66.7 and ev.source == "gemini" and ev.is_ai_generated and ev.model == "fake-model-1"
        assert ev.strengths == ["Covers the main idea clearly"] and ev.missing_info == ["A specific date"]


def test_conversation_context_is_carried_across_questions(client, user_a, ai):
    iid = start(client, user_a, n=3)["interview"]["id"]
    for _ in range(3):
        answer(client, user_a, iid)
        nxt(client, user_a, iid)
    first, second, third = (c["prompt"] for c in ai.eval_calls)
    assert "EARLIER IN THIS INTERVIEW" not in first
    assert "EARLIER IN THIS INTERVIEW" in second and "80.0/100" in second
    assert third.count("/100") >= 2  # both earlier questions are in the context


def test_prompts_never_leak_between_users_or_include_credentials(client, user_a, ai, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "SENTINEL-KEY-XYZ-123456789")
    run_interview(client, user_a, n=2)
    for call in ai.calls:
        assert "SENTINEL-KEY" not in call["prompt"] and "SENTINEL-KEY" not in call["system"]
        assert "a@example.com" not in call["prompt"]


# ---- follow-ups ---------------------------------------------------------------------------------
def test_follow_up_is_asked_answered_and_persisted(client, user_a, ai, db_session):
    ai.script = [eval_output(score=5, follow_up="Can you name the article that made it binding?")]
    iid = start(client, user_a, n=2)["interview"]["id"]
    ack = answer(client, user_a, iid).json()
    assert ack["follow_up_question"] == "Can you name the article that made it binding?"
    assert ack["evaluation_source"] == "gemini"

    # the interview cannot move on until the follow-up is answered
    assert nxt(client, user_a, iid).status_code == 409
    detail = client.get(f"{POST}/{iid}", headers=user_a).json()
    assert detail["pending_follow_up"] == "Can you name the article that made it binding?"

    ai.script = [eval_output(score=9)]
    fu = client.post(f"{POST}/follow-up", json={"interview_id": iid, "answer_text": "Article 2A."}, headers=user_a)
    assert fu.status_code == 200
    assert fu.json()["evaluation_source"] == "gemini" and fu.json()["has_next"] is True
    assert client.get(f"{POST}/{iid}", headers=user_a).json()["pending_follow_up"] is None
    assert nxt(client, user_a, iid).status_code == 200

    # the follow-up reply is evaluated SEPARATELY; the main answer's evaluation is not re-scored
    p = ai.eval_calls[1]["prompt"]
    assert "Can you name the article" in p and "Article 2A." in p and "FOLLOW-UPS ALLOWED NOW: no" in p
    with db_session() as db:
        assert db.query(Evaluation).count() == 1 and db.query(Evaluation).one().overall == 50.0
        row = db.query(FollowUp).one()
        assert row.overall == 90.0 and row.source == "gemini" and row.is_ai_generated
        assert row.question_text.startswith("Can you name") and row.answer_text == "Article 2A."


def test_follow_up_shows_in_the_report(client, user_a, ai):
    ai.script = [eval_output(follow_up="Why?")]
    iid = start(client, user_a, n=1)["interview"]["id"]
    answer(client, user_a, iid)
    client.post(f"{POST}/follow-up", json={"interview_id": iid, "answer_text": "Because of X."}, headers=user_a)
    q = complete(client, user_a, iid).json()["questions"][0]
    assert q["follow_up_question"] == "Why?" and q["follow_up_answer"] == "Because of X."


def test_only_one_follow_up_per_question(client, user_a, ai, db_session):
    ai.script = [eval_output(follow_up="First follow-up?"), eval_output(follow_up="A second one?")]
    iid = start(client, user_a, n=2)["interview"]["id"]
    answer(client, user_a, iid)
    r = client.post(f"{POST}/follow-up", json={"interview_id": iid, "answer_text": "reply"}, headers=user_a)
    assert r.json().get("follow_up_question") is None  # re-evaluation never chains another follow-up
    again = client.post(f"{POST}/follow-up", json={"interview_id": iid, "answer_text": "again"}, headers=user_a)
    assert again.status_code == 409
    with db_session() as db:
        assert db.query(FollowUp).count() == 1


def test_follow_ups_are_capped_per_interview(client, user_a, ai, monkeypatch):
    monkeypatch.setattr(settings, "max_follow_ups_per_interview", 1)
    ai.script = [eval_output(follow_up="Q-A?"), eval_output(), eval_output(follow_up="Q-B?")]
    iid = start(client, user_a, n=3)["interview"]["id"]
    assert answer(client, user_a, iid).json()["follow_up_question"] == "Q-A?"
    client.post(f"{POST}/follow-up", json={"interview_id": iid, "answer_text": "r"}, headers=user_a)  # uses script[1]
    nxt(client, user_a, iid)
    second = answer(client, user_a, iid).json()  # model asks again, but the cap (1) is used up
    assert second["follow_up_question"] is None
    assert "FOLLOW-UPS ALLOWED NOW: no" in ai.eval_calls[2]["prompt"]
    assert nxt(client, user_a, iid).status_code == 200


def test_a_follow_up_suggestion_is_ignored_when_the_prompt_said_not_allowed(client, user_a, ai, monkeypatch):
    monkeypatch.setattr(settings, "max_follow_ups_per_interview", 0)
    ai.script = [eval_output(follow_up="Sneaky follow-up?")]
    iid = start(client, user_a, n=1)["interview"]["id"]
    assert answer(client, user_a, iid).json()["follow_up_question"] is None


def test_follow_up_endpoint_rules(client, user_a, user_b, ai):
    ai.script = [eval_output(follow_up="Why?")]
    iid = start(client, user_a, n=2)["interview"]["id"]
    body = {"interview_id": iid, "answer_text": "reply"}
    assert client.post(f"{POST}/follow-up", json=body, headers=user_a).status_code == 409  # nothing answered yet
    answer(client, user_a, iid)
    assert client.post(f"{POST}/follow-up", json=body, headers=user_b).status_code == 404  # not their interview
    assert client.post(f"{POST}/follow-up", json={"interview_id": iid, "answer_text": "  "}, headers=user_a).status_code == 422
    assert client.post(f"{POST}/follow-up", json=body).status_code == 401
    assert client.post(f"{POST}/follow-up", json=body, headers=user_a).status_code == 200
    complete(client, user_a, iid)
    assert client.post(f"{POST}/follow-up", json=body, headers=user_a).status_code == 409  # completed


def test_no_follow_up_asked_means_follow_up_endpoint_conflicts(client, user_a, ai):
    iid = start(client, user_a, n=1)["interview"]["id"]
    assert answer(client, user_a, iid).json()["follow_up_question"] is None
    r = client.post(f"{POST}/follow-up", json={"interview_id": iid, "answer_text": "x"}, headers=user_a)
    assert r.status_code == 409


def test_unanswered_follow_up_does_not_block_completion(client, user_a, ai):
    ai.script = [eval_output(follow_up="Why?")]
    iid = start(client, user_a, n=1)["interview"]["id"]
    answer(client, user_a, iid)
    rep = complete(client, user_a, iid).json()
    assert rep["questions"][0]["follow_up_question"] == "Why?" and rep["questions"][0]["follow_up_answer"] is None


# ---- timeouts and failures: labelled fallback, never fabricated AI ------------------------------
@pytest.mark.parametrize(
    "error,reason",
    [
        (LLMTransientError("x", "timeout"), "timeout"),
        (LLMTransientError("x", "http_503"), "http_503"),
        (LLMRequestError("x", "http_401"), "http_401"),
        (LLMInvalidOutput("x"), "invalid_output"),
    ],
)
def test_gemini_failure_during_answer_falls_back_with_a_visible_label(client, user_a, ai, db_session, error, reason):
    ai.script = [error]
    iid = start(client, user_a, n=2)["interview"]["id"]
    ack = answer(client, user_a, iid)
    assert ack.status_code == 200  # the interview is not blocked by an AI outage
    b = ack.json()
    assert b["evaluation_source"] == "dev_heuristic" and b["is_ai_generated"] is False
    assert b["fallback_reason"] == reason and "development" in b["ai_notice"] and "NOT by an AI" in b["ai_notice"]
    assert b["follow_up_question"] is None
    with db_session() as db:
        ev = db.query(Evaluation).one()
        assert ev.source == "dev_heuristic" and ev.is_ai_generated is False and ev.model is None
    assert nxt(client, user_a, iid).status_code == 200


def test_total_outage_yields_a_clearly_non_ai_report(client, user_a, ai):
    ai.script = [LLMTransientError("x", "timeout")] * 10
    iid, acks, resp = run_interview(client, user_a, n=3)
    assert all(a["evaluation_source"] == "dev_heuristic" for a in acks)
    rep = resp.json()
    assert rep["evaluation_source"] == "dev_heuristic" and rep["is_ai_generated"] is False
    assert "NOT by an AI" in rep["notice"] and rep["evaluation_model"] is None
    assert rep["feedback_source"] == "dev_rules" and rep["feedback_is_ai_generated"] is False
    assert all(q["evaluation_source"] == "dev_heuristic" and not q["is_ai_generated"] for q in rep["questions"])


def test_mixed_report_when_gemini_fails_part_way(client, user_a, ai):
    ai.script = [eval_output(8), LLMTransientError("x", "timeout"), eval_output(8)]
    iid, acks, resp = run_interview(client, user_a, n=3)
    assert [a["evaluation_source"] for a in acks] == ["gemini", "dev_heuristic", "gemini"]
    rep = resp.json()
    assert rep["evaluation_source"] == "mixed" and rep["is_ai_generated"] is False
    assert "Mixed evaluation" in rep["notice"] and "NOT AI" in rep["notice"]
    assert [q["evaluation_source"] for q in rep["questions"]] == ["gemini", "dev_heuristic", "gemini"]


def test_feedback_failure_only_downgrades_the_feedback(client, user_a, ai):
    ai.script = [eval_output(), eval_output(), LLMTransientError("x", "timeout")]
    iid = start(client, user_a, n=2)["interview"]["id"]
    for _ in range(2):
        answer(client, user_a, iid)
        nxt(client, user_a, iid)
    rep = complete(client, user_a, iid).json()
    assert rep["evaluation_source"] == "gemini" and rep["is_ai_generated"] is True
    assert rep["feedback_source"] == "dev_rules" and rep["feedback_is_ai_generated"] is False
    assert "not by an AI" in rep["summary"]


def test_ai_feedback_with_invented_topics_keeps_only_real_ones(client, user_a, ai):
    ai.script = [eval_output(), feedback_output(revision_topics=["Not A Real Topic"])]
    iid = start(client, user_a, n=1)["interview"]["id"]
    answer(client, user_a, iid)
    rep = complete(client, user_a, iid).json()
    assert rep["feedback_source"] == "gemini" and rep["revision_topics"] == []


def test_without_a_provider_the_app_is_in_labelled_dev_mode(client, user_a):
    iid = start(client, user_a, n=1)["interview"]["id"]
    b = answer(client, user_a, iid).json()
    assert b["evaluation_source"] == "dev_heuristic" and b["fallback_reason"] == "not_configured"
    assert "not configured" in b["ai_notice"] and "NOT by an AI" in b["ai_notice"]
    rep = complete(client, user_a, iid).json()
    assert rep["evaluation_source"] == "dev_heuristic" and rep["feedback_source"] == "dev_rules"


# ---- the real GeminiProvider through the whole stack ---------------------------------------------
def test_transient_504_is_retried_inside_a_real_interview_step(client, user_a, monkeypatch):
    clock = Clock()
    fake = FakeClient([FakeApiError(504), FakeResponse(eval_output(7).model_dump_json())])
    provider = GeminiProvider("k-123", "gemini-test", client=fake, sleep=clock.sleep, clock=clock, max_retries=2)
    monkeypatch.setattr(runtime, "get_provider", lambda: provider)
    iid = start(client, user_a, n=1)["interview"]["id"]
    ack = answer(client, user_a, iid).json()
    assert ack["evaluation_source"] == "gemini" and len(fake.calls) == 2 and clock.sleeps == [2]


def test_persistent_outage_falls_back_and_then_fails_fast_during_cooldown(client, user_a, monkeypatch):
    clock = Clock()
    fake = FakeClient([FakeApiError(504)] * 20)
    provider = GeminiProvider("k-123", "gemini-test", client=fake, sleep=clock.sleep, clock=clock, max_retries=2)
    monkeypatch.setattr(runtime, "get_provider", lambda: provider)
    iid = start(client, user_a, n=2)["interview"]["id"]
    first = answer(client, user_a, iid).json()
    assert first["evaluation_source"] == "dev_heuristic" and first["fallback_reason"] == "timeout"
    sent = len(fake.calls)
    assert sent == 3  # 1 + 2 retries
    nxt(client, user_a, iid)
    second = answer(client, user_a, iid).json()
    assert second["fallback_reason"] == "cooldown" and len(fake.calls) == sent  # no request, no waiting


def test_api_key_never_appears_in_responses_or_logs(client, user_a, monkeypatch, caplog):
    secret = "SENTINEL-SECRET-KEY-0123456789"
    caplog.set_level("DEBUG")
    clock = Clock()
    fake = FakeClient([FakeApiError(401, f"invalid key {secret}")] + [FakeApiError(503, f"oops {secret}")] * 8)
    provider = GeminiProvider(secret, "gemini-test", client=fake, sleep=clock.sleep, clock=clock)
    monkeypatch.setattr(runtime, "get_provider", lambda: provider)
    monkeypatch.setattr(settings, "gemini_api_key", secret)
    captured = []
    iid = start(client, user_a, n=2)["interview"]["id"]
    captured.append(answer(client, user_a, iid).text)  # 401 -> fallback
    nxt(client, user_a, iid)
    captured.append(answer(client, user_a, iid).text)  # 503s -> fallback
    captured.append(complete(client, user_a, iid).text)
    captured.append(client.get(f"{POST}/{iid}", headers=user_a).text)
    captured.append(client.get("/api/health").text)
    assert all(secret not in text for text in captured)
    assert secret not in caplog.text


# ---- persistence --------------------------------------------------------------------------------
def test_everything_is_saved_in_the_database(client, user_a, ai, db_session):
    ai.script = [eval_output(8, follow_up="Why?"), eval_output(6), eval_output(7)]  # feedback uses the default
    iid = start(client, user_a, n=2)["interview"]["id"]
    answer(client, user_a, iid, "first answer text")
    client.post(f"{POST}/follow-up", json={"interview_id": iid, "answer_text": "follow-up reply"}, headers=user_a)
    nxt(client, user_a, iid)
    answer(client, user_a, iid, "second answer text")
    nxt(client, user_a, iid)
    rep = complete(client, user_a, iid).json()
    with db_session() as db:
        iv = db.get(Interview, iid)
        assert iv.status == "completed" and iv.completed_at is not None
        answers = db.query(Answer).filter_by(interview_id=iid).order_by(Answer.order_index).all()
        assert [a.answer_text for a in answers] == ["first answer text", "second answer text"]
        assert [a.evaluation.overall for a in answers] == [80.0, 70.0]  # the follow-up reply (6/10) did not replace the 8/10
        assert answers[0].follow_up.overall == 60.0
        assert iv.overall_score == 75.0 == rep["overall_score"]
        fb = db.query(Feedback).filter_by(interview_id=iid).one()
        assert fb.source == "gemini" and fb.is_ai_generated and fb.model == "fake-model-1"
        assert fb.summary == rep["summary"] and len(fb.model_answers) == 2
        prog = db.query(Progress).filter_by(user_id=iv.user_id).one()
        assert prog.sessions_count == 1 and prog.last_score == 75.0


def test_report_is_stable_and_complete_is_idempotent_without_new_ai_calls(client, user_a, ai):
    iid, _, resp = run_interview(client, user_a, n=2)
    calls = len(ai.calls)
    again = complete(client, user_a, iid)
    assert again.status_code == 200 and again.json() == resp.json()
    assert client.get(f"/api/reports/{iid}", headers=user_a).json() == resp.json()
    assert len(ai.calls) == calls


def test_dashboard_and_progress_use_ai_scores(client, user_a, ai):
    ai.default_score = 9.0
    run_interview(client, user_a, n=2)
    d = client.get("/api/dashboard", headers=user_a).json()
    assert d["total_interviews"] == 1 and d["average_score"] == 90.0 and d["best_score"] == 90.0
    p = client.get("/api/progress", headers=user_a).json()
    assert p["subjects"][0]["avg_score"] == 90.0


def test_progress_note_compares_with_the_previous_session(client, user_a, ai):
    ai.default_score = 5.0
    run_interview(client, user_a, n=1)
    ai.default_score = 8.0
    _, _, resp = run_interview(client, user_a, n=1)
    note = resp.json()["progress_note"]
    assert "up 30.0 points" in note and "not by AI" not in note  # plain rule-based comparison


def test_ai_results_are_isolated_between_users(client, user_a, user_b, ai):
    iid, _, _ = run_interview(client, user_a, n=1)
    assert client.get(f"/api/reports/{iid}", headers=user_b).status_code == 404
    assert client.get(f"{POST}/{iid}", headers=user_b).status_code == 404
    assert client.get("/api/dashboard", headers=user_b).json()["total_interviews"] == 0


def test_two_users_interleaved_do_not_share_context(client, user_a, user_b, ai):
    a = start(client, user_a, n=2)["interview"]["id"]
    b = start(client, user_b, n=2)["interview"]["id"]
    answer(client, user_a, a)
    nxt(client, user_a, a)
    answer(client, user_b, b)  # B's first answer must not see A's context
    assert "EARLIER IN THIS INTERVIEW" not in ai.eval_calls[-1]["prompt"]
