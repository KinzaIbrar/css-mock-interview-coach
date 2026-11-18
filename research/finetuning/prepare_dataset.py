"""Task 18: prepares a fine-tuning-ready dataset from the EXISTING, already-curated question bank
(data/questions/*.json, 112 entries) -- no new content generated, no RAG/evaluation data touched.

Reuses the exact production prompt contract from backend/scripts/generate_questions.py (SYSTEM_PROMPT +
build_prompt) so the "input" side of every training example matches what the real app actually sends
Gemini today, and the "output" side is the exact QuestionDraft JSON shape the model is asked to return --
this makes the dataset directly usable the moment real tuning access exists, with zero reformatting.

Quality checks performed (not assumed): exact-duplicate questions, near-duplicate questions (normalized
string overlap), schema-field completeness and length compliance against QuestionDraft's own
constraints, per-subject/difficulty balance. Deterministic 80/10/10 train/val/test split, stratified by
subject, seeded (reproducible).
"""

import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from scripts.generate_questions import SYSTEM_PROMPT, build_prompt  # noqa: E402

QUESTIONS_DIR = ROOT / "data" / "questions"
OUT_DIR = Path(__file__).parent
SEED = 42

FIELD_MIN_LENGTHS = {
    "question": 15, "topic": 2, "expected_answer": 40, "explanation": 20,
}
FIELD_MIN_LIST_LENGTHS = {"important_concepts": 3, "evaluation_criteria": 2, "tags": 1}


def load_all():
    items = []
    for f in sorted(QUESTIONS_DIR.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        rows = data if isinstance(data, list) else data.get("questions", data)
        for r in rows:
            r["_source_file"] = f.name
            items.append(r)
    return items


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def quality_report(items: list[dict]) -> dict:
    report = {"total": len(items), "missing_fields": [], "short_fields": [], "exact_duplicates": [], "near_duplicates": []}

    seen_exact: dict[str, str] = {}
    norm_to_id: dict[str, str] = {}
    for it in items:
        qid = it.get("id", "?")
        for field, min_len in FIELD_MIN_LENGTHS.items():
            val = it.get(field)
            if not val:
                report["missing_fields"].append((qid, field))
            elif len(val) < min_len:
                report["short_fields"].append((qid, field, len(val), min_len))
        for field, min_n in FIELD_MIN_LIST_LENGTHS.items():
            val = it.get(field)
            if not val:
                report["missing_fields"].append((qid, field))
            elif len(val) < min_n:
                report["short_fields"].append((qid, field, len(val), min_n))

        q_norm = normalize(it.get("question", ""))
        if q_norm in seen_exact:
            report["exact_duplicates"].append((qid, seen_exact[q_norm]))
        else:
            seen_exact[q_norm] = qid

        # near-duplicate: same normalized question minus trailing punctuation/articles, or >=90% token overlap
        tokens = set(q_norm.split())
        for other_norm, other_id in norm_to_id.items():
            if other_id == qid:
                continue
            other_tokens = set(other_norm.split())
            if not tokens or not other_tokens:
                continue
            overlap = len(tokens & other_tokens) / max(len(tokens), len(other_tokens))
            if overlap >= 0.85 and q_norm != other_norm:
                report["near_duplicates"].append((qid, other_id, round(overlap, 2)))
        norm_to_id[q_norm] = qid

    report["by_subject"] = dict(Counter(it["subject"] for it in items))
    report["by_difficulty"] = dict(Counter(it["difficulty"] for it in items))
    return report


def to_training_example(item: dict, existing_for_subject: list[str]) -> dict:
    """Matches the real production contract: SYSTEM_PROMPT + build_prompt() as input, the QuestionDraft
    JSON (the fields Gemini is actually asked to return) as the target output."""
    prompt = build_prompt(
        subject=item["subject"], topic=item["topic"], difficulty=item["difficulty"],
        count=1, existing_questions=existing_for_subject, notes=None,
    )
    output = {
        "question": item["question"], "topic": item["topic"], "difficulty": item["difficulty"],
        "expected_answer": item["expected_answer"], "important_concepts": item["important_concepts"],
        "evaluation_criteria": item["evaluation_criteria"], "tags": item["tags"], "explanation": item["explanation"],
    }
    return {
        "systemInstruction": SYSTEM_PROMPT,
        "input": prompt,
        "output": json.dumps({"questions": [output]}, ensure_ascii=False),
        "metadata": {"id": item.get("id"), "subject": item["subject"], "difficulty": item["difficulty"]},
    }


def main():
    items = load_all()
    report = quality_report(items)

    # Stratified 80/10/10 split by subject, deterministic.
    rng = random.Random(SEED)
    by_subject: dict[str, list[dict]] = {}
    for it in items:
        by_subject.setdefault(it["subject"], []).append(it)

    train, val, test = [], [], []
    for subject, rows in by_subject.items():
        rows = rows[:]
        rng.shuffle(rows)
        n = len(rows)
        n_val = max(1, round(n * 0.1))
        n_test = max(1, round(n * 0.1))
        test.extend(rows[:n_test])
        val.extend(rows[n_test:n_test + n_val])
        train.extend(rows[n_test + n_val:])

    def write_split(name: str, rows: list[dict]):
        existing_by_subject: dict[str, list[str]] = {}
        out_path = OUT_DIR / f"{name}.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for it in rows:
                subj = it["subject"]
                existing = existing_by_subject.setdefault(subj, [])
                f.write(json.dumps(to_training_example(it, existing), ensure_ascii=False) + "\n")
                existing.append(it["question"])
        return out_path

    paths = {name: write_split(name, rows) for name, rows in (("train", train), ("val", val), ("test", test))}

    report["split_counts"] = {"train": len(train), "val": len(val), "test": len(test)}
    report["split_by_subject"] = {
        name: dict(Counter(it["subject"] for it in rows))
        for name, rows in (("train", train), ("val", val), ("test", test))
    }
    (OUT_DIR / "dataset_quality_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Total items: {report['total']}")
    print(f"Missing fields: {len(report['missing_fields'])}")
    print(f"Short fields: {len(report['short_fields'])}")
    print(f"Exact duplicates: {len(report['exact_duplicates'])}")
    print(f"Near duplicates (>=85% token overlap): {len(report['near_duplicates'])}")
    print(f"Split: {report['split_counts']}")
    for name, path in paths.items():
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
