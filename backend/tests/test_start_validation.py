"""POST /interviews/start: the real cause of the repeated 400s, pinned down.

400 means exactly one thing: the question bank has fewer questions for (subject, topic, difficulty) than requested.
Malformed fields are 422. In the real dataset 52 of 53 topics hold fewer than 5 questions, so
'topic + a specific difficulty' with the default 5 questions is refused for every combination."""

import pytest

from app.core.config import settings
from app.rag import load_dataset
from tests.conftest import auth, register

URL = "/api/interviews/start"


def body(**over):
    base = {"subject": "English", "difficulty": "mixed", "num_questions": 3, "duration_minutes": 30, "mode": "mock"}
    base.update(over)
    return base


@pytest.fixture()
def h(full_client):
    return auth(register(full_client, "v@example.com", "V"))


# ---- 422: malformed requests are never confused with "not enough questions" -------------------------------------
@pytest.mark.parametrize(
    "over",
    [
        {"subject": "Astrology"}, {"subject": ""}, {"difficulty": "extreme"}, {"difficulty": "HARD"}, {"mode": "weird"},
        {"num_questions": 0}, {"num_questions": 21}, {"num_questions": "five"}, {"duration_minutes": 4}, {"duration_minutes": 121},
        {"topic": "x" * 129},
    ],
)
def test_malformed_fields_are_422_not_400(full_client, h, over):
    r = full_client.post(URL, json=body(**over), headers=h)
    assert r.status_code == 422, r.text
    assert isinstance(r.json()["detail"], list)  # field-level errors the UI can map


def test_missing_subject_is_422(full_client, h):
    assert full_client.post(URL, json={"difficulty": "mixed"}, headers=h).status_code == 422


# ---- 400: not enough questions, with a message that names the problem --------------------------------------------
def test_topic_plus_difficulty_with_the_default_count_is_a_clear_400(full_client, h):
    r = full_client.post(URL, json=body(topic="Grammar", difficulty="hard", num_questions=5), headers=h)
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert isinstance(detail, str)
    assert "English / Grammar" in detail and "hard" in detail and "requested 5" in detail and "Only 1" in detail


def test_unknown_topic_is_a_clear_400_with_zero_available(full_client, h):
    r = full_client.post(URL, json=body(topic="No Such Topic"), headers=h)
    assert r.status_code == 400 and "Only 0" in r.json()["detail"] and "No Such Topic" in r.json()["detail"]


def test_difficulty_only_shortage_is_a_400(full_client, h):
    r = full_client.post(URL, json=body(difficulty="hard", num_questions=5), headers=h)  # English has 4 hard questions
    assert r.status_code == 400 and "Only 4" in r.json()["detail"]


# ---- the property the form relies on: GET /questions total == the most start will accept ----------------------------------
def _combos():
    records = load_dataset(settings.questions_path)
    seen = sorted({(r.subject, r.topic, r.difficulty) for r in records})
    return seen[:: max(1, len(seen) // 14)]  # a deterministic spread across subjects, topics and levels


@pytest.mark.parametrize("subject,topic,difficulty", _combos())
def test_exact_count_from_the_questions_endpoint_matches_what_start_accepts(full_client, h, subject, topic, difficulty):
    total = full_client.get("/api/questions", params={"subject": subject, "topic": topic, "difficulty": difficulty, "limit": 1}, headers=h).json()["total"]
    assert total >= 1
    ok = full_client.post(URL, json=body(subject=subject, topic=topic, difficulty=difficulty, num_questions=total), headers=h)
    assert ok.status_code == 201, ok.text
    assert ok.json()["total_questions"] == total
    over = full_client.post(URL, json=body(subject=subject, topic=topic, difficulty=difficulty, num_questions=total + 1), headers=h)
    assert over.status_code == 400 and f"Only {total}" in over.json()["detail"]


def test_a_combination_with_no_questions_counts_zero_and_is_refused(full_client, h):
    total = full_client.get("/api/questions", params={"subject": "English", "topic": "Grammar", "difficulty": "medium", "limit": 1}, headers=h).json()["total"]
    zero = full_client.get("/api/questions", params={"subject": "English", "topic": "Figures of Speech", "difficulty": "hard", "limit": 1}, headers=h).json()["total"]
    assert total >= 1 and zero == 0
    r = full_client.post(URL, json=body(topic="Figures of Speech", difficulty="hard", num_questions=1), headers=h)
    assert r.status_code == 400 and "Only 0" in r.json()["detail"]


def test_topic_matching_is_case_insensitive_on_both_endpoints(full_client, h):
    a = full_client.get("/api/questions", params={"subject": "English", "topic": "grammar", "limit": 1}, headers=h).json()["total"]
    b = full_client.get("/api/questions", params={"subject": "English", "topic": "GRAMMAR", "limit": 1}, headers=h).json()["total"]
    assert a == b >= 1
    assert full_client.post(URL, json=body(topic="gRaMmAr", num_questions=a), headers=h).status_code == 201


def test_a_refused_request_creates_nothing(full_client, h):
    full_client.post(URL, json=body(topic="Grammar", difficulty="hard", num_questions=5), headers=h)
    assert full_client.get("/api/interviews/history", headers=h).json() == []
    assert full_client.get("/api/dashboard", headers=h).json()["in_progress_count"] == 0
