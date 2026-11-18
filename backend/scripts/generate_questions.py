"""Draft new CSS interview questions with Gemini, in the exact shape `app.rag.dataset.QuestionRecord` expects.

This never writes into the live dataset (`data/questions/*.json`) directly. It writes a reviewable
draft file under `data/questions/_drafts/`, which `app.rag.dataset.read_raw_items` never picks up
(it only globs `*.json` in `data/questions/` itself), so nothing here reaches the running app until a
human reviews the draft and merges entries into the real subject file by hand.

    cd backend
    .venv\\Scripts\\python -m scripts.generate_questions --subject "Current Affairs" --topic "Climate Policy" --count 5

Requires GEMINI_API_KEY in backend/.env (same as scripts/check_gemini.py). Exits 1 if Gemini is not
configured, the call fails, or the draft fails validation (duplicates / near-duplicates / schema errors).
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from app.agents import runtime
from app.agents.errors import LLMError
from app.core.config import settings
from app.core.constants import QUESTION_DIFFICULTIES, SUBJECTS
from app.rag.dataset import read_raw_items, validate_records

SUBJECT_FILES = {
    "Pakistan Affairs": ("pakistan_affairs.json", "pa"),
    "Current Affairs": ("current_affairs.json", "ca"),
    "Islamic Studies": ("islamic_studies.json", "is"),
    "General Knowledge": ("general_knowledge.json", "gk"),
    "English": ("english.json", "en"),
    "International Relations": ("international_relations.json", "ir"),
    "Governance and Constitutional Studies": ("governance_constitutional_studies.json", "gc"),
}
assert set(SUBJECT_FILES) == set(SUBJECTS)


class QuestionDraft(BaseModel):
    question: str = Field(min_length=15)
    topic: str = Field(min_length=2)
    difficulty: str
    expected_answer: str = Field(min_length=40)
    important_concepts: list[str] = Field(min_length=3)
    evaluation_criteria: list[str] = Field(min_length=2)
    tags: list[str] = Field(min_length=1)
    explanation: str = Field(min_length=20)


class DraftBatch(BaseModel):
    questions: list[QuestionDraft]


SYSTEM_PROMPT = """You are drafting PRACTICE questions for a CSS (Pakistan) mock-interview study tool.

Rules you must follow:
- These are unverified study aids, not official FPSC material. Never claim a question was actually
  asked in a real CSS interview, and never cite a source as if it were official or authoritative.
- Do not invent statistics, dates, or events; if a fact is not well-established, phrase the question
  so the candidate explains concepts/reasoning rather than requiring you to assert a disputed figure.
- Each `expected_answer` is a model study answer (a few sentences, not bullet points), not a transcript
  of what a real candidate said.
- Return ONLY the fields requested, matching the schema exactly."""


def build_prompt(subject: str, topic: str, difficulty: str, count: int, existing_questions: list[str], notes: str | None) -> str:
    avoid = "\n".join(f"- {q}" for q in existing_questions) or "(none yet)"
    extra = f"\nAdditional guidance from the question-bank maintainer: {notes}\n" if notes else ""
    return f"""Generate exactly {count} CSS interview practice question(s) for:
Subject: {subject}
Topic: {topic}
Difficulty: {difficulty}
{extra}
Do not duplicate or closely paraphrase any of these existing questions for this subject:
{avoid}

For each question provide:
- question: the interview question text
- topic: a short topic label (2-4 words)
- difficulty: must be exactly "{difficulty}"
- expected_answer: a model answer of 2-5 sentences a well-prepared candidate could give
- important_concepts: at least 3 distinct key terms/concepts the answer should cover
- evaluation_criteria: at least 2 criteria an evaluator would check for
- tags: at least 1 short lowercase-hyphenated tag
- explanation: 1-2 sentences on what the question tests and how to structure a strong answer"""


def next_ids(prefix: str, existing_ids: list[str], count: int) -> list[str]:
    nums = [int(i.split("-")[1]) for i in existing_ids if i.startswith(prefix + "-")]
    start = (max(nums) + 1) if nums else 1
    return [f"{prefix}-{n:03d}" for n in range(start, start + count)]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", required=True, choices=SUBJECTS)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--difficulty", default="medium", choices=QUESTION_DIFFICULTIES)
    parser.add_argument("--notes", default=None, help="Extra guidance appended to the prompt")
    args = parser.parse_args(argv[1:])

    provider = runtime.get_provider()
    if provider is None:
        print("GEMINI_API_KEY is not set in backend/.env: nothing to generate (dev fallback has no drafting mode).")
        return 1

    filename, prefix = SUBJECT_FILES[args.subject]
    dataset_path = settings.questions_path
    existing_raw = read_raw_items(dataset_path)
    existing_for_subject = [q for q in existing_raw if q.get("subject") == args.subject]
    existing_ids = [q["id"] for q in existing_for_subject]
    existing_questions = [q["question"] for q in existing_for_subject]

    prompt = build_prompt(args.subject, args.topic, args.difficulty, args.count, existing_questions, args.notes)
    print(f"provider: {type(provider).__name__} | model: {provider.model}")
    try:
        batch = provider.generate_json(system=SYSTEM_PROMPT, prompt=prompt, schema=DraftBatch)
    except LLMError as exc:
        print(f"Gemini call failed: {exc}")
        return 1

    ids = next_ids(prefix, existing_ids, len(batch.questions))
    new_items = [
        {
            "id": qid,
            "subject": args.subject,
            "is_sample": True,
            **draft.model_dump(),
        }
        for qid, draft in zip(ids, batch.questions)
    ]

    report = validate_records(existing_raw + new_items)
    new_id_set = set(ids)
    relevant_errors = [e for e in report.errors if any(nid in e for nid in new_id_set)] or report.errors
    if relevant_errors:
        print(f"\n{len(relevant_errors)} VALIDATION ISSUE(S) in the draft:")
        for e in relevant_errors:
            print(f"  - {e}")

    out_dir = dataset_path / "_drafts"
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"{Path(filename).stem}_draft_{stamp}.json"
    status = "AI-DRAFT (Gemini) — NOT reviewed, NOT loaded by the app. Verify facts, resolve any issues printed above, then merge by hand into " + filename + "."
    if relevant_errors:
        status += " CONTAINS VALIDATION ISSUES — fix before merging."
    out_path.write_text(
        json.dumps({"meta": {"subject": args.subject, "status": status}, "questions": new_items}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nWrote {len(new_items)} draft question(s) to {out_path}")
    return 1 if relevant_errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
