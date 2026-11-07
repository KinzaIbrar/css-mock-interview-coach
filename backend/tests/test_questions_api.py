from tests.conftest import GOOD_ANSWER, auth, register, run_full_interview, start


def headers(client):
    return auth(register(client, "q@example.com", "Q User"))


def test_meta_describes_the_bank(full_client):
    h = headers(full_client)
    m = full_client.get("/api/questions/meta", headers=h)
    assert m.status_code == 200
    body = m.json()
    assert body["total"] == 112 and len(body["subjects"]) == 7
    eng = next(s for s in body["subjects"] if s["subject"] == "English")
    assert eng["count"] == 16 and sum(eng["difficulties"].values()) == 16
    assert sum(t["count"] for t in eng["topics"]) == 16
    assert "kashmir" in body["tags"] and body["tags"] == sorted(body["tags"])
    assert "sample" in body["notice"].lower()


def test_meta_requires_auth_and_does_not_shadow_question_ids(full_client):
    assert full_client.get("/api/questions/meta").status_code == 401
    h = headers(full_client)
    assert full_client.get("/api/questions/meta", headers=h).status_code == 200
    assert full_client.get("/api/questions/1", headers=h).status_code == 200


def test_new_fields_are_returned(full_client):
    h = headers(full_client)
    q = full_client.get("/api/questions", params={"search": "Objectives Resolution", "limit": 1}, headers=h).json()["items"][0]
    assert q["tags"] and q["explanation"] and len(q["evaluation_criteria"]) >= 2
    assert q["reference_answer"] and q["keywords"]


def test_filters_subject_topic_difficulty_tag(full_client):
    h = headers(full_client)
    get = lambda **p: full_client.get("/api/questions", params={"limit": 100, **p}, headers=h).json()  # noqa: E731
    assert get(subject="Islamic Studies")["total"] == 16
    assert get(subject="Islamic Studies", difficulty="easy")["total"] == 5
    assert get(topic="Seerah")["total"] >= 2
    assert get(tag="kashmir")["total"] >= 2
    assert get(subject="English", topic="Grammar", difficulty="easy")["total"] >= 2
    assert get(topic="No Such Topic")["total"] == 0


def test_search_is_ranked_and_scored(full_client):
    h = headers(full_client)
    r = full_client.get("/api/questions", params={"search": "Objectives Resolution"}, headers=h).json()
    assert r["items"][0]["text"].startswith("Describe the main features of the Objectives Resolution")
    scores = [i["score"] for i in r["items"]]
    assert all(s > 0 for s in scores) and scores == sorted(scores, reverse=True)
    plain = full_client.get("/api/questions", params={"subject": "English"}, headers=h).json()
    assert all(i["score"] is None for i in plain["items"])


def test_pagination_through_the_api(full_client):
    h = headers(full_client)
    seen = []
    for offset in range(0, 112, 40):
        page = full_client.get("/api/questions", params={"limit": 40, "offset": offset}, headers=h).json()
        assert page["total"] == 112 and page["limit"] == 40 and page["offset"] == offset
        seen += [i["id"] for i in page["items"]]
    assert len(seen) == len(set(seen)) == 112
    assert full_client.get("/api/questions", params={"limit": 101}, headers=h).status_code == 422
    assert full_client.get("/api/questions", params={"offset": -1}, headers=h).status_code == 422


# ---- interview compatibility with the curated bank ----------------------------------------------
def test_existing_interview_workflow_with_full_dataset(full_client):
    h = headers(full_client)
    report = run_full_interview(full_client, h, subject="Governance and Constitutional Studies", n=5)
    assert report["interview"]["status"] == "completed" and len(report["questions"]) == 5
    assert full_client.get(f"/api/reports/{report['interview']['id']}", headers=h).json() == report
    d = full_client.get("/api/dashboard", headers=h).json()
    assert d["total_interviews"] == 1


def test_interview_questions_never_reveal_answers_or_criteria(full_client):
    h = headers(full_client)
    s = start(full_client, h, subject="Current Affairs", n=3)
    assert set(s["question"]) == {"id", "subject", "topic", "difficulty", "text"}


def test_mixed_interview_ramps_in_difficulty(full_client):
    h = headers(full_client)
    s = start(full_client, h, subject="International Relations", difficulty="mixed", n=6)
    iid = s["interview"]["id"]
    rank = {"easy": 0, "medium": 1, "hard": 2}
    levels = [rank[s["question"]["difficulty"]]]
    for _ in range(5):
        full_client.post("/api/interviews/answer", json={"interview_id": iid, "answer_text": GOOD_ANSWER}, headers=h)
        levels.append(rank[full_client.post("/api/interviews/next", json={"interview_id": iid}, headers=h).json()["question"]["difficulty"]])
    assert levels == sorted(levels) and set(levels) == {0, 1, 2}


