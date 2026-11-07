import copy
import json

import pytest

from app.core.config import settings
from app.core.constants import QUESTION_DIFFICULTIES, SUBJECTS
from app.rag import DatasetError, load_dataset, validate_records
from app.rag.dataset import read_raw_items
from app.rag.validate import main as validate_main


def good(**overrides) -> dict:
    base = {
        "id": "zz-001",
        "question": "What is the purpose of the test question used here?",
        "subject": "English",
        "topic": "Testing",
        "difficulty": "easy",
        "expected_answer": "The purpose of the test question is to exercise the validator with a valid record.",
        "important_concepts": ["validator", "record", "valid"],
        "evaluation_criteria": ["Mentions the validator", "Mentions the record"],
        "tags": ["Testing"],
        "explanation": "Used only by the test-suite to build valid and invalid records.",
    }
    base.update(overrides)
    return base


def errors_for(*items: dict) -> list[str]:
    return validate_records(list(items)).errors


# ---- the real curated dataset -------------------------------------------------------------------
def test_real_dataset_is_valid_and_large_enough():
    report = validate_records(read_raw_items(settings.questions_path))
    assert report.errors == []
    assert 100 <= len(report.records) <= 150


def test_real_dataset_covers_every_subject_and_difficulty():
    records = load_dataset(settings.questions_path)
    for subject in SUBJECTS:
        for difficulty in QUESTION_DIFFICULTIES:
            n = sum(1 for r in records if r.subject == subject and r.difficulty == difficulty)
            assert n >= 3, f"{subject}/{difficulty} has only {n}"


def test_real_dataset_has_unique_ids_and_questions():
    records = load_dataset(settings.questions_path)
    assert len({r.id for r in records}) == len(records)
    assert len({r.question.lower() for r in records}) == len(records)


def test_every_real_record_is_labelled_sample_and_complete():
    for r in load_dataset(settings.questions_path):
        assert r.is_sample is True  # nothing is claimed to be verified
        assert r.expected_answer.strip() and r.explanation.strip()
        assert len(r.important_concepts) >= 3 and len(r.evaluation_criteria) >= 2 and r.tags


def test_cli_ok_for_real_dataset(capsys):
    assert validate_main(["validate"]) == 0
    out = capsys.readouterr().out
    assert "OK: dataset is valid" in out and "Valid records:" in out


def test_cli_fails_for_bad_dataset(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"questions": [good(difficulty="extreme")]}), encoding="utf-8")
    assert validate_main(["validate", str(bad)]) == 1
    assert "difficulty" in capsys.readouterr().out


# ---- rule checks --------------------------------------------------------------------------------
def test_valid_record_passes_and_tags_are_lowercased():
    report = validate_records([good()])
    assert report.ok and report.records[0].tags == ["testing"]


@pytest.mark.parametrize(
    "field",
    ["id", "question", "subject", "topic", "difficulty", "expected_answer",
     "important_concepts", "evaluation_criteria", "tags", "explanation"],
)
def test_missing_required_field(field):
    item = good()
    del item[field]
    errs = errors_for(item)
    assert any(field in e for e in errs), errs


def test_unknown_field_is_rejected_to_catch_typos():
    assert any("extra" in e.lower() or "not permitted" in e.lower() for e in errors_for(good(expected_anwser="x")))


def test_duplicate_ids_detected():
    errs = errors_for(good(), good(question="A completely different question about another subject area?"))
    assert any("duplicate id" in e and "zz-001" in e for e in errs)


def test_duplicate_question_text_detected():
    errs = errors_for(good(id="zz-001"), good(id="zz-002"))
    assert any("duplicate question text" in e for e in errs)


def test_near_duplicate_question_text_detected():
    a = good(id="zz-001", question="Explain the sources of Islamic law and how they are ranked in practice")
    b = good(id="zz-002", question="Explain the sources of Islamic law and how they are ranked in practice today")
    assert any("near-duplicate" in e for e in errors_for(a, b))


