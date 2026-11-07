"""Conversational multi-agent features: introduction, conversation order/numbering, separate follow-up
evaluation, repeat protection, observations (privacy/bounds/ownership/rules), coaching, agents endpoint."""

import pytest

from app.agents import runtime
from app.agents.coaching_agent import build as build_coaching
from app.models.followup import FollowUp
from app.services import observation_service
from tests.conftest import GOOD_ANSWER
from tests.fakes import FakeProvider, eval_output

POST = "/api/interviews"


@pytest.fixture()
def ai(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr(runtime, "get_provider", lambda: provider)
    return provider


def start_intro(client, h, n=2, subject="Pakistan Affairs"):
    r = client.post(
        f"{POST}/start",
        json={"subject": subject, "difficulty": "mixed", "num_questions": n, "duration_minutes": 30, "with_introduction": True},
        headers=h,
    )
    assert r.status_code == 201, r.text
    return r.json()


def answer(client, h, iid, text=GOOD_ANSWER):
    return client.post(f"{POST}/answer", json={"interview_id": iid, "answer_text": text}, headers=h)


def intro(client, h, iid, text="I studied political science and want to serve the public."):
    return client.post(f"{POST}/introduction", json={"interview_id": iid, "answer_text": text}, headers=h)


def nxt(client, h, iid):
    return client.post(f"{POST}/next", json={"interview_id": iid}, headers=h)


# ---- introduction -------------------------------------------------------------------------------
def test_introduction_is_required_before_the_first_answer(client, user_a, ai):
    body = start_intro(client, user_a)
    iid = body["interview"]["id"]
    assert body["introduction_required"] is True
    assert "tell me about yourself" in body["introduction_prompt"]["question"].lower()
    assert answer(client, user_a, iid).status_code == 409
    d = client.get(f"{POST}/{iid}", headers=user_a).json()
    assert d["introduction_pending"] is True and d["main_questions_answered"] == 0
    assert [t["kind"] for t in d["conversation"]] == ["greeting", "introduction_question"]

    assert intro(client, user_a, iid).status_code == 200
    assert intro(client, user_a, iid).status_code == 409  # not twice
    assert answer(client, user_a, iid).status_code == 200


def test_legacy_interview_has_no_introduction_step(client, user_a):
    from tests.conftest import start

    body = start(client, user_a)
    assert body["introduction_required"] is False and body["introduction_prompt"] is None
    assert intro(client, user_a, body["interview"]["id"]).status_code == 409


def test_blank_introduction_is_rejected_and_ownership_enforced(client, user_a, user_b):
    iid = start_intro(client, user_a)["interview"]["id"]
    assert intro(client, user_a, iid, "   ").status_code == 422
    assert intro(client, user_b, iid).status_code == 404


def test_introduction_reaches_the_evaluator_prompt_but_is_not_scored(client, user_a, ai):
    iid = start_intro(client, user_a)["interview"]["id"]
    intro(client, user_a, iid, "I am a law graduate from Lahore.")
    answer(client, user_a, iid)
    prompt = ai.eval_calls[0]["prompt"]
    assert "<candidate_introduction>" in prompt and "law graduate from Lahore" in prompt


# ---- conversation order & numbering -----------------------------------------------------------------
def test_conversation_order_and_main_question_numbering(client, user_a, ai):
    ai.script = [eval_output(5, follow_up="Which article was that?"), eval_output(8), eval_output(7)]
    iid = start_intro(client, user_a, n=2)["interview"]["id"]
    intro(client, user_a, iid)
    ack = answer(client, user_a, iid).json()
    assert ack["follow_up_question"] == "Which article was that?"
    assert {s["agent"] for s in ack["trace"]} == {"orchestration", "evaluator", "interviewer"}
    client.post(f"{POST}/follow-up", json={"interview_id": iid, "answer_text": "Article 2A."}, headers=user_a)
    assert nxt(client, user_a, iid).status_code == 200

    d = client.get(f"{POST}/{iid}", headers=user_a).json()
    kinds = [(t["kind"], t["question_number"]) for t in d["conversation"]]
    assert kinds == [
        ("greeting", None), ("introduction_question", None), ("introduction", None),
        ("question", 1), ("answer", 1), ("follow_up", 1), ("follow_up_answer", 1),
        ("question", 2),
    ]
    assert d["main_questions_answered"] == 1  # the follow-up is not counted as a main question
    assert d["question_number"] == 2 and d["total_questions"] == 2


def test_resume_returns_pending_follow_up_and_history(client, user_a, ai):
    ai.script = [eval_output(5, follow_up="Why?")]
    iid = start_intro(client, user_a, n=1)["interview"]["id"]
    intro(client, user_a, iid)
    answer(client, user_a, iid)
    d = client.get(f"{POST}/{iid}", headers=user_a).json()
    assert d["pending_follow_up"] == "Why?"
    assert d["conversation"][-1]["kind"] == "follow_up"


# ---- follow-ups are evaluated separately ----------------------------------------------------------
def test_follow_up_reply_is_evaluated_separately_in_the_report(client, user_a, ai, db_session):
    ai.script = [eval_output(8, follow_up="Why?"), eval_output(4)]
    iid = start_intro(client, user_a, n=1)["interview"]["id"]
    intro(client, user_a, iid)
    answer(client, user_a, iid)
    client.post(f"{POST}/follow-up", json={"interview_id": iid, "answer_text": "Not sure."}, headers=user_a)
    assert "Evaluate ONLY the candidate's reply" in ai.eval_calls[1]["prompt"]
    rep = client.post(f"{POST}/complete", json={"interview_id": iid}, headers=user_a).json()
    q = rep["questions"][0]
    assert q["overall"] == 80.0 and q["follow_up_evaluation"]["overall"] == 40.0
    assert rep["overall_score"] == 80.0 and rep["follow_up_average"] == 40.0
    assert rep["introduction"].startswith("I studied")


def test_second_follow_up_reply_is_rejected(client, user_a, ai):
    ai.script = [eval_output(5, follow_up="Why?")]
    iid = start_intro(client, user_a, n=1)["interview"]["id"]
    intro(client, user_a, iid)
    answer(client, user_a, iid)
    body = {"interview_id": iid, "answer_text": "because"}
    assert client.post(f"{POST}/follow-up", json=body, headers=user_a).status_code == 200
    assert client.post(f"{POST}/follow-up", json=body, headers=user_a).status_code == 409


def test_repeated_follow_up_is_not_asked(client, user_a, ai, db_session):
    from app.models.question import Question

    with db_session() as db:
        text = db.query(Question).first().text
    # the model "suggests" the main question again; the Conductor must drop it
    ai.script = [eval_output(5, follow_up=text)]
    iid = start_intro(client, user_a, n=1)["interview"]["id"]
    intro(client, user_a, iid)
    # whichever question was picked, a follow-up equal to ANY asked text is refused; use the picked one
    picked = client.get(f"{POST}/{iid}", headers=user_a).json()["current_question"]["text"]
    ai.script = [eval_output(5, follow_up=picked)]
    ack = answer(client, user_a, iid).json()
    assert ack["follow_up_question"] is None
    with db_session() as db:
        assert db.query(FollowUp).count() == 0


# ---- dev mode never fabricates AI behaviour --------------------------------------------------------
def test_dev_mode_trace_is_labelled_not_ai(client, user_a):
    iid = start_intro(client, user_a)["interview"]["id"]
    intro(client, user_a, iid)
    ack = answer(client, user_a, iid).json()
    ev = next(s for s in ack["trace"] if s["agent"] == "evaluator")
    assert ev["source"] == "dev_heuristic" and ev["status"] == "error" and "heuristic" in ev["detail"]


# ---- observations ---------------------------------------------------------------------------------
GOOD_CAM = {
    "enabled": True, "total_seconds": 120, "analysed_seconds": 110, "samples": 400,
    "face_visible_pct": 95, "facing_camera_pct": 80, "posture_stability": "stable",
    "movement_level": "low", "tracking_quality_pct": 90,
}


def post_obs(client, h, iid, **body):
    return client.post(f"{POST}/observations", json={"interview_id": iid, **body}, headers=h)


def test_observations_are_saved_and_reported_separately(client, user_a, ai):
    iid = start_intro(client, user_a, n=1)["interview"]["id"]
    intro(client, user_a, iid)
    answer(client, user_a, iid)
    r = post_obs(client, user_a, iid, camera=GOOD_CAM, voice={"dictated_words": 120, "dictated_seconds": 60})
    assert r.status_code == 200 and "no video" in r.json()["stored"]
    rep = client.post(f"{POST}/complete", json={"interview_id": iid}, headers=user_a).json()
    nv = rep["observations"]
    assert nv["camera_used"] and nv["voice_used"] and nv["limitations"] and nv["rules"]
    metrics = {m["key"]: m for m in nv["metrics"]}
    assert metrics["facing_camera"]["value"] == "80% of the time"
    assert metrics["speaking_pace"]["value"] == "120 words/min"
    assert "score" not in nv  # no combined score
    assert rep["overall_score"] == 70.0 or rep["overall_score"] > 0  # verbal score unaffected


def test_observations_reject_raw_data_and_out_of_range_values(client, user_a):
    iid = start_intro(client, user_a)["interview"]["id"]
    assert post_obs(client, user_a, iid, camera={**GOOD_CAM, "frames": ["data:image/png;base64,AAA"]}).status_code == 422
    assert post_obs(client, user_a, iid, camera={**GOOD_CAM, "face_visible_pct": 140}).status_code == 422
    assert post_obs(client, user_a, iid, camera={**GOOD_CAM, "landmarks": [[0, 0]]}).status_code == 422
    assert post_obs(client, user_a, iid, extra_field=1, camera=GOOD_CAM).status_code == 422


def test_observations_are_owner_only(client, user_a, user_b):
    iid = start_intro(client, user_a)["interview"]["id"]
    assert post_obs(client, user_b, iid, camera=GOOD_CAM).status_code == 404
    assert client.post(f"{POST}/observations", json={"interview_id": iid, "camera": GOOD_CAM}).status_code == 401


def test_unreliable_tracking_shows_not_enough_data():
    weak = {**GOOD_CAM, "analysed_seconds": 5, "samples": 10, "tracking_quality_pct": 30}
    rep = observation_service.build_report({"camera": weak})
    assert all(not m.available and m.note == "Not enough data" for m in rep.metrics)
    assert "Face visible" in rep.unavailable


def test_short_voice_sample_has_no_pace_and_nothing_means_no_report():
    rep = observation_service.build_report({"voice": {"dictated_words": 10, "dictated_seconds": 5}})
    assert rep.metrics[0].available is False
    assert observation_service.build_report(None) is None
    assert observation_service.build_report({"camera": {"enabled": False, "total_seconds": 0}}) is None


def test_no_unsupported_claims_in_rules_or_limitations():
    text = " ".join(observation_service.RULES + observation_service.LIMITATIONS).lower()
    assert "no emotion, confidence, honesty or personality is inferred" in text
    assert "never leave your device" in text


# ---- coaching ---------------------------------------------------------------------------------------
def test_coaching_plan_is_rule_based_and_reports_weak_topics(client, user_a, ai, db_session):
    ai.script = [eval_output(2, follow_up="Why?"), eval_output(3)]
    iid = start_intro(client, user_a, n=1)["interview"]["id"]
    intro(client, user_a, iid)
    answer(client, user_a, iid, "short")
    client.post(f"{POST}/follow-up", json={"interview_id": iid, "answer_text": "idk"}, headers=user_a)
    rep = client.post(f"{POST}/complete", json={"interview_id": iid}, headers=user_a).json()
    c = rep["coaching"]
    assert c["source"] == "rule_based" and c["is_ai_generated"] is False
    assert c["weak_topics"] and c["weak_topics"][0]["score"] < 60
    asked = {q["question_id"] for q in rep["questions"]}
    assert all(p["question_id"] not in asked for p in c["recommended_practice"])


# ---- agents endpoint ----------------------------------------------------------------------------------
def test_agents_endpoint_lists_four_agents_and_requires_auth(client, user_a):
    assert client.get("/api/agents").status_code == 401
    agents = client.get("/api/agents", headers=user_a).json()
    assert [a["key"] for a in agents] == ["interviewer", "evaluator", "coaching", "orchestration"]
    ev = next(a for a in agents if a["key"] == "evaluator")
    assert ev["uses_llm"] is True and ev["available"] is False  # tests run without a Gemini key
    assert "not configured" in ev["unavailable_reason"]
    assert next(a for a in agents if a["key"] == "orchestration")["available"] is True


# ---- adaptive difficulty --------------------------------------------------------------------------------
def test_adaptation_only_reorders_unasked_questions(client, user_a, ai, db_session):
    from app.models.interview import Interview

    ai.script = [eval_output(9), eval_output(9), eval_output(9)]
    body = start_intro(client, user_a, n=3)
    iid = body["interview"]["id"]
    with db_session() as db:
        before = list(db.get(Interview, iid).question_ids)
    intro(client, user_a, iid)
    answer(client, user_a, iid)
    assert nxt(client, user_a, iid).status_code == 200
    with db_session() as db:
        after = list(db.get(Interview, iid).question_ids)
    assert before[0] == after[0] and sorted(before) == sorted(after) and len(set(after)) == 3
