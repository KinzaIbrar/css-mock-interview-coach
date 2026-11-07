def test_list_questions(client, user_a):
    r = client.get("/api/questions?limit=100", headers=user_a)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 21 and len(body["items"]) == 21
    assert "Sample" in body["notice"] or "sample" in body["notice"]
    assert all(q["is_sample"] for q in body["items"])


def test_filter_by_subject_and_difficulty(client, user_a):
    r = client.get("/api/questions", params={"subject": "English"}, headers=user_a)
    assert r.json()["total"] == 3
    r = client.get("/api/questions", params={"subject": "English", "difficulty": "hard"}, headers=user_a)
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["difficulty"] == "hard"


def test_search_questions(client, user_a):
    r = client.get("/api/questions", params={"search": "simile"}, headers=user_a)
    assert r.json()["total"] == 1
    assert client.get("/api/questions", params={"search": "zzzznomatch"}, headers=user_a).json()["total"] == 0


def test_pagination(client, user_a):
    r = client.get("/api/questions", params={"limit": 5, "offset": 5}, headers=user_a).json()
    assert len(r["items"]) == 5 and r["total"] == 21 and r["offset"] == 5


def test_invalid_difficulty_rejected(client, user_a):
    assert client.get("/api/questions", params={"difficulty": "impossible"}, headers=user_a).status_code == 422


def test_get_question_detail_includes_reference_answer(client, user_a):
    qid = client.get("/api/questions", headers=user_a).json()["items"][0]["id"]
    r = client.get(f"/api/questions/{qid}", headers=user_a)
    assert r.status_code == 200
    assert r.json()["reference_answer"] and r.json()["keywords"]


def test_get_question_404(client, user_a):
    assert client.get("/api/questions/99999", headers=user_a).status_code == 404
