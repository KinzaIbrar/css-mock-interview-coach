from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings

settings.bcrypt_rounds = 4  # fast hashing in tests only

import app.models  # noqa: E402,F401
from app.database.session import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.question_service import seed_questions  # noqa: E402


@pytest.fixture(autouse=True)
def no_real_llm(monkeypatch):
    """Tests are hermetic: never call the real Gemini API (the developer's .env holds a live key).

    Default is the labelled development fallback (no provider). AI tests install a fake provider."""
    from app.agents import runtime

    monkeypatch.setattr(runtime, "get_provider", lambda: None)


LEGACY_DATASET = Path(__file__).parent / "fixtures" / "legacy_21.json"  # frozen Phase 3 question set


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with Session() as s:
        seed_questions(s, LEGACY_DATASET)
    yield Session
    engine.dispose()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        db = db_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)  # no `with`: lifespan (real DB init) is not run
    app.dependency_overrides.clear()


@pytest.fixture()
def full_db_session():
    """Same as db_session but seeded with the real curated dataset (data/questions/)."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with Session() as s:
        seed_questions(s, settings.questions_path)
    yield Session
    engine.dispose()


@pytest.fixture()
def full_client(full_db_session):
    def override_get_db():
        db = full_db_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


PASSWORD = "correct-horse-battery"


def register(client, email="user@example.com", name="Test User", password=PASSWORD):
    r = client.post("/api/auth/register", json={"email": email, "password": password, "full_name": name})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def user_a(client):
    return auth(register(client, "a@example.com", "User A"))


@pytest.fixture()
def user_b(client):
    return auth(register(client, "b@example.com", "User B"))


def start(client, headers, subject="Pakistan Affairs", difficulty="mixed", n=3):
    r = client.post(
        "/api/interviews/start",
        json={"subject": subject, "difficulty": difficulty, "num_questions": n, "duration_minutes": 30},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


GOOD_ANSWER = (
    "The Lahore Resolution of 1940 was passed by the Muslim League under Jinnah; because it demanded "
    "independent states for the Muslim majority areas it became the basis of the Pakistan movement. "
    "Fazlul Huq moved it. However, the objectives resolution and the constituent assembly came later. "
    "Therefore it is significant."
)


def run_full_interview(client, headers, subject="Pakistan Affairs", n=3, answer=GOOD_ANSWER):
    """Start, answer every question, complete. Returns the final report JSON."""
    s = start(client, headers, subject=subject, n=n)
    iid = s["interview"]["id"]
    for i in range(n):
        r = client.post("/api/interviews/answer", json={"interview_id": iid, "answer_text": answer}, headers=headers)
        assert r.status_code == 200, r.text
        r = client.post("/api/interviews/next", json={"interview_id": iid}, headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["finished"] == (i == n - 1)
    r = client.post("/api/interviews/complete", json={"interview_id": iid}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()
