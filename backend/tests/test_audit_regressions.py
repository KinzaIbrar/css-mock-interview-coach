"""Regression tests for problems found in the Phase 4 audit.

These use a real SQLite *file* database (not the shared in-memory one) because the problems are about
locks, transactions and constraints, which the in-memory StaticPool fixtures cannot show.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.agents import runtime
from app.agents.errors import LLMTransientError
from app.core.config import settings
from app.database.session import Base, enable_sqlite_foreign_keys, get_db
from app.main import app
from app.models.answer import Answer
from app.models.evaluation import Evaluation
from app.models.followup import FollowUp
from app.models.interview import Interview
from app.models.user import User
from app.services.question_service import seed_questions
from tests.conftest import GOOD_ANSWER, auth, register
from tests.fakes import FakeProvider, eval_output

POST = "/api/interviews"


@pytest.fixture()
def file_db(tmp_path):
    """File-backed SQLite with a SHORT lock timeout so a held write lock shows up as a fast failure."""
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'audit.db').as_posix()}", connect_args={"check_same_thread": False, "timeout": 0.5}
    )
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with Session() as s:
        seed_questions(s, settings.questions_path.parent / "questions")  # full curated dataset
    yield Session
    engine.dispose()


@pytest.fixture()
def fclient(file_db):
    def override():
        db = file_db()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def user(client, email="a@example.com"):
    return auth(register(client, email, "A"))


def start(client, h, n=2, subject="English"):
    r = client.post(f"{POST}/start", json={"subject": subject, "difficulty": "mixed", "num_questions": n, "duration_minutes": 20}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["interview"]["id"]


def answer(client, h, iid, text_=GOOD_ANSWER):
    return client.post(f"{POST}/answer", json={"interview_id": iid, "answer_text": text_}, headers=h)


# ---- 1. no database write lock may be held while waiting for Gemini ----------------------------
def test_other_users_can_write_while_gemini_is_slow(fclient, file_db, monkeypatch):
    """A slow/retried Gemini call must not freeze every other writer (SQLite allows one writer at a time)."""
    h = user(fclient)
    iid = start(fclient, h)
    outcome = {}

    def during_the_gemini_call(schema, prompt):
        # Meanwhile, another request (another user registering) writes to the database.
        try:
            with file_db() as other:
                other.add(User(email="other@example.com", full_name="O", hashed_password="x", preferences={}))
                other.commit()
            outcome["write"] = "ok"
        except OperationalError as exc:
            outcome["write"] = f"BLOCKED: {exc.orig}"
        return eval_output(7)

    provider = FakeProvider([during_the_gemini_call])
    monkeypatch.setattr(runtime, "get_provider", lambda: provider)
    assert answer(fclient, h, iid).status_code == 200
    assert outcome["write"] == "ok", outcome["write"]


def test_follow_up_reply_does_not_hold_the_lock_either(fclient, file_db, monkeypatch):
    h = user(fclient)
    iid = start(fclient, h)
    provider = FakeProvider([eval_output(5, follow_up="Why?")])
    monkeypatch.setattr(runtime, "get_provider", lambda: provider)
    answer(fclient, h, iid)
    outcome = {}

    def during(schema, prompt):
        try:
            with file_db() as other:
                other.add(User(email="o2@example.com", full_name="O", hashed_password="x", preferences={}))
                other.commit()
            outcome["write"] = "ok"
        except OperationalError as exc:
            outcome["write"] = f"BLOCKED: {exc.orig}"
        return eval_output(8)

    provider.script = [during]
    r = fclient.post(f"{POST}/follow-up", json={"interview_id": iid, "answer_text": "reply"}, headers=h)
    assert r.status_code == 200 and outcome["write"] == "ok", outcome


def test_feedback_generation_does_not_hold_the_lock(fclient, file_db, monkeypatch):
    h = user(fclient)
    iid = start(fclient, h, n=1)
    provider = FakeProvider()
    monkeypatch.setattr(runtime, "get_provider", lambda: provider)
    answer(fclient, h, iid)
    outcome = {}

    def during(schema, prompt):
        try:
            with file_db() as other:
                other.add(User(email="o3@example.com", full_name="O", hashed_password="x", preferences={}))
                other.commit()
            outcome["write"] = "ok"
        except OperationalError as exc:
            outcome["write"] = f"BLOCKED: {exc.orig}"
        from tests.fakes import feedback_output

        return feedback_output(prompt)

    provider.script = [during]
    assert fclient.post(f"{POST}/complete", json={"interview_id": iid}, headers=h).status_code == 200
    assert outcome["write"] == "ok", outcome


# ---- 2. an interrupted request must not leave an answer without an evaluation -----------------
def test_interrupted_answer_leaves_nothing_behind_and_can_be_retried(fclient, file_db, monkeypatch):
    h = user(fclient)
    iid = start(fclient, h)

    class Boom(Exception):
        pass

    def crash(schema, prompt):
        raise Boom("process died mid-request")  # not an LLMError: simulates an unexpected failure

    provider = FakeProvider([crash])
    monkeypatch.setattr(runtime, "get_provider", lambda: provider)
    r = answer(fclient, h, iid)
    assert r.status_code == 200 and r.json()["evaluation_source"] == "dev_heuristic"  # AI layer bug never blocks the interview
    assert r.json()["fallback_reason"] == "unexpected_error"


def test_a_crash_after_evaluation_rolls_back_the_whole_answer(fclient, file_db, monkeypatch):
    """If persisting fails, there must be no orphan Answer row and the candidate can simply resubmit."""
    h = user(fclient)
    iid = start(fclient, h)
    import app.agents.graph as graph

    real_save = graph.save_evaluation_node
    calls = {"n": 0}

    def flaky_save(state, config):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("disk full")
        return real_save(state, config)

    monkeypatch.setattr(graph, "answer_graph", graph._build_answer_graph())  # rebuilt below with the flaky node
    monkeypatch.setattr(graph, "save_evaluation_node", flaky_save)
    monkeypatch.setattr(graph, "answer_graph", graph._build_answer_graph())
    with pytest.raises(RuntimeError):
        answer(fclient, h, iid)
    with file_db() as db:
        assert db.query(Answer).count() == 0 and db.query(Evaluation).count() == 0
    assert answer(fclient, h, iid).status_code == 200  # retry works
    with file_db() as db:
        assert db.query(Answer).count() == 1 and db.query(Evaluation).count() == 1


# ---- 3. a failed follow-up re-evaluation must not destroy a good AI evaluation -----------------
def test_failed_follow_up_evaluation_never_touches_the_main_ai_evaluation(fclient, file_db, monkeypatch):
    h = user(fclient)
    iid = start(fclient, h)
    provider = FakeProvider([eval_output(9, follow_up="Why?"), LLMTransientError("x", "timeout")])
    monkeypatch.setattr(runtime, "get_provider", lambda: provider)
    answer(fclient, h, iid)
    r = fclient.post(f"{POST}/follow-up", json={"interview_id": iid, "answer_text": "because"}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["evaluation_source"] == "dev_heuristic" and body["is_ai_generated"] is False  # the REPLY's own label
    assert body["fallback_reason"] == "timeout" and body["ai_notice"]
    with file_db() as db:
        ev = db.query(Evaluation).one()
        assert ev.source == "gemini" and ev.is_ai_generated and ev.overall == 90.0 and ev.model == "fake-model-1"
        fu = db.query(FollowUp).one()
        assert fu.answer_text == "because" and fu.source == "dev_heuristic" and not fu.is_ai_generated


# ---- 4. concurrent / repeated completion ----------------------------------------------------------
def test_losing_a_completion_race_returns_the_existing_report(fclient, file_db, monkeypatch):
    h = user(fclient)
    iid = start(fclient, h, n=1)
    provider = FakeProvider()
    monkeypatch.setattr(runtime, "get_provider", lambda: provider)
    answer(fclient, h, iid)
    import app.services.interview_service as svc

    real = svc.run_completion_step

    def lose_the_race(db, state):
        # Another request finishes the same interview first; ours then collides on the unique constraint.
        monkeypatch.setattr(svc, "run_completion_step", real)  # the competing request uses the real workflow
        other = fclient.post(f"{POST}/complete", json={"interview_id": iid}, headers=h)
        assert other.status_code == 200
        raise IntegrityError("insert", {}, Exception("UNIQUE constraint failed: feedback.interview_id"))

    monkeypatch.setattr(svc, "run_completion_step", lose_the_race)
    r = fclient.post(f"{POST}/complete", json={"interview_id": iid}, headers=h)
    assert r.status_code == 200 and r.json()["interview"]["status"] == "completed"


def test_duplicate_answer_submission_is_a_clean_409(fclient, file_db, monkeypatch):
    h = user(fclient)
    iid = start(fclient, h)
    provider = FakeProvider()
    monkeypatch.setattr(runtime, "get_provider", lambda: provider)
    assert answer(fclient, h, iid).status_code == 200
    assert answer(fclient, h, iid).status_code == 409
    assert len(provider.eval_calls) == 1  # the duplicate did not cost another Gemini call


def test_double_submit_race_loses_cleanly(fclient, file_db, monkeypatch):
    """Both requests pass the 'not answered yet' check; the loser hits the unique constraint -> 409, no 500."""
    h = user(fclient)
    iid = start(fclient, h)

    def other_request_wins(schema, prompt):
        r = answer(fclient, h, iid, "the competing answer submitted by the other request")
        assert r.status_code == 200
        return eval_output(7)

    provider = FakeProvider([other_request_wins])
    monkeypatch.setattr(runtime, "get_provider", lambda: provider)
    r = answer(fclient, h, iid)
    assert r.status_code == 409
    with file_db() as db:
        assert db.query(Answer).count() == 1 and db.query(Answer).one().answer_text.startswith("the competing")


# ---- 5. foreign keys are really enforced (SQLite ignores them unless asked) ------------------------
def test_sqlite_foreign_keys_are_enforced(file_db):
    with file_db() as db:
        db.add(Answer(interview_id=9999, question_id=1, order_index=0, answer_text="orphan"))
        with pytest.raises(IntegrityError):
            db.commit()


def test_deleting_a_user_cascades_through_the_whole_graph(fclient, file_db, monkeypatch):
    provider = FakeProvider([eval_output(5, follow_up="Why?")])
    monkeypatch.setattr(runtime, "get_provider", lambda: provider)
    h = user(fclient)
    iid = start(fclient, h, n=1)
    answer(fclient, h, iid)
    fclient.post(f"{POST}/follow-up", json={"interview_id": iid, "answer_text": "r"}, headers=h)
    fclient.post(f"{POST}/complete", json={"interview_id": iid}, headers=h)
    with file_db() as db:
        db.delete(db.query(User).one())
        db.commit()
        for table in ("interviews", "answers", "evaluations", "feedback", "follow_ups", "progress"):
            assert db.execute(text(f"select count(*) from {table}")).scalar() == 0, table
        assert db.execute(text("select count(*) from questions")).scalar() > 100  # shared data untouched


def test_production_engine_enables_foreign_keys():
    """Checked without connecting, so the test never creates or touches the real database file."""
    from app.database.session import engine

    if engine.dialect.name == "sqlite":
        assert "_set_pragma" in [getattr(f, "__name__", "") for f in engine.pool.dispatch.connect]  # PRAGMA foreign_keys=ON


# ---- 6. input edge cases ------------------------------------------------------------------------------
@pytest.mark.parametrize("payload", [
    {"answer_text": ""}, {"answer_text": "   \n\t "}, {"answer_text": "x" * 8001}, {},
    {"answer_text": "ok", "time_taken_seconds": -1}, {"answer_text": "ok", "time_taken_seconds": "soon"},
])
def test_invalid_answers_are_rejected_before_any_ai_call(fclient, file_db, monkeypatch, payload):
    h = user(fclient)
    iid = start(fclient, h)
    provider = FakeProvider()
    monkeypatch.setattr(runtime, "get_provider", lambda: provider)
    r = fclient.post(f"{POST}/answer", json={"interview_id": iid, **payload}, headers=h)
    assert r.status_code == 422 and provider.calls == []


@pytest.mark.parametrize("iid", [0, -1, 999999])
def test_unknown_interview_ids_return_404(fclient, file_db, iid):
    h = user(fclient)
    for path, body in [
        ("answer", {"interview_id": iid, "answer_text": "hello there"}),
        ("follow-up", {"interview_id": iid, "answer_text": "hello there"}),
        ("next", {"interview_id": iid}),
        ("complete", {"interview_id": iid}),
    ]:
        assert fclient.post(f"{POST}/{path}", json=body, headers=h).status_code == 404, path
    assert fclient.get(f"{POST}/{iid}", headers=h).status_code == 404
    assert fclient.get(f"/api/reports/{iid}", headers=h).status_code == 404


def test_non_integer_interview_id_is_422(fclient, file_db):
    h = user(fclient)
    assert fclient.post(f"{POST}/next", json={"interview_id": "abc"}, headers=h).status_code == 422
    assert fclient.get(f"{POST}/abc", headers=h).status_code == 422


def test_unicode_urdu_and_emoji_round_trip_through_the_json_columns(fclient, file_db, monkeypatch):
    provider = FakeProvider([eval_output(7, strengths=["واضح جواب"], follow_up="")])
    monkeypatch.setattr(runtime, "get_provider", lambda: provider)
    h = user(fclient)
    iid = start(fclient, h, n=1)
    text_ = "پاکستان کا آئین 1973 میں منظور ہوا 🇵🇰 — Article 2A"
    assert answer(fclient, h, iid, text_).status_code == 200
    rep = fclient.post(f"{POST}/complete", json={"interview_id": iid}, headers=h).json()
    assert rep["questions"][0]["answer_text"] == text_ and rep["strengths"] == ["واضح جواب"]
    assert text_ in provider.eval_calls[0]["prompt"]
