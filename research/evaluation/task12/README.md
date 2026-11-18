# Task 12 — Controlled RAG Evaluation: Methodology & Reproducibility

**Terminology:** CSS = Central Superior Services Examination (Pakistan, FPSC) throughout.

This is a research/evaluation directory, separate from production interview content. Nothing here is
read by the running app; `data/questions/*.json` was never touched.

## Dataset (`evaluation_dataset.jsonl`), v1, built 2026-11-18

**32 scenarios.** 28 reuse real questions/reference answers/criteria straight from
`data/questions/*.json` (the exact production schema fields: `question`, `expected_answer`,
`evaluation_criteria`, `important_concepts`) — `question_source: "production_dataset"`. 4 cover Political
Science and General Science & Ability, which exist in the RAG knowledge base's syllabus but have **no**
production questions to draw from; these are marked `question_source: "evaluation_only_not_production"`,
clearly labelled unverified (never added to `data/questions/`), built in the same schema shape for
consistency only.

**Subject coverage** (4 scenarios each unless noted): Pakistan Affairs, Current Affairs, Governance and
Constitutional Studies, International Relations, English, General Knowledge, Islamic Studies, Political
Science (2), General Science and Ability (2).

**Answer-quality types** (all 7 requested, each used 3-9 times): strong/well-supported, partially
correct, weak/superficial, factually incorrect, unsupported claims, valid alternative argument, correct-
but-different-terminology. Every candidate answer was **hand-written for this task**, grounded in the
real reference answer's facts/concepts, and never copied from a retrieved RAG passage (the passages
weren't looked at until the separate Phase 4 retrieval step, run afterward, against the frozen
question/answer text — so the dataset cannot be dependent on retrieval wording).

**`expected_rag_relevance`** per scenario is a *prediction*, made from this project's own Task 8-10
evidence where available (e.g. the Montesquieu/separation-of-powers case) and informed guesses
elsewhere — **and real Phase 4 retrieval sometimes contradicted it** (see `retrieval_relevance.csv` and
`FINAL_REPORT.md`); that's reported honestly, not smoothed over.

## Reproducing Phase 4 (retrieval relevance)

```
cd backend
.venv\Scripts\python <path-to>\task12_phase4_retrieval.py   # queries the real approved baseline, read-only
```

Against `research/colab/output_promoted_baseline/InterviewIQ_Dataset/08_Embeddings/` only. The original
979-chunk baseline and Task 10's rejected 1,085-chunk experimental index were never touched or used.

## Reproducing Phase 7 (performance)

Same approach as Task 11's `rag_perf_measure.py`, re-run fresh for this task; see
`performance_results.csv` for both sessions' numbers side by side.

## What's NOT reproducible right now: Phases 3/5/6 (the A/B comparison)

Gemini (`gemini-3.8-flash`) returned HTTP 503 "high demand... temporary" on 3 independent attempts this
session. See `ab_results.jsonl` (32 rows, all `status: "blocked_gemini_unavailable"`, every score field
`null`) and `FINAL_REPORT.md` for the full account. **Re-run the same script once Gemini is reachable**
-- the dataset, harness and methodology are otherwise ready to go.

## Files

- `evaluation_dataset.jsonl` — the 32 scenarios.
- `retrieval_raw.json` — raw top-3 FAISS hits per scenario (scores, chunk IDs, full metadata).
- `retrieval_relevance.csv` — the same hits with human (developer) relevance judgments added.
- `ab_results.jsonl` — scenario-level A/B result rows, all blocked (see above).
- `performance_results.csv` — resource/latency measurements, Task 11 and Task 12 sessions.
- `failure_analysis.md` — Phase 8 robustness/negative-testing results, including one real gap found.
- `FINAL_REPORT.md` — the complete synthesis and GO/CONDITIONAL GO/NO-GO decision.

Nothing here is an API key, secret, or large binary; no FAISS index or model cache is stored in this
directory (only read from the existing approved baseline path, elsewhere, already git-ignored).
