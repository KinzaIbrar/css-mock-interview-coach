import json

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

import app.models  # noqa: F401
from app.database.migrate import _config, run_migrations
from app.database.session import Base
from tests.test_dataset_validation import good


@pytest.fixture()
def url(tmp_path):
    return f"sqlite:///{(tmp_path / 'migr.db').as_posix()}"


def columns(url, table):
    engine = create_engine(url)
    try:
        return {c["name"] for c in inspect(engine).get_columns(table)}
    finally:
        engine.dispose()


def version(url):
    engine = create_engine(url)
    try:
        with engine.connect() as c:
            return c.execute(text("select version_num from alembic_version")).scalar()
    finally:
        engine.dispose()


def test_fresh_database_migrates_to_head(url):
    run_migrations(url)
    engine = create_engine(url)
    tables = set(inspect(engine).get_table_names())
    engine.dispose()
    assert {"users", "questions", "interviews", "answers", "evaluations", "feedback", "progress"} <= tables
    assert {"evaluation_criteria", "tags", "explanation"} <= columns(url, "questions")
    assert version(url) == "0002"


def test_migrations_match_the_models_exactly(url):
    """If someone edits a model without writing a migration, this fails."""
    run_migrations(url)
    engine = create_engine(url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert diff == []


def test_run_migrations_is_idempotent(url):
    run_migrations(url)
    run_migrations(url)
    assert version(url) == "0002"


def test_legacy_phase3_database_is_upgraded_without_data_loss(url):
    """A DB created before Alembic existed (no alembic_version) is adopted, not deleted."""
    command.upgrade(_config(url), "0001")  # produces exactly the Phase 3 schema
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("drop table alembic_version"))  # simulate create_all-era database
        conn.execute(
            text(
                "insert into questions (source_id, subject, topic, difficulty, text, reference_answer, keywords,"
                " is_sample, created_at, updated_at) values ('old-001','English','Grammar','easy','Old question text here',"
                "'old answer','[\"a\"]',1,'2024-01-01','2024-01-01')"
            )
        )
        conn.execute(
            text(
                "insert into users (email, full_name, hashed_password, is_active, preferences, created_at, updated_at)"
                " values ('legacy@example.com','Legacy','x',1,'{}','2024-01-01','2024-01-01')"
            )
        )
    assert "tags" not in columns(url, "questions")
    engine.dispose()

    run_migrations(url)

    assert {"evaluation_criteria", "tags", "explanation"} <= columns(url, "questions")
    assert version(url) == "0002"
    engine = create_engine(url)
    with engine.connect() as conn:
        row = conn.execute(text("select text, tags, explanation from questions where source_id='old-001'")).one()
        assert row.text == "Old question text here" and json.loads(row.tags) == [] and row.explanation == ""
        assert conn.execute(text("select count(*) from users")).scalar() == 1
    engine.dispose()


def test_legacy_rows_are_filled_in_by_the_next_dataset_load(url, tmp_path):
    from sqlalchemy.orm import sessionmaker

    from app.models.question import Question
    from app.services.question_service import seed_questions

    run_migrations(url)
    f = tmp_path / "q.json"
    f.write_text(json.dumps({"questions": [good(id="old-001")]}), encoding="utf-8")
    engine = create_engine(url)
    with sessionmaker(bind=engine)() as db:
        db.add(Question(source_id="old-001", subject="English", topic="x", difficulty="easy", text="old", reference_answer="", keywords=[]))
        db.commit()
        seed_questions(db, f)
        q = db.query(Question).filter_by(source_id="old-001").one()
        assert q.tags == ["testing"] and q.explanation
    engine.dispose()


def test_downgrade_removes_the_new_columns(url):
    run_migrations(url)
    command.downgrade(_config(url), "0001")
    assert not ({"evaluation_criteria", "tags", "explanation"} & columns(url, "questions"))
    assert version(url) == "0001"
    run_migrations(url)  # and upgrading again works
    assert "tags" in columns(url, "questions")
