# Task 18 — Fine-Tuning Feasibility Audit and Dataset Preparation

Research only. No RAG/FAISS/question-bank/backend-runtime changes; nothing committed/pushed; no paid
cloud resources created.

## Summary

1. **Feasibility checked first, not assumed**: the plain Gemini API (what this project's
   `GEMINI_API_KEY`/`GEMINI_API_KEYS` actually authenticate against) does not currently support
   fine-tuning at all — verified via web search, not guessed. Real tuning exists only on Vertex AI, a
   separate billed platform not configured here. See `feasibility_and_integration.md`.
2. **Dataset audit**: the 112-question bank (`data/questions/*.json`) is clean (0 missing fields, 0
   duplicates/near-duplicates) and reformatted into a fine-tuning-ready split matching the real
   production prompt contract. A second candidate (real Gemini-scored evaluation examples) was checked
   and found **not to exist** — only 2 dev-heuristic rows in `app.db`, zero real AI-scored examples
   anywhere. See `dataset_quality_report.md`.
3. **No tuning job was run** — correctly, since the infrastructure/authorization don't exist. A concrete,
   accurate (verified against current docs) training config is designed and ready for when they do. See
   `training_config.json`.
4. **Integration is already compatible** with Task 17's multi-provider pool by design — a future tuned
   model needs only a new `model` identifier and one small, additive client-construction branch, no
   rewrite. See `feasibility_and_integration.md`.

## Reproducing the dataset prep

```
cd research/finetuning
..\..\backend\.venv\Scripts\python prepare_dataset.py
```

## Files

- `README.md` — this file.
- `dataset_quality_report.md` / `dataset_quality_report.json` — the real quality audit.
- `prepare_dataset.py` — the script that built the split (reuses `backend/scripts/generate_questions.py`'s own prompt contract).
- `train.jsonl` / `val.jsonl` / `test.jsonl` — the prepared, fine-tuning-ready dataset (84/14/14).
- `training_config.json` — a designed, not executed, supervised-tuning job spec.
- `feasibility_and_integration.md` — the feasibility finding, what was/wasn't done, baseline, and the integration recommendation.
