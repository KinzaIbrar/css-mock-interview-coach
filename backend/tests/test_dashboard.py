import pytest

from tests.conftest import GOOD_ANSWER, run_full_interview, start


def test_new_user_dashboard_is_empty_not_fabricated(client, user_a):
    d = client.get("/api/dashboard", headers=user_a).json()
    assert d["total_interviews"] == 0
    assert d["average_score"] is None and d["best_score"] is None and d["weakest_subject"] is None
    assert d["score_trend"] == [] and d["subject_performance"] == [] and d["recent_interviews"] == []
    assert d["recommendations"][0]["title"].startswith("Start your first")
    assert d["is_ai_generated"] is False


def test_dashboard_stats_come_from_saved_interviews(client, user_a):
    r1 = run_full_interview(client, user_a, subject="Pakistan Affairs", n=3)
    r2 = run_full_interview(client, user_a, subject="English", n=1, answer="short answer here ok")
    d = client.get("/api/dashboard", headers=user_a).json()
    scores = [r1["overall_score"], r2["overall_score"]]
    assert d["total_interviews"] == 2
    assert d["best_score"] == max(scores)
    assert d["average_score"] == pytest.approx(sum(scores) / 2, abs=0.1)
    assert d["weakest_subject"] == ("English" if r2["overall_score"] < r1["overall_score"] else "Pakistan Affairs")
    assert {s["subject"] for s in d["subject_performance"]} == {"Pakistan Affairs", "English"}
    assert [t["interview_id"] for t in d["score_trend"]] == [r1["interview"]["id"], r2["interview"]["id"]]
    assert len(d["recent_interviews"]) == 2


def test_dashboard_counts_in_progress_separately(client, user_a):
    start(client, user_a, n=2)
    d = client.get("/api/dashboard", headers=user_a).json()
    assert d["total_interviews"] == 0 and d["in_progress_count"] == 1
    assert len(d["recent_interviews"]) == 1
    assert any(r["title"].startswith("Resume") for r in d["recommendations"])


def test_progress_aggregates_per_subject(client, user_a):
    a = run_full_interview(client, user_a, subject="Pakistan Affairs", n=1)
    b = run_full_interview(client, user_a, subject="Pakistan Affairs", n=1, answer="a very short reply sorry")
    p = client.get("/api/progress", headers=user_a).json()
    assert p["total_completed"] == 2
    [subj] = p["subjects"]
    assert subj["subject"] == "Pakistan Affairs" and subj["sessions_count"] == 2
    assert subj["best_score"] == max(a["overall_score"], b["overall_score"])
    assert subj["last_score"] == b["overall_score"]
    assert subj["avg_score"] == pytest.approx((a["overall_score"] + b["overall_score"]) / 2, abs=0.1)
    assert len(p["trend"]) == 2


def test_progress_empty_for_new_user(client, user_a):
    p = client.get("/api/progress", headers=user_a).json()
    assert p == {"total_completed": 0, "overall_average": None, "subjects": [], "trend": []}


def test_answer_with_dev_text_does_not_crash_on_long_input(client, user_a):
    iid = start(client, user_a, n=1)["interview"]["id"]
    r = client.post("/api/interviews/answer", json={"interview_id": iid, "answer_text": GOOD_ANSWER * 20}, headers=user_a)
    assert r.status_code == 200
