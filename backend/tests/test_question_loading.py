import json

import pytest

from app.core.config import settings
from app.models.question import Question
from app.rag import DatasetError
from app.services.question_service import seed_questions
from tests.test_dataset_validation import good


def test_seed_loads_every_record_with_all_fields(full_db_session):
    with full_db_session() as db:
        assert db.query(Question).count() == 112
        q = db.query(Question).filter_by(source_id="pa-002").one()
        assert q.subject == "Pakistan Affairs" and q.difficulty == "medium"
        assert q.reference_answer.startswith("Passed by the first Constituent Assembly")  # expected_answer
        assert "objectives resolution" in q.keywords  # important_concepts
        assert len(q.evaluation_criteria) >= 2 and q.tags and q.explanation
        assert q.is_sample is True


def test_seed_is_idempotent(full_db_session):
    with full_db_session() as db:
        assert seed_questions(db, settings.questions_path) == 112
        assert seed_questions(db, settings.questions_path) == 112
        assert db.query(Question).count() == 112
        assert db.query(Question.source_id).distinct().count() == 112


def test_reseed_updates_changed_records_in_place(db_session, tmp_path):
    f = tmp_path / "q.json"
    f.write_text(json.dumps({"questions": [good()]}), encoding="utf-8")
    with db_session() as db:
        seed_questions(db, f)
        original_id = db.query(Question).filter_by(source_id="zz-001").one().id
        f.write_text(json.dumps({"questions": [good(topic="Changed topic", tags=["new"])]}), encoding="utf-8")
        seed_questions(db, f)
        q = db.query(Question).filter_by(source_id="zz-001").one()
        assert q.id == original_id  # same row: existing interview references stay valid
        assert q.topic == "Changed topic" and q.tags == ["new"]


def test_seed_with_missing_dataset_is_tolerated(db_session, tmp_path):
    with db_session() as db:
        before = db.query(Question).count()
        assert seed_questions(db, tmp_path / "missing") == 0
        assert db.query(Question).count() == before


def test_seed_rejects_invalid_dataset_and_leaves_db_untouched(db_session, tmp_path):
    f = tmp_path / "bad.json"
    f.write_text(json.dumps({"questions": [good(difficulty="extreme")]}), encoding="utf-8")
    with db_session() as db:
        before = db.query(Question).count()
        with pytest.raises(DatasetError):
            seed_questions(db, f)
        assert db.query(Question).count() == before


def test_duplicate_detection_blocks_seeding(db_session, tmp_path):
    f = tmp_path / "dup.json"
    f.write_text(json.dumps({"questions": [good(), good(id="zz-002")]}), encoding="utf-8")  # same text
    with db_session() as db:
        with pytest.raises(DatasetError, match="duplicate"):
            seed_questions(db, f)
