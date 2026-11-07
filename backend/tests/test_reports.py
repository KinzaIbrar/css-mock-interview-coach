from tests.conftest import run_full_interview, start


def test_report_after_completion(client, user_a):
    done = run_full_interview(client, user_a, n=3)
    r = client.get(f"/api/reports/{done['interview']['id']}", headers=user_a)
    assert r.status_code == 200
    rep = r.json()
    assert set(rep["criteria_scores"]) == {
        "relevance", "subject_knowledge", "accuracy", "reasoning", "structure", "clarity"
    }
    assert len(rep["questions"]) == 3
    assert rep["summary"] and rep["improvements"]
    assert all(q["model_answer"] for q in rep["questions"])
    assert rep == done


def test_report_is_clearly_labelled_as_not_ai(client, user_a):
    rep = run_full_interview(client, user_a, n=2)
    assert rep["is_ai_generated"] is False
    assert rep["evaluation_source"] == "dev_heuristic"
    assert "NOT by an AI" in rep["notice"] or "NOT" in rep["notice"]
    assert "unverified" in rep["reference_notice"]


def test_report_before_completion_is_409(client, user_a):
    iid = start(client, user_a, n=2)["interview"]["id"]
    assert client.get(f"/api/reports/{iid}", headers=user_a).status_code == 409


def test_report_404_for_missing(client, user_a):
    assert client.get("/api/reports/424242", headers=user_a).status_code == 404


def test_good_answer_scores_higher_than_poor_answer(client, user_a):
    good = run_full_interview(client, user_a, n=1)
    poor = run_full_interview(client, user_a, n=1, answer="I do not know much about this topic really")
    assert good["overall_score"] > poor["overall_score"]
    assert poor["weaknesses"]


def test_perfect_keyword_answer_is_not_penalised_for_missing_info(client, user_a, db_session):
    from app.models.question import Question

    with db_session() as db:
        q = db.query(Question).filter_by(source_id="en-001").one()
        text = (
            "A simile is a comparison using like or as, for example as brave as a lion. "
            "A metaphor is a direct comparison without like or as. Both are a figure of speech. "
            "Therefore the key difference is the explicit comparison word."
        )
        from app.services.dev_evaluator import evaluate

        ev = evaluate(q, text)
    assert ev["missing_info"] == []
    assert ev["overall"] > 50
