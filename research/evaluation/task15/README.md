# Task 15 — Targeted RAG Retrieval Quality Improvement: Scope & Methodology

**Terminology:** CSS = Central Superior Services Examination (Pakistan, FPSC) throughout.

Research only, kept separate from production. `RAG_EVIDENCE_ENABLED` remains `False`; no backend code
was touched (all Task 11/13 backend modifications are preserved, unchanged); the approved 972-chunk
baseline FAISS index was never modified; Task 14's own experimental index
(`output_task14_coverage/`) is preserved untouched for audit.

## What this task did, and did not repeat

Reused Task 14's already-verified 7 sources and already-downloaded/extracted content — **no new source
research, no new web fetching, and no full 32-scenario retrieval comparison were performed**, per this
task's explicit constraint. Only the 6 scenarios actually affected by the two fixes (plus the 2
previously-noisy-but-unaffected ones) were targeted-tested.

1. **Phase 1-2 (regression fixes, `regression_fixes.md`)**: both Task 14 regressions
   (`t12-pa-002` Objectives Resolution, `t12-ps-custom-001` Montesquieu) fixed by precise, empirically-
   validated per-chunk exclusion from the two over-broad sources responsible (`Paigham-e-Pakistan`,
   `Sovereignty`) — not a crude page-range or chunk-count heuristic, which was tried first and proven
   insufficient by direct measurement before the final fix was applied. Both of that source's own
   genuine wins (`is-016`, `is-003`, `ps-custom-002`) are verified preserved, not just assumed.
2. **Phase 3 (`lahore_declaration_investigation.md`)**: investigated the Lahore Declaration/Resolution
   false-match; confirmed no clean retrieval-side mitigation exists (the false match's score overlaps
   with genuine wins' scores, so no universal similarity floor can separate them) without changing the
   embedding model or retrieval algorithm, both out of bounds. Documented as a disclosed, pre-existing,
   unresolved risk — not silently worked around.
3. **Phase 4 (`structural_failures_diagnosis.md`)**: diagnosis-only (per your selection) for the 5
   structural chunking/retrieval failures identified in Task 14 — rigorously confirmed (by literal
   `chunk_id` match, not inference) that 3 of the 5 share the exact same root chunk, proposed but did not
   implement a re-chunking remediation (would require modifying the approved baseline, out of bounds).
4. **Phase 5 (targeted tests)**: `research/colab/task15_regression_tests.py` — 9 automated, assertion-
   based checks against the real built index (not mocked), all passing.

## Reproducing this task's work

```
cd research/colab
..\..\.venv-rag\Scripts\python task15_build_corpus.py          # re-scopes the 2 sources, rebuilds the candidate index
..\..\.venv-rag\Scripts\python task15_regression_tests.py      # 9 automated checks
..\..\.venv-rag\Scripts\python task15_verify.py                # human-readable top-5 printout for the 6 affected scenarios
```

## Files

- `README.md` — this file.
- `regression_fixes.md` — Phase 1-2: the exact fix methodology and verified before/after.
- `lahore_declaration_investigation.md` — Phase 3: the false-match diagnosis and why no fix was applied.
- `structural_failures_diagnosis.md` — Phase 4: root-cause confirmation for all 5 structural failures.
- `verification_raw.json` — raw top-5 hits for the 6 targeted scenarios against the Task 15 index.
- `FINAL_REPORT.md` — complete synthesis and final recommendation.

Supporting scripts in `research/colab/`: `task15_build_corpus.py` (the re-scoping/rebuild logic, fully
commented with the empirical reasoning for every exclusion), `task15_verify.py`, `task15_regression_tests.py`.
