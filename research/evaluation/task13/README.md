# Task 13 — RAG Security Hardening and Evidence-Boundary Validation: Scope & Methodology

**Terminology:** CSS = Central Superior Services Examination (Pakistan, FPSC) throughout.

This is a research/evaluation directory, separate from production content. Nothing here is read by the
running app.

## Scope

A backend security-hardening task, triggered by a real gap found during Task 12 (see
`research/evaluation/task12/failure_analysis.md`, case 11): a candidate's own answer text containing a
literal `<retrieved_background>` (or an obfuscated variant of it) was **not** neutralized by
`sanitize_user_text` before being wrapped in `<candidate_answer>...</candidate_answer>` and sent to
Gemini — only `<candidate_*>`, `<system>` and `<instructions?>`-shaped tags were stripped. This is a
hardening task, not a RAG architecture redesign: the retrieval algorithm, embedding model, evaluation
dimensions, scoring rules, and feature flag default are all unchanged.

## Methodology

1. **Trace the data flow** by reading the real code (not assuming): `backend/app/prompts/common.py`,
   `backend/app/prompts/evaluation.py`, `backend/app/agents/evaluation_agent.py`,
   `backend/app/rag/vector/evidence.py`, `backend/app/rag/vector/vector_retriever.py`, the existing
   injection tests in `tests/test_agents.py` and `tests/test_vector_retrieval.py`, and Task 12's
   `failure_analysis.md`/`FINAL_REPORT.md`.
2. **Reproduce the gap directly** against the real `sanitize_user_text` function before changing
   anything (see `security_test_results.md`, "before" column).
3. **Implement a fix** in the one file that is the actual root cause (`backend/app/prompts/common.py`)
   — no other application file needed to change.
4. **Test the fix against every adversarial variant** listed in the task brief: mixed case, whitespace
   variations, nested attempts, repeated tags, malformed tags, escaped-looking tags, Unicode lookalikes,
   multiple fake blocks — both directly against the sanitizer and end-to-end through
   `EvaluationAgent.evaluate()`, inspecting the actual constructed prompt string each time, never a bare
   HTTP/call success.
5. **Add adversarial regression tests** (`backend/tests/test_security_task13.py`, 57 tests) covering the
   three required categories (candidate-answer, retrieved-evidence, mixed-input) plus citation/provenance
   and regression checks.
6. **Run the full backend suite** before and after (454/454 baseline, confirmed unchanged by the fix;
   511/511 with the new tests added).
7. **Verify git scope**: only `backend/app/prompts/common.py` was modified by this task; no frontend, no
   production question JSON, no migrations, no RAG index files.

## Reproducing this task's work

```
cd backend
.venv\Scripts\python -m pytest tests/test_security_task13.py -q   # 57 new tests
.venv\Scripts\python -m pytest -q                                  # full suite, 511/511
```

## Files

- `README.md` — this file.
- `threat_model.md` — the trust boundaries, actors, and threats this task addresses.
- `security_test_results.md` — every adversarial case tested, with the actual before/after outcome.
- `FINAL_REPORT.md` — the complete synthesis and final PASS/CONDITIONAL PASS/FAIL recommendation.

No secrets, API keys, FAISS indexes, or model caches are stored here.