def test_distinct_questions_are_not_flagged():
    a = good(id="zz-001", question="Explain the sources of Islamic law and how they are ranked")
    b = good(id="zz-002", question="Describe the structure of the federal civil service of Pakistan")
    assert errors_for(a, b) == []


@pytest.mark.parametrize("bad", ["extreme", "", "EASY", "mixed"])
def test_invalid_difficulty(bad):
    assert any("difficulty" in e for e in errors_for(good(difficulty=bad)))


@pytest.mark.parametrize("bad", ["Astrology", "", "english"])
def test_invalid_subject(bad):
    assert any("subject" in e for e in errors_for(good(subject=bad)))


@pytest.mark.parametrize("bad", ["", "   ", "too short"])
def test_empty_or_trivial_expected_answer(bad):
    assert any("expected_answer" in e for e in errors_for(good(expected_answer=bad)))


def test_evaluation_criteria_rules():
    assert any("evaluation_criteria" in e for e in errors_for(good(evaluation_criteria=[])))
    assert any("evaluation_criteria" in e for e in errors_for(good(evaluation_criteria=["only one"])))
    assert any("evaluation_criteria" in e for e in errors_for(good(evaluation_criteria=["fine", "  "])))
    assert any("unique" in e for e in errors_for(good(evaluation_criteria=["same", "Same"])))


def test_concepts_and_tags_rules():
    assert any("important_concepts" in e for e in errors_for(good(important_concepts=["a", "b"])))
    assert any("tags" in e for e in errors_for(good(tags=[])))
    assert any("tags" in e for e in errors_for(good(tags=["ok", ""])))


@pytest.mark.parametrize("bad_id", ["1", "ENG-001", "en_001", "en-1", "english-001", "en-0001"])
def test_invalid_id_format(bad_id):
    assert any("id" in e for e in errors_for(good(id=bad_id)))


def test_all_problems_reported_in_one_pass_with_record_labels():
    errs = errors_for(good(id="zz-001", difficulty="bad"), good(id="zz-002", subject="nope", expected_answer=""))
    assert any("zz-001" in e for e in errs) and any("zz-002" in e for e in errs)
    assert len(errs) >= 3


def test_non_object_record_reported():
    assert validate_records(["not a dict"]).errors


def test_coverage_warnings_do_not_fail_validation():
    report = validate_records([good()])
    assert report.ok and report.warnings  # most subjects/difficulties are empty


# ---- loading ------------------------------------------------------------------------------------
def test_load_dataset_raises_with_all_errors(tmp_path):
    f = tmp_path / "q.json"
    f.write_text(json.dumps({"questions": [good(difficulty="x"), good(id="zz-002", subject="y")]}), encoding="utf-8")
    with pytest.raises(DatasetError) as exc:
        load_dataset(f)
    assert len(exc.value.errors) >= 2


def test_load_directory_merges_files_and_detects_cross_file_duplicates(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps({"questions": [good(id="zz-001")]}), encoding="utf-8")
    (tmp_path / "b.json").write_text(
        json.dumps({"questions": [good(id="zz-002", question="Another unrelated question about governance reform?")]}),
        encoding="utf-8",
    )
    assert {r.id for r in load_dataset(tmp_path)} == {"zz-001", "zz-002"}
    (tmp_path / "c.json").write_text(json.dumps({"questions": [copy.deepcopy(good(id="zz-001"))]}), encoding="utf-8")
    with pytest.raises(DatasetError) as exc:
        load_dataset(tmp_path)
    assert any("duplicate id" in e for e in exc.value.errors)


def test_load_rejects_bad_json_and_bad_shape(tmp_path):
    f = tmp_path / "x.json"
    f.write_text("{not json", encoding="utf-8")
    with pytest.raises(DatasetError, match="invalid JSON"):
        load_dataset(f)
    f.write_text(json.dumps({"items": []}), encoding="utf-8")
    with pytest.raises(DatasetError, match="questions"):
        load_dataset(f)


def test_load_missing_path(tmp_path):
    with pytest.raises(DatasetError, match="not found"):
        load_dataset(tmp_path / "nope.json")
