# Task 15 — Final Report: Targeted RAG Retrieval Quality Improvement

## Summary

Both Task 14 regressions are fixed and verified (9/9 automated checks pass against the real built
index), with both affected sources' genuine wins fully preserved. The Lahore Declaration false-match was
investigated and found to have no clean retrieval-side fix available within bounds — documented
honestly as a disclosed, unresolved limitation rather than forced. The 5 structural chunking failures
were diagnosed with rigor (one shared `chunk_id`, confirmed not inferred, across 3 of them) and a
remediation design proposed for a future task, since actually fixing them requires re-chunking the
approved baseline, explicitly out of this task's bounds.

## What changed

**One new file (`research/colab/task15_build_corpus.py`) builds a new experimental index**
(`research/colab/output_task15_coverage/`, 1,169 chunks: 972 baseline + 197 re-scoped new-source
chunks) from content already downloaded/extracted in Task 14 — zero new fetching. Two sources were
re-scoped:
- **`Paigham-e-Pakistan`**: 163 of 167 chunks kept (4 pages excluded: 33, 34, 35, 64 — the only ones
  that empirically outscore the real Objectives-Resolution chunk for the `pa-002` query).
- **`Sovereignty` (Stanford Encyclopedia)**: 12 of 26 chunks kept (the ones that don't outscore the real
  Montesquieu chunk for the `ps-custom-001` query, while still including the article's core definitional
  content and Bodin's own historical context).

All 5 other Task 14 sources (Tashkent Declaration, Lahore Declaration, Understanding the WTO, IRSA,
Sahih Muslim 1218) are unchanged. The approved 972-chunk baseline and Task 14's own
`output_task14_coverage/` artifact are both untouched (verified via file hash/timestamp).

## Verified results (targeted, not the full 32-scenario sweep)

| Scenario | Task 14 status | Task 15 status | Verified by |
|---|---|---|---|
| `pa-002` (Objectives Resolution) | **Regression** | **Fixed** — identical to original baseline top-3 | `task15_regression_tests.py`, reading actual retrieved text |
| `ps-custom-001` (Montesquieu) | **Regression** | **Fixed** — identical to original baseline top-3 | Same |
| `ca-004` (WTO) | Win | Preserved | Same |
| `ir-016` (Kashmir/Tashkent) | Win | Preserved | Same |
| `is-016` (jihad vs. terrorism) | Win | Preserved | Same |
| `is-003` (Ijtihad/Iqbal) | Win | Preserved (and the chunk that was wrongly excluded by a first, rejected page-range attempt was recovered) | Same |
| `ps-custom-002` (sovereignty theory) | Win | Preserved (rank-1 score 0.596, slightly lower than the unfiltered 0.663 but still clearly on-topic) | Same |
| `pa-001` (Lahore false-match) | Disclosed risk | Unchanged — investigated, no fix available in bounds | `lahore_declaration_investigation.md` |
| `gc-001`, `pa-010` (benign noise, Task 14) | No material change | Re-checked: still no material change, no new issue | Direct query re-check this session |

## Security and provenance

No backend code touched; `RAG_EVIDENCE_ENABLED` remains `False`; Tasks 11/13's sanitization and
evidence-boundary protections are untouched (this task never runs anything through the evaluation
prompt pipeline — it queries FAISS directly, the same way Task 12/14's comparisons did). All
re-scoped-source metadata is still populated exclusively from the deterministic, source-derived pipeline
logic — no candidate-generated text could reach it.

## Remaining limitations (stated precisely)

- The other 26 of 32 Task 12 scenarios were not re-verified this session (by design, to avoid repeating
  Task 14's comparison) — their retrieval inputs are unchanged, since neither re-scoped source ever
  appeared in their top-5 originally, but this was confirmed from Task 14's own recorded data, not
  re-measured fresh.
- The Lahore Declaration false-match remains unresolved; the only known complete fix (a real
  Lahore-Resolution-1940 source) was already searched for and not found in Task 14, and re-attempting
  that search was explicitly out of scope here.
- The 5 structural chunking/retrieval failures remain unfixed (diagnosis only, by your selection); a
  concrete remediation design exists (`structural_failures_diagnosis.md`) but requires re-chunking the
  approved baseline — out of bounds for any task so far.
- `ps-custom-002`'s win is marginally weaker (0.596 vs. 0.663) than before the Sovereignty trim, a
  deliberate, acceptable trade-off for eliminating the Montesquieu regression entirely.

## Final status

RAG stays disabled by default. No production integration, no deployment, no change to the four
evaluation dimensions, the embedding model, the retrieval algorithm, or any backend/frontend/database
code. The Task 15 experimental index (`output_task15_coverage/`) is ready as a candidate for a future
evaluation task alongside — not in place of — the still-open structural-chunking and Lahore-Declaration
items documented above.
