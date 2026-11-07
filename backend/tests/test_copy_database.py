import pytest
from sqlalchemy import create_engine, select

from app.database.migrate import run_migrations
from app.models.interview import Interview
from app.models.question import Question
from app.models.user import User
from scripts.copy_database import copy


def test_copy_moves_data_and_refuses_a_non_empty_target(tmp_path):
    src, dst = f"sqlite:///{(tmp_path / 's.db').as_posix()}", f"sqlite:///{(tmp_path / 't.db').as_posix()}"
    run_migrations(src)
    e = create_engine(src)
    from sqlalchemy.orm import Session

    with Session(e) as db:
        u = User(email="a@example.com", full_name="A", hashed_password="x", is_active=True, preferences={})
        db.add(u); db.flush()
        db.add(Question(source_id="q-1", subject="English", topic="Grammar", difficulty="easy", text="Q?", reference_answer="A",
                        keywords=["a"], evaluation_criteria=[], tags=[], explanation="", is_sample=True))
        db.flush()
        db.add(Interview(user_id=u.id, subject="English", difficulty="mixed", num_questions=1, duration_minutes=10, mode="mock",
                         status="in_progress", current_index=0, question_ids=[1]))
        db.commit()
    counts = copy(src, dst)
    assert counts["users"] == 1 and counts["interviews"] == 1 and counts["questions"] == 1
    with create_engine(dst).connect() as c:
        assert c.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
    with Session(create_engine(dst)) as db:
        assert db.scalar(select(User.email)) == "a@example.com"
    with pytest.raises(SystemExit, match="refusing"):
        copy(src, dst)


def test_copy_accepts_a_target_already_seeded_with_the_same_questions(tmp_path):
    from sqlalchemy.orm import Session

    src, dst = f"sqlite:///{(tmp_path / 's.db').as_posix()}", f"sqlite:///{(tmp_path / 't.db').as_posix()}"
    for url in (src, dst):
        run_migrations(url)
        with Session(create_engine(url)) as db:
            db.add(Question(id=1, source_id="q-1", subject="English", topic="G", difficulty="easy", text="Q?", reference_answer="A",
                            keywords=[], evaluation_criteria=[], tags=[], explanation="", is_sample=True))
            db.commit()
    with Session(create_engine(src)) as db:
        u = User(email="a@example.com", full_name="A", hashed_password="x", is_active=True, preferences={})
        db.add(u); db.commit()
    assert copy(src, dst)["users"] == 1
