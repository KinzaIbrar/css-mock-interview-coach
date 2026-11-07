from tests.conftest import GOOD_ANSWER, run_full_interview, start


def test_user_cannot_read_another_users_interview_or_report(client, user_a, user_b):
    report = run_full_interview(client, user_a, n=2)
    iid = report["interview"]["id"]
    assert client.get(f"/api/interviews/{iid}", headers=user_a).status_code == 200
    assert client.get(f"/api/interviews/{iid}", headers=user_b).status_code == 404
    assert client.get(f"/api/reports/{iid}", headers=user_b).status_code == 404


def test_user_cannot_answer_next_or_complete_another_users_interview(client, user_a, user_b):
    iid = start(client, user_a, n=2)["interview"]["id"]
    answer = {"interview_id": iid, "answer_text": GOOD_ANSWER}
    assert client.post("/api/interviews/answer", json=answer, headers=user_b).status_code == 404
    assert client.post("/api/interviews/next", json={"interview_id": iid}, headers=user_b).status_code == 404
    assert client.post("/api/interviews/complete", json={"interview_id": iid}, headers=user_b).status_code == 404
    # and the owner's interview was untouched by those attempts
    d = client.get(f"/api/interviews/{iid}", headers=user_a).json()
    assert d["answered_indexes"] == [] and d["interview"]["status"] == "in_progress"


def test_history_dashboard_and_progress_exclude_other_users(client, user_a, user_b):
    run_full_interview(client, user_a, n=2)
    start(client, user_a, subject="English", n=1)

    assert client.get("/api/interviews/history", headers=user_b).json() == []
    d = client.get("/api/dashboard", headers=user_b).json()
    assert d["total_interviews"] == 0 and d["recent_interviews"] == [] and d["subject_performance"] == []
    p = client.get("/api/progress", headers=user_b).json()
    assert p["total_completed"] == 0 and p["subjects"] == []

    assert len(client.get("/api/interviews/history", headers=user_a).json()) == 2


def test_each_user_builds_independent_progress(client, user_a, user_b):
    run_full_interview(client, user_a, subject="Pakistan Affairs", n=1)
    b = run_full_interview(client, user_b, subject="Pakistan Affairs", n=1, answer="a short reply to this one")
    pa = client.get("/api/progress", headers=user_a).json()["subjects"][0]
    pb = client.get("/api/progress", headers=user_b).json()["subjects"][0]
    assert pa["sessions_count"] == pb["sessions_count"] == 1
    assert pb["avg_score"] == b["overall_score"]
    assert pa["avg_score"] != pb["avg_score"]