def test_single_difficulty_interview_only_uses_that_level(full_client):
    h = headers(full_client)
    s = start(full_client, h, subject="English", difficulty="hard", n=4)
    iid = s["interview"]["id"]
    got = [s["question"]["difficulty"]]
    for _ in range(3):
        full_client.post("/api/interviews/answer", json={"interview_id": iid, "answer_text": GOOD_ANSWER}, headers=h)
        got.append(full_client.post("/api/interviews/next", json={"interview_id": iid}, headers=h).json()["question"]["difficulty"])
    assert set(got) == {"hard"}


def _question_ids(client, h, iid):
    ids, d = [], client.get(f"/api/interviews/{iid}", headers=h).json()
    ids.append(d["current_question"]["id"])
    for _ in range(d["total_questions"] - 1):
        client.post("/api/interviews/answer", json={"interview_id": iid, "answer_text": GOOD_ANSWER}, headers=h)
        ids.append(client.post("/api/interviews/next", json={"interview_id": iid}, headers=h).json()["question"]["id"])
    return ids


def test_consecutive_interviews_avoid_repeating_questions(full_client):
    h = headers(full_client)
    first = _question_ids(full_client, h, start(full_client, h, subject="English", n=5)["interview"]["id"])
    second = _question_ids(full_client, h, start(full_client, h, subject="English", n=5)["interview"]["id"])
    third = _question_ids(full_client, h, start(full_client, h, subject="English", n=5)["interview"]["id"])
    assert not set(first) & set(second)  # 16 questions available, so two sessions fit without repeats
    assert len(set(first) | set(second) | set(third)) >= 10
    assert len(set(third)) == 5


def test_recently_seen_questions_are_reused_only_when_necessary(full_client):
    h = headers(full_client)
    # 5 easy English questions exist; two interviews of 4 must overlap, but never within one interview
    a = _question_ids(full_client, h, start(full_client, h, subject="English", difficulty="easy", n=4)["interview"]["id"])
    b = _question_ids(full_client, h, start(full_client, h, subject="English", difficulty="easy", n=4)["interview"]["id"])
    assert len(set(a)) == 4 and len(set(b)) == 4
    assert len(set(a) | set(b)) == 5  # the one unseen question was used first


def test_dedup_is_per_user(full_client):
    ha = headers(full_client)
    hb = auth(register(full_client, "other@example.com", "Other"))
    _question_ids(full_client, ha, start(full_client, ha, subject="English", difficulty="easy", n=5)["interview"]["id"])
    # user B has never been asked anything, so all 5 easy questions are fresh for them
    b = start(full_client, hb, subject="English", difficulty="easy", n=5)
    assert b["total_questions"] == 5


def test_topic_restricted_interview(full_client):
    h = headers(full_client)
    r = full_client.post(
        "/api/interviews/start",
        json={"subject": "English", "difficulty": "mixed", "num_questions": 3, "duration_minutes": 20, "topic": "grammar"},
        headers=h,
    )
    assert r.status_code == 201 and r.json()["question"]["topic"] == "Grammar"


def test_topic_with_too_few_questions_is_a_clear_400(full_client):
    h = headers(full_client)
    r = full_client.post(
        "/api/interviews/start",
        json={"subject": "English", "difficulty": "mixed", "num_questions": 10, "duration_minutes": 20, "topic": "Grammar"},
        headers=h,
    )
    assert r.status_code == 400 and "English / Grammar" in r.json()["detail"]
    r = full_client.post(
        "/api/interviews/start",
        json={"subject": "English", "num_questions": 1, "duration_minutes": 20, "topic": "Nope"},
        headers=h,
    )
    assert r.status_code == 400


def test_dedup_window_is_exactly_the_last_five_interviews(full_client):
    """16 English questions, 3 per interview: the window slides over the latest 5 interviews."""
    h = headers(full_client)
    runs = [
        _question_ids(full_client, h, start(full_client, h, subject="English", n=3)["interview"]["id"])
        for _ in range(5)
    ]
    assert len({q for r in runs for q in r}) == 15  # five interviews, no repeats at all

    sixth = _question_ids(full_client, h, start(full_client, h, subject="English", n=3)["interview"]["id"])
    never_seen = set(range(1, 10_000)) - {q for r in runs for q in r}  # only 1 English id is unseen
    fresh6 = [q for q in sixth if q not in {x for r in runs for x in r}]
    assert len(fresh6) == 1 and fresh6[0] in never_seen  # the single unseen question is used first
    stale6 = [q for q in sixth if q not in fresh6]
    assert set(stale6) <= set(runs[0])  # the rest come from the OLDEST interview, not from 2-5
    assert not set(sixth) & {q for r in runs[1:] for q in r}

    seventh = _question_ids(full_client, h, start(full_client, h, subject="English", n=3)["interview"]["id"])
    window = {q for r in runs[1:] for q in r} | set(sixth)  # last five = interviews 2..6
    outside = [q for q in seventh if q not in window]
    assert len(outside) == 1 and outside[0] in runs[0]  # interview 1 has slid out of the window
    assert set(q for q in seventh if q in window) <= set(runs[1])  # remaining picks: oldest in window
