import pytest

from tests.conftest import GOOD_ANSWER, run_full_interview, start


def test_start_creates_interview_with_first_question(client, user_a):
    s = start(client, user_a, n=3)
    assert s["interview"]["status"] == "in_progress"
    assert s["interview"]["num_questions"] == 3
    assert s["question_number"] == 1 and s["total_questions"] == 3
    q = s["question"]
    assert q["subject"] == "Pakistan Affairs"
    # the reference answer / keywords must never be shown during the interview
    assert "reference_answer" not in q and "keywords" not in q


def test_start_validation(client, user_a):
    base = {"subject": "English", "difficulty": "mixed", "num_questions": 2, "duration_minutes": 30}
    for bad in (
        {**base, "subject": "Astrology"},
        {**base, "difficulty": "extreme"},
        {**base, "mode": "weird"},
        {**base, "num_questions": 0},
        {**base, "num_questions": 99},
        {**base, "duration_minutes": 1},
    ):
        assert client.post("/api/interviews/start", json=bad, headers=user_a).status_code == 422


def test_start_with_too_few_questions_is_a_clear_400(client, user_a):
    r = client.post(
        "/api/interviews/start",
        json={"subject": "English", "difficulty": "hard", "num_questions": 5, "duration_minutes": 30},
        headers=user_a,
    )
    assert r.status_code == 400
    assert "available" in r.json()["detail"]


def test_questions_are_distinct_within_an_interview(client, user_a, db_session):
    from app.models.interview import Interview

    s = start(client, user_a, n=3)
    with db_session() as db:
        ids = db.get(Interview, s["interview"]["id"]).question_ids
    assert len(set(ids)) == 3


def test_submit_answer_returns_ack_without_feedback(client, user_a):
    s = start(client, user_a, n=2)
    iid = s["interview"]["id"]
    r = client.post("/api/interviews/answer", json={"interview_id": iid, "answer_text": GOOD_ANSWER}, headers=user_a)
    assert r.status_code == 200
    body = r.json()
    assert body["answered_count"] == 1 and body["has_next"] is True
    assert body["evaluation_source"] == "dev_heuristic"
    assert not {"overall", "scores", "strengths", "weaknesses"} & set(body)


def test_double_answer_conflicts(client, user_a):
    iid = start(client, user_a, n=2)["interview"]["id"]
    payload = {"interview_id": iid, "answer_text": GOOD_ANSWER}
    assert client.post("/api/interviews/answer", json=payload, headers=user_a).status_code == 200
    assert client.post("/api/interviews/answer", json=payload, headers=user_a).status_code == 409


def test_blank_answer_rejected(client, user_a):
    iid = start(client, user_a, n=2)["interview"]["id"]
    for text in ("", "    "):
        r = client.post("/api/interviews/answer", json={"interview_id": iid, "answer_text": text}, headers=user_a)
        assert r.status_code == 422


def test_next_requires_answer_first(client, user_a):
    iid = start(client, user_a, n=2)["interview"]["id"]
    assert client.post("/api/interviews/next", json={"interview_id": iid}, headers=user_a).status_code == 409


def test_next_advances_and_finishes(client, user_a):
    iid = start(client, user_a, n=2)["interview"]["id"]
    client.post("/api/interviews/answer", json={"interview_id": iid, "answer_text": GOOD_ANSWER}, headers=user_a)
    r = client.post("/api/interviews/next", json={"interview_id": iid}, headers=user_a).json()
    assert r["finished"] is False and r["question_number"] == 2 and r["question"] is not None
    client.post("/api/interviews/answer", json={"interview_id": iid, "answer_text": GOOD_ANSWER}, headers=user_a)
    r = client.post("/api/interviews/next", json={"interview_id": iid}, headers=user_a).json()
    assert r["finished"] is True and r["question"] is None


def test_answer_evaluation_is_persisted_and_labelled_dev(client, user_a, db_session):
    from app.models.answer import Answer

    iid = start(client, user_a, n=1)["interview"]["id"]
    client.post("/api/interviews/answer", json={"interview_id": iid, "answer_text": GOOD_ANSWER}, headers=user_a)
    with db_session() as db:
        answer = db.query(Answer).filter_by(interview_id=iid).one()
        assert answer.answer_text == GOOD_ANSWER
        ev = answer.evaluation
        assert ev.source == "dev_heuristic" and ev.is_ai_generated is False
        assert 0 <= ev.overall <= 100


def test_empty_quality_answer_scores_zero(client, user_a, db_session):
    from app.models.answer import Answer

    iid = start(client, user_a, n=1)["interview"]["id"]
    client.post("/api/interviews/answer", json={"interview_id": iid, "answer_text": "idk"}, headers=user_a)
    with db_session() as db:
        assert db.query(Answer).filter_by(interview_id=iid).one().evaluation.overall == 0.0


def test_complete_requires_at_least_one_answer(client, user_a):
    iid = start(client, user_a, n=2)["interview"]["id"]
    assert client.post("/api/interviews/complete", json={"interview_id": iid}, headers=user_a).status_code == 409


def test_full_flow_and_actions_after_completion(client, user_a):
    report = run_full_interview(client, user_a, n=3)
    iid = report["interview"]["id"]
    assert report["interview"]["status"] == "completed"
    assert 0 < report["overall_score"] <= 100
    payload = {"interview_id": iid, "answer_text": GOOD_ANSWER}
    assert client.post("/api/interviews/answer", json=payload, headers=user_a).status_code == 409
    assert client.post("/api/interviews/next", json={"interview_id": iid}, headers=user_a).status_code == 409
    # completing again is idempotent and returns the same report
    again = client.post("/api/interviews/complete", json={"interview_id": iid}, headers=user_a)
    assert again.status_code == 200 and again.json()["overall_score"] == report["overall_score"]


def test_skipped_questions_count_as_zero(client, user_a):
    iid = start(client, user_a, n=3)["interview"]["id"]
    client.post("/api/interviews/answer", json={"interview_id": iid, "answer_text": GOOD_ANSWER}, headers=user_a)
    r = client.post("/api/interviews/complete", json={"interview_id": iid}, headers=user_a).json()
    skipped = [q for q in r["questions"] if q["skipped"]]
    assert len(skipped) == 2 and all(q["scores"] is None for q in skipped)
    answered = [q for q in r["questions"] if not q["skipped"]][0]
    assert r["overall_score"] == pytest.approx(answered["overall"] / 3, abs=0.1)


def test_history_lists_newest_first(client, user_a):
    first = start(client, user_a, n=1)["interview"]["id"]
    second = start(client, user_a, subject="English", n=1)["interview"]["id"]
    r = client.get("/api/interviews/history", headers=user_a)
    assert r.status_code == 200
    assert [i["id"] for i in r.json()] == [second, first]


def test_interview_detail_in_progress_and_completed(client, user_a):
    s = start(client, user_a, n=2)
    iid = s["interview"]["id"]
    d = client.get(f"/api/interviews/{iid}", headers=user_a).json()
    assert d["current_question"]["id"] == s["question"]["id"]
    assert d["report_available"] is False and d["answered_indexes"] == []
    for _ in range(2):
        client.post("/api/interviews/answer", json={"interview_id": iid, "answer_text": GOOD_ANSWER}, headers=user_a)
        client.post("/api/interviews/next", json={"interview_id": iid}, headers=user_a)
    client.post("/api/interviews/complete", json={"interview_id": iid}, headers=user_a)
    d = client.get(f"/api/interviews/{iid}", headers=user_a).json()
    assert d["report_available"] is True and d["current_question"] is None and d["answered_indexes"] == [0, 1]
