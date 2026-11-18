# Task 14 — CSS RAG Knowledge-Base Coverage Improvement: Scope & Methodology

**Terminology:** CSS = Central Superior Services Examination (Pakistan, FPSC) throughout.

Research and evaluation only, kept separate from the production backend and from the approved RAG
baseline, exactly as Task 11-13 kept their own research work separate. `RAG_EVIDENCE_ENABLED` remains
`False`; no backend code was touched by this task.

## What this task investigated

Task 12 found that only 34% of its 32 real evaluation scenarios had a directly relevant hit in the
approved baseline's top-3 retrieval, with 22% having no useful evidence at all. This task diagnoses
*why*, builds a separately-validated experimental corpus that adds real, verified, authoritative sources
for the gaps that are actually fixable by sourcing (as opposed to gaps caused by the existing corpus's
own chunking structure), and measures whether it actually helps — honestly, including where it doesn't.

## Method, in order

1. **Coverage diagnosis** (`coverage_gap_analysis.md`): every one of Task 12's 32 scenarios reclassified
   by real, human-judged retrieval outcome (not the dataset's own pre-retrieval predictions) into one of
   four root causes: already-good coverage, genuinely missing content, content that exists but is too
   broad/generic, or a retrieval/chunk-structure failure that no new source could fix. 13 scenarios
   landed in the genuinely-missing category; 10 priority gaps were selected from those for source
   research.
2. **Source research** (`proposed_sources.json`, `source_coverage_matrix.csv`): real web research and
   direct verification (HTTP fetch + actual text extraction, same tools the existing notebook pipeline
   uses) against the 10 priority gaps. 7 real sources were found, verified, and added; 4 gaps had zero
   viable source found and are honestly documented as such, not forced.
3. **Experimental corpus build** (`research/colab/task14_pipeline.py`, `task14_fetch_jobs.py`): the 7
   verified sources were downloaded/extracted/chunked using the *exact same* functions as the existing
   notebook (`clean_text`, `chunk_text` at 350 words/70-word overlap, the same deterministic
   `document_id`/`chunk_id` hashing, the same metadata schema), merged with the approved baseline's 972
   chunks unchanged, then the whole 1,187-chunk set was re-embedded with the same
   `all-MiniLM-L6-v2` model into a new `faiss.IndexFlatIP`, saved to
   `research/colab/output_task14_coverage/InterviewIQ_Dataset/08_Embeddings/`. The approved baseline
   directory was never written to; verified unchanged (`built_at_utc` timestamp identical before/after).
4. **Retrieval comparison** (`research/colab/task14_retrieval_eval.py` → `retrieval_comparison_raw.json`
   → `baseline_vs_candidate.csv`): the exact same 32 Task 12 scenarios, the exact same query text
   (`question_text`, matching production's own `rag_evidence.get_evidence(question.text)` convention),
   the exact same model/metric/top-k, run against both the baseline and candidate indexes. Every
   scenario whose top-5 composition changed (16 of 32) was individually read and re-judged by hand
   (relevant/partial/irrelevant/misleading) against the actual retrieved text — a score increase was
   never treated as proof of improvement on its own, per this task's own instruction.
5. **Failure analysis** (`failure_analysis.md`): every regression, new misleading-evidence risk, and
   added-but-ineffective source, with root cause.

## Reproducing this task's work

```
cd research/colab
..\..\.venv-rag\Scripts\python task14_fetch_jobs.py     # downloads + chunks the 7 new sources
..\..\.venv-rag\Scripts\python task14_pipeline.py build  # merges with baseline, builds the candidate index
..\..\.venv-rag\Scripts\python task14_retrieval_eval.py   # runs the 32-scenario baseline-vs-candidate comparison
```
All three steps were actually executed this session using `.venv-rag` (already has
`faiss-cpu`/`sentence-transformers`/`pymupdf`/`trafilatura`/`truststore` installed from earlier
sessions) — not merely written and left unexecuted.

## Files

- `README.md` — this file.
- `coverage_gap_analysis.md` — Phase 2: the real root-cause diagnosis of all 32 scenarios.
- `proposed_sources.json` — Phase 3: the 7 verified new sources, plus 4 honestly-documented failed
  searches, plus 3 lower-priority gaps not attempted.
- `source_coverage_matrix.csv` — Phase 3: one row per gap, mapping it to its candidate source and status.
- `baseline_vs_candidate.csv` — Phase 5: scenario-by-scenario, human-judged comparison.
- `retrieval_comparison_raw.json` — the raw top-5 hits (scores, chunk IDs, metadata, excerpts) for both
  conditions on all 32 scenarios, generated directly by the real retrieval run.
- `failure_analysis.md` — every regression and non-improvement found, with root cause.
- `FINAL_REPORT.md` — the complete synthesis and final PASS/CONDITIONAL PASS/FAIL recommendation.

Supporting scripts live in `research/colab/`: `task14_pipeline.py` (ported extraction/chunking/
embedding functions, ground-truth-identical to the notebook's own section 4-6/11, with the experimental
build/merge logic), `task14_fetch_jobs.py` (the 7-source job list), `task14_retrieval_eval.py` (the
comparison runner). The existing `css_knowledge_base_builder.ipynb` notebook itself was **not modified**.

No secrets, API keys, or large binary artifacts are stored in this evaluation directory (the actual
FAISS index/embeddings live under `research/colab/output_task14_coverage/`, separate from this
evaluation report directory, exactly mirroring how the approved baseline is organized).
