"""Curated question dataset: record schema, validation and loading.

The dataset lives in `data/questions/*.json` (one file per subject) as
`{"meta": {...}, "questions": [ {...}, ... ]}`. Validation is strict so that mistakes in hand-written
content (typos in field names, duplicate ids, empty answers, invalid subjects) fail loudly at load time.

Dataset field -> database column: id->source_id, question->text, expected_answer->reference_answer,
important_concepts->keywords. The other fields keep their names.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.core.constants import QUESTION_DIFFICULTIES, SUBJECTS

ID_PATTERN = re.compile(r"^[a-z][a-z0-9]{1,5}-\d{3}$")  # e.g. pa-001
NEAR_DUPLICATE_JACCARD = 0.85
MIN_QUESTIONS_PER_SUBJECT_DIFFICULTY = 2  # warning threshold only


class DatasetError(Exception):
    """Raised when the dataset fails validation; `errors` lists every problem found."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Question dataset is invalid ({len(errors)} problem(s)):\n- " + "\n- ".join(errors[:20]))


class QuestionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str
    question: str = Field(min_length=15)
    subject: str
    topic: str = Field(min_length=2)
    difficulty: str
    expected_answer: str = Field(min_length=40)
    important_concepts: list[str] = Field(min_length=3)
    evaluation_criteria: list[str] = Field(min_length=2)
    tags: list[str] = Field(min_length=1)
    explanation: str = Field(min_length=20)
    is_sample: bool = True

    @field_validator("id")
    @classmethod
    def valid_id(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError("id must look like 'pa-001' (lowercase prefix, hyphen, 3 digits)")
        return v

    @field_validator("subject")
    @classmethod
    def valid_subject(cls, v: str) -> str:
        if v not in SUBJECTS:
            raise ValueError(f"unknown subject {v!r}")
        return v

    @field_validator("difficulty")
    @classmethod
    def valid_difficulty(cls, v: str) -> str:
        if v not in QUESTION_DIFFICULTIES:
            raise ValueError(f"difficulty must be one of {QUESTION_DIFFICULTIES}")
        return v

    @field_validator("expected_answer", "question", "explanation")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v

    @field_validator("important_concepts", "evaluation_criteria", "tags")
    @classmethod
    def clean_string_list(cls, v: list[str]) -> list[str]:
        cleaned = [s.strip() for s in v]
        if any(not s for s in cleaned):
            raise ValueError("entries must not be empty")
        if len({s.lower() for s in cleaned}) != len(cleaned):
            raise ValueError("entries must be unique")
        return cleaned

    @field_validator("tags")
    @classmethod
    def lower_tags(cls, v: list[str]) -> list[str]:
        return [t.lower() for t in v]


@dataclass
class ValidationReport:
    records: list[QuestionRecord] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", text.lower()).strip()


def _tokens(text: str) -> set[str]:
    return set(_normalise(text).split())


def validate_records(raw_items: list[dict]) -> ValidationReport:
    """Validate raw dicts. Never raises; collects every problem so they can be fixed in one pass."""
    report = ValidationReport()
    for pos, item in enumerate(raw_items):
        label = f"#{pos + 1} ({item.get('id', '?')})" if isinstance(item, dict) else f"#{pos + 1}"
        if not isinstance(item, dict):
            report.errors.append(f"{label}: record must be an object")
            continue
        try:
            report.records.append(QuestionRecord.model_validate(item))
        except ValidationError as exc:
            for err in exc.errors():
                loc = ".".join(str(p) for p in err["loc"]) or "record"
                report.errors.append(f"{label}: {loc}: {err['msg']}")

    seen_ids: dict[str, int] = {}
    for rec in report.records:
        seen_ids[rec.id] = seen_ids.get(rec.id, 0) + 1
    for qid, count in seen_ids.items():
        if count > 1:
            report.errors.append(f"duplicate id {qid!r} appears {count} times")

    token_sets = [(r, _tokens(r.question)) for r in report.records]
    for i, (a, ta) in enumerate(token_sets):
        for b, tb in token_sets[i + 1:]:
            if a.id == b.id:
                continue
            if _normalise(a.question) == _normalise(b.question):
                report.errors.append(f"duplicate question text: {a.id} and {b.id}")
                continue
            union = ta | tb
            if union and len(ta & tb) / len(union) >= NEAR_DUPLICATE_JACCARD:
                report.errors.append(f"near-duplicate question text: {a.id} and {b.id}")

    for subject in SUBJECTS:
        if not any(r.subject == subject for r in report.records):
            report.warnings.append(f"no questions for subject {subject!r}")
            continue
        for diff in QUESTION_DIFFICULTIES:
            n = sum(1 for r in report.records if r.subject == subject and r.difficulty == diff)
            if n < MIN_QUESTIONS_PER_SUBJECT_DIFFICULTY:
                report.warnings.append(f"{subject} / {diff}: only {n} question(s)")
    return report


def read_raw_items(path: Path) -> list[dict]:
    """Read `questions` arrays from one JSON file, or from every *.json file in a directory."""
    files = sorted(path.glob("*.json")) if path.is_dir() else [path]
    if not files or not all(f.exists() for f in files):
        raise DatasetError([f"dataset not found at {path}"])
    items: list[dict] = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DatasetError([f"{f.name}: invalid JSON ({exc})"]) from exc
        if not isinstance(data, dict) or not isinstance(data.get("questions"), list):
            raise DatasetError([f"{f.name}: expected an object with a 'questions' list"])
        items.extend(data["questions"])
    return items


def load_dataset(path: Path) -> list[QuestionRecord]:
    """Load and validate; raises DatasetError listing every problem if invalid."""
    report = validate_records(read_raw_items(path))
    if not report.ok:
        raise DatasetError(report.errors)
    return report.records
