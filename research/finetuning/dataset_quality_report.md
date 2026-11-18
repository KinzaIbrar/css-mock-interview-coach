# Task 18 — Dataset Quality Report

**Source:** `data/questions/*.json` (112 entries, 7 subjects × 16 each) — the existing, already-curated
production question bank. No new data generated; no RAG/evaluation artifacts touched.

## Automated checks (via `prepare_dataset.py`, real validation, not assumed)

| Check | Result |
|---|---|
| Missing required fields (`question`, `topic`, `expected_answer`, `important_concepts`, `evaluation_criteria`, `tags`, `explanation`) | **0** |
| Fields below `QuestionDraft`'s own minimum-length constraints | **0** |
| Exact-duplicate questions (normalized) | **0** |
| Near-duplicate questions (≥85% token overlap, cross-subject and within-subject) | **0** |
| Subject balance | Perfectly even: 16/16/16/16/16/16/16 |

The dataset is clean as-is — it already passed `app.rag.validate` in production, and this pass adds
duplicate/near-duplicate and length-constraint checks specific to fine-tuning suitability, finding
nothing to fix.

## A second candidate dataset was considered and found NOT suitable: answer-evaluation examples

Checked for real (non-synthetic) Gemini-scored evaluation examples to fine-tune an evaluator on:
- `backend/app.db`: **2 evaluation rows total, both `source=dev_heuristic`, `is_ai_generated=0`.**
  Zero real Gemini-generated scores exist anywhere in this project's actual database.
- `research/evaluation/task12/evaluation_dataset.jsonl` (32 hand-written scenarios): has candidate
  answers and a human-assigned `answer_quality_label` (e.g. "strong_well_supported"), but **no numeric
  4-dimension scores** — Task 12's live-Gemini A/B comparison was blocked by a real API outage (see
  `research/evaluation/task12/FINAL_REPORT.md`), so no reference scores were ever produced for these.

**Conclusion: there is no real ground-truth-scored dataset in this project suitable for fine-tuning an
evaluation/scoring model.** Producing one would require either genuine Gemini calls (consuming quota,
and Gemini has repeatedly been unavailable per `PROJECT_STATUS.md`'s own history) or human expert
scoring (no reviewer available, consistent with every prior task's documented limitation). This is
reported as a real, current gap — not worked around with a weaker substitute.

## What IS fine-tuning-ready: the 112-question bank, reformatted to the real production contract

`prepare_dataset.py` converts each entry into `{systemInstruction, input, output}`, where
`systemInstruction`/`input` are **exactly** `backend/scripts/generate_questions.py`'s own
`SYSTEM_PROMPT`/`build_prompt()` output (not a reinterpretation), and `output` is the exact
`QuestionDraft` JSON shape Gemini is already asked to return in production. This means the dataset is
usable the moment real tuning access exists, with zero reformatting.

**Split** (stratified by subject, seeded, deterministic — `SEED=42`): 84 train / 14 validation / 14 test
(≈75/12.5/12.5%, not quite 80/10/10 due to 7 subjects × 16 rounding to whole numbers per subject).

**Honest limitation**: Google's own supervised-tuning guidance recommends "at least 100 to 500 examples"
for best results; our 84-example train split is **below** that threshold. The dataset is clean, but its
*size* is a real constraint on how well any tuning run would generalize — flagged here, not hidden.
