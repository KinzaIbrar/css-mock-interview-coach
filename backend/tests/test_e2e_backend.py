"""End-to-end backend workflow on a temporary database created by the REAL Alembic migrations.

Mirrors what the frontend will do. Uses a fake Gemini provider (the real API is never called in tests)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.agents import runtime
from app.agents.errors import LLMTransientError
from app.core.config import settings
from app.database.migrate import run_migrations
from app.database.session import enable_sqlite_foreign_keys, get_db
from app.main import app
from app.models.answer import Answer
from app.models.evaluation import Evaluation
from app.models.feedback import Feedback
from app.models.followup import FollowUp
from app.models.interview import Interview
from app.services.question_service import seed_questions
from tests.fakes import FakeProvider, eval_output

PW = "correct-horse-battery"
ANSWER = "The Objectives Resolution of 1949 declared the sovereignty of Allah and promised democracy and minority rights."


@pytest.fixture()
def env(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'e2e.db').as_posix()}"
    run_migrations(url)  # the real migration chain 0001 -> 0003, not create_all
    engine = create_engine(url, connect_args={"check_same_thread": False})
    enable_sqlite_foreign_keys(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with Session() as s:
        assert seed_questions(s, settings.questions_path) == 112

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app), Session
    app.dependency_overrides.clear()
    engine.dispose()


def hdr(token):
    return {"Authorization": f"Bearer {token}"}


def test_complete_workflow_with_gemini_and_a_follow_up(env, monkeypatch):
    client, Session = env
    provider = FakeProvider([
        eval_output(8, follow_up="Which article made the resolution binding?"),  # Q1 answer: follow-up
        eval_output(9),                                                          # Q1 re-evaluation
    ])
    monkeypatch.setattr(runtime, "get_provider", lambda: provider)

    # 1-2. register + authenticate
    reg = client.post("/api/auth/register", json={"email": "e2e@example.com", "password": PW, "full_name": "E2E"})
    assert reg.status_code == 201
    login = client.post("/api/auth/login", json={"email": "e2e@example.com", "password": PW})
    assert login.status_code == 200
    h = hdr(login.json()["access_token"])
    assert client.get("/api/auth/me", headers=h).json()["email"] == "e2e@example.com"

    # 3-4. start a mock interview and receive the first question
    s = client.post("/api/interviews/start", headers=h, json={
        "subject": "Pakistan Affairs", "difficulty": "mixed", "num_questions": 2, "duration_minutes": 20, "mode": "mock"})
    assert s.status_code == 201
    iid = s.json()["interview"]["id"]
    assert s.json()["question_number"] == 1 and set(s.json()["question"]) == {"id", "subject", "topic", "difficulty", "text"}

    # 5-7. submit an answer -> Gemini evaluation -> follow-up
    a1 = client.post("/api/interviews/answer", headers=h, json={"interview_id": iid, "answer_text": ANSWER})
    assert a1.status_code == 200
    b1 = a1.json()
    assert b1["evaluation_source"] == "gemini" and b1["is_ai_generated"] and b1["ai_notice"] is None
    assert b1["follow_up_question"] == "Which article made the resolution binding?"
    assert not {"overall", "scores", "strengths", "weaknesses"} & set(b1)  # nothing revealed mid-interview

    # pending follow-up blocks /next
    blocked = client.post("/api/interviews/next", headers=h, json={"interview_id": iid})
    assert blocked.status_code == 409
    assert client.get(f"/api/interviews/{iid}", headers=h).json()["pending_follow_up"] == b1["follow_up_question"]

    # 8. answer the follow-up (never chained)
    f1 = client.post("/api/interviews/follow-up", headers=h, json={"interview_id": iid, "answer_text": "Article 2A."})
    assert f1.status_code == 200 and f1.json()["evaluation_source"] == "gemini"
    assert client.post("/api/interviews/follow-up", headers=h, json={"interview_id": iid, "answer_text": "again"}).status_code == 409

    # 9. continue to the next question, answer it, finish
    n1 = client.post("/api/interviews/next", headers=h, json={"interview_id": iid})
    assert n1.status_code == 200 and n1.json()["finished"] is False and n1.json()["question_number"] == 2
    a2 = client.post("/api/interviews/answer", headers=h, json={"interview_id": iid, "answer_text": "A reasonable second answer about the topic."})
    assert a2.status_code == 200 and a2.json()["follow_up_question"] is None
    assert client.post("/api/interviews/next", headers=h, json={"interview_id": iid}).json()["finished"] is True

    # 10-11. complete and read the report
    done = client.post("/api/interviews/complete", headers=h, json={"interview_id": iid})
    assert done.status_code == 200
    rep = done.json()
    assert client.get(f"/api/reports/{iid}", headers=h).json() == rep
    assert rep["evaluation_source"] == "gemini" and rep["is_ai_generated"] and rep["feedback_source"] == "gemini"
    assert rep["evaluation_model"] == "fake-model-1" and "fake-model-1" in rep["notice"]
    assert rep["questions"][0]["follow_up_question"] and rep["questions"][0]["follow_up_answer"] == "Article 2A."
    assert rep["overall_score"] == pytest.approx((80.0 + 80.0) / 2, abs=0.1)  # Q1 main (8) + Q2 (8); the follow-up (9) is separate
    assert rep["questions"][0]["follow_up_evaluation"]["overall"] == 90.0 and rep["follow_up_average"] == 90.0
    assert rep["summary"] and rep["improvements"] and set(rep["criteria_scores"]) == {
        "relevance", "subject_knowledge", "accuracy", "reasoning", "structure", "clarity"}

    # 12. dashboard + history + progress
    dash = client.get("/api/dashboard", headers=h).json()
    assert dash["total_interviews"] == 1 and dash["average_score"] == rep["overall_score"]
    hist = client.get("/api/interviews/history", headers=h).json()
    assert [i["id"] for i in hist] == [iid] and hist[0]["status"] == "completed"
    assert client.get("/api/progress", headers=h).json()["subjects"][0]["sessions_count"] == 1

    # 13. everything persisted with the right labels
    with Session() as db:
        iv = db.get(Interview, iid)
        assert iv.status == "completed" and iv.overall_score == rep["overall_score"]
        answers = db.query(Answer).filter_by(interview_id=iid).order_by(Answer.order_index).all()
        assert len(answers) == 2 and all(a.evaluation.source == "gemini" and a.evaluation.is_ai_generated for a in answers)
        assert db.query(Evaluation).count() == 2  # no duplicate evaluations after the re-evaluation
        assert db.query(FollowUp).count() == 1
        fb = db.query(Feedback).one()
        assert fb.source == "gemini" and fb.is_ai_generated and fb.model == "fake-model-1"


def test_workflow_when_gemini_is_unavailable_is_labelled_and_complete(env, monkeypatch):
    client, Session = env
    provider = FakeProvider([LLMTransientError("x", "http_503")] * 6)
    monkeypatch.setattr(runtime, "get_provider", lambda: provider)
    h = hdr(client.post("/api/auth/register", json={"email": "down@example.com", "password": PW, "full_name": "D"}).json()["access_token"])
    iid = client.post("/api/interviews/start", headers=h, json={"subject": "English", "num_questions": 2, "duration_minutes": 20}).json()["interview"]["id"]
    for _ in range(2):
        a = client.post("/api/interviews/answer", headers=h, json={"interview_id": iid, "answer_text": ANSWER}).json()
        assert a["evaluation_source"] == "dev_heuristic" and a["is_ai_generated"] is False
        assert a["fallback_reason"] == "http_503" and "NOT by an AI" in a["ai_notice"] and a["follow_up_question"] is None
        client.post("/api/interviews/next", headers=h, json={"interview_id": iid})
    rep = client.post("/api/interviews/complete", headers=h, json={"interview_id": iid}).json()
    assert rep["evaluation_source"] == "dev_heuristic" and rep["is_ai_generated"] is False
    assert rep["feedback_source"] == "dev_rules" and rep["evaluation_model"] is None and "NOT by an AI" in rep["notice"]
    with Session() as db:
        assert {e.source for e in db.query(Evaluation)} == {"dev_heuristic"}
        assert db.query(Evaluation).first().model is None


def test_unauthenticated_and_cross_user_access(env, monkeypatch):
    client, _ = env
    monkeypatch.setattr(runtime, "get_provider", lambda: None)
    for method, path in [("get", "/api/dashboard"), ("get", "/api/interviews/history"), ("get", "/api/reports/1"),
                         ("post", "/api/interviews/start"), ("post", "/api/interviews/follow-up"), ("get", "/api/progress")]:
        assert getattr(client, method)(path).status_code == 401, path
    assert client.get("/api/dashboard", headers=hdr("not.a.token")).status_code == 401
    owner = hdr(client.post("/api/auth/register", json={"email": "o@example.com", "password": PW, "full_name": "O"}).json()["access_token"])
    other = hdr(client.post("/api/auth/register", json={"email": "x@example.com", "password": PW, "full_name": "X"}).json()["access_token"])
    iid = client.post("/api/interviews/start", headers=owner, json={"subject": "English", "num_questions": 1, "duration_minutes": 20}).json()["interview"]["id"]
    for call in (
        lambda: client.get(f"/api/interviews/{iid}", headers=other),
        lambda: client.post("/api/interviews/answer", headers=other, json={"interview_id": iid, "answer_text": "hello there"}),
        lambda: client.post("/api/interviews/follow-up", headers=other, json={"interview_id": iid, "answer_text": "hello there"}),
        lambda: client.post("/api/interviews/complete", headers=other, json={"interview_id": iid}),
        lambda: client.get(f"/api/reports/{iid}", headers=other),
    ):
        assert call().status_code == 404
    assert client.get("/api/interviews/history", headers=other).json() == []


def test_invalid_requests_return_clear_errors(env, monkeypatch):
    client, _ = env
    monkeypatch.setattr(runtime, "get_provider", lambda: None)
    h = hdr(client.post("/api/auth/register", json={"email": "v@example.com", "password": PW, "full_name": "V"}).json()["access_token"])
    bad_start = {"subject": "Astrology", "num_questions": 1, "duration_minutes": 20}
    assert client.post("/api/interviews/start", headers=h, json=bad_start).status_code == 422
    assert client.post("/api/interviews/start", headers=h, json={"subject": "English", "num_questions": 99, "duration_minutes": 20}).status_code == 422
    too_many = client.post("/api/interviews/start", headers=h, json={"subject": "English", "difficulty": "hard", "num_questions": 10, "duration_minutes": 20})
    assert too_many.status_code == 400 and "available" in too_many.json()["detail"]
    iid = client.post("/api/interviews/start", headers=h, json={"subject": "English", "num_questions": 1, "duration_minutes": 20}).json()["interview"]["id"]
    assert client.post("/api/interviews/next", headers=h, json={"interview_id": iid}).status_code == 409  # unanswered
    assert client.post("/api/interviews/complete", headers=h, json={"interview_id": iid}).status_code == 409  # nothing answered
    assert client.get(f"/api/reports/{iid}", headers=h).status_code == 409  # not completed
    assert client.post("/api/interviews/answer", headers=h, json={"interview_id": iid, "answer_text": " "}).status_code == 422
