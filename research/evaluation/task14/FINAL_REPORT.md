# Task 14 — Final Report: CSS RAG Knowledge-Base Coverage Improvement

## 1. Executive summary

Task 12 found 34% of 32 real evaluation scenarios had directly relevant top-3 evidence against the
approved 972-chunk baseline, 22% had none. This task diagnosed the root cause of every scenario
individually, found that **5 of the 32 weak scenarios are not fixable by adding sources at all** (a
chunking-structure problem in the existing baseline, out of scope here), researched and verified 7 real
authoritative sources for the remaining genuinely-missing-content gaps, built a separate 1,187-chunk
experimental index (baseline + new, never modifying the baseline), and ran the identical 32-scenario
retrieval comparison. Result: **5 genuine improvements, 2 genuine regressions, 1 new misleading-evidence
risk, and 2 real sources that didn't help at all** — a real, mixed, honestly-measured outcome, not a
uniform win. Final recommendation: **CONDITIONAL PASS**.

## 2. Initial coverage diagnosis

Built from Task 12's actual human-judged retrieval results (not its own pre-retrieval predictions, which
several times turned out wrong in either direction). Full detail in `coverage_gap_analysis.md`. Root
causes across all 32 scenarios: 9 already-good coverage, 13 genuinely missing content, 5 content-exists-
but-too-broad, **5 retrieval/chunk-structure failures that no new source can fix** (3 of them trace to
one shared dense Political-Science/IR-theory syllabus list chunk; a 4th to header-fragment pollution in
the 225-page Constitution PDF; a 5th to phrasing sensitivity on otherwise-working content).

## 3. Main subject-level gaps

Pakistan Affairs (Pakistan Movement history, 1971 separation, doctrine-of-necessity case law — all
genuinely missing), Current Affairs (WTO institutional facts missing; IMF/Paris Agreement/circular-debt
content exists but too broad), International Relations (Kashmir bilateral documents missing),
Political Science (sovereignty theory missing; separation-of-powers/realism theory present but buried by
chunk structure), Islamic Studies (Seerah and jihad-vs-terrorism content missing), General Knowledge
(2008 financial crisis and water/dam policy missing), English (composition/rhetoric pedagogy entirely
absent — a structural source-type gap: no government body publishes writing-skills textbooks, so this
cannot be closed with this task's source-priority list).

## 4. Proposed sources and verification status

**7 added, verified by direct fetch + real text extraction** (not title/snippet alone):
Paigham-e-Pakistan (2018, IIUI Islamic Research Institute, 121 pages/167 chunks), Tashkent Declaration
1966 (UN Treaty Series, 4 pages/4 chunks), Lahore Declaration 1999 (PA-X Peace Agreements
Database/Edinburgh, 2 pages/2 chunks), Sovereignty (Stanford Encyclopedia of Philosophy, 26 chunks —
independently re-verified this session: 47,627 real extracted characters), Understanding the WTO
(wto.org's own explainer, 2 chunks), IRSA official detail page (Ministry of Water Resources, 1 chunk),
Sahih Muslim 1218 (sunnah.com, 13 chunks). **4 gaps had zero viable source found**, documented honestly
in `proposed_sources.json`'s `excluded_or_failed`: Pakistan Movement narrative history (only
Wikipedia-tier mirrors), the Hamoodur Rahman Commission report (remains classified; the one candidate
host is a client-rendered SPA with no extractable text), doctrine-of-necessity case law (no accessible
official judgment text), and the Simla Agreement specifically (UN Peacemaker PDF returned HTTP 403, not
circumvented with a spoofed user-agent). One World Bank PDF that search results suggested was a
2008-crisis retrospective was rejected after actually reading it — it turned out to be an unrelated
Pakistan loan-appraisal document; title-only matching would have wrongly accepted it.

## 5. Successfully processed versus inaccessible sources

All 7 verified sources were successfully downloaded/fetched and chunked — 0 failures in the fetch step
(`task14_fetch_jobs.py`, log: "Succeeded: 7, Failed: 0"). The 4 excluded gaps above never reached the
fetch step because no accessible URL was found in the first place.

## 6. Baseline and experimental corpus statistics

| Metric | Baseline | Candidate |
|---|---|---|
| Total chunks | 972 | 1,187 (+215, +22%) |
| New chunks dropped as duplicate-of-baseline | — | 0 |
| New chunks dropped as duplicate-within-new | — | 0 |
| New chunks flagged (not removed) as <20 words | — | 4 |
| New chunks missing required metadata | — | 0 |
| Embedding model | all-MiniLM-L6-v2 | all-MiniLM-L6-v2 (unchanged) |
| Embedding dimension | 384 | 384 (unchanged) |
| Index type | faiss.IndexFlatIP | faiss.IndexFlatIP (unchanged) |
| Fresh-process reload check | — | Passed (ntotal/dim match saved config) |

New-source chunk distribution: Paigham-e-Pakistan 167, Sovereignty 26, Sahih Muslim 13, Tashkent
Declaration 4, Lahore Declaration 2, Understanding the WTO 2, IRSA 1. **Paigham-e-Pakistan alone is 78%
of all new chunks** — this concentration is directly responsible for most of both the gains and the
regressions found in §9 (see `failure_analysis.md`).

**Evaluation-contamination check** (per this task's explicit requirement): every retrieved excerpt
actually read during the comparison (§7-9) was inspected for overlap with the Task 12 dataset's own
`question_text`/`reference_answer` fields — none found. All 7 new sources are independent real
documents; none was built from, or contains, the evaluation dataset's own content.

## 7. Retrieval evaluation methodology

Same 32 Task 12 scenarios, same query text (`question_text`), same embedding model, same similarity
metric (cosine via normalized inner product), same `top_k=5`, same retrieval code path logic as
production's `rag_evidence`/`vector_retriever` convention — only the index differed (baseline vs.
candidate). No keyword shortcuts, no hand-picked results, no query rewriting between conditions. Every
one of the 16 scenarios whose top-5 composition changed was individually read and re-judged by hand
(relevant/partial/irrelevant/misleading) against the real retrieved excerpt text, reusing Task 12's own
human-judgment methodology and categories. **Top-1 and top-3 metrics are rigorously comparable this
way. Top-5 is not**: Task 12 only ever human-judged the top-3 for the baseline, so a fair top-5
comparison would require new judgment of the baseline's ranks 4-5 that was not performed in either task
— this is stated as a limitation (§11), not glossed over.

## 8. Baseline versus candidate results

| Metric | Baseline (972 chunks) | Candidate (1,187 chunks) |
|---|---|---|
| Top-1 relevant | 5/32 (16%) | 10/32 (31%) |
| Scenarios with ≥1 relevant hit in top-3 | 11/32 (34%) | 14/32 (44%) |
| Scenarios with NO useful evidence (top-3 all irrelevant/misleading) | 7/32 (22%) | 8/32 (25%) |
| Scenarios with a misleading top-3 hit | 1/32 | 2/32 |

Full scenario-by-scenario detail: `baseline_vs_candidate.csv`.

## 9. Improvements and regressions

**5 genuine improvements** (verified by reading the actual retrieved text, not score alone):
`ca-004` (WTO — 0→2 relevant hits in top-3), `ir-016` (Kashmir/Tashkent Declaration — 0→2 relevant),
`is-016` (jihad vs. terrorism/Paigham-e-Pakistan — 0→3 relevant, the strongest single result),
`is-003` (Ijtihad/Iqbal via Paigham-e-Pakistan — upgraded partial→relevant), `ps-custom-002`
(sovereignty theory — 0→1 relevant plus 2 partial).

**2 genuine regressions**: `pa-002` (Objectives Resolution — lost its one relevant hit, displaced by
unrelated Paigham-e-Pakistan content); `ps-custom-001` (Montesquieu/separation of powers — lost its one
relevant hit, the exact same chunk now buried at rank 16 of 1,187, displaced by five tangential
Sovereignty-encyclopedia chunks about different theory).

**1 new misleading-evidence risk**: `pa-001` (Lahore Resolution 1940) — new rank-1 hit is "The Lahore
Declaration (1999)," a real but entirely unrelated document matched almost purely on the shared place
name.

**2 real sources added but never surfacing for their own target question**: the IRSA page (ranked #99
of 1,187 for its own water-scarcity target query) and Sahih Muslim 1218 (ranked #117 of 1,187 for its
own Farewell Sermon target query) — both too thin/short relative to competing broader content in the
same index. Full root-cause detail for every item above: `failure_analysis.md`.

**6 benign no-ops** (new chunk entered top-5 but changed nothing material) and **16 scenarios entirely
unchanged**.

## 10. Security and provenance checks

No backend code was touched by this task — `RAG_EVIDENCE_ENABLED` remains `False` (unchanged, verified
via `git status`), Task 13's shared sanitizer (`sanitize_user_text`) and evidence-boundary protections
are untouched and unaffected, since this task never ran any content through the evaluation prompt
pipeline at all (the comparison script queries FAISS directly, the same way Task 12's Phase 4 did, not
through `EvaluationAgent`). All new-source metadata (`source_title`, `source_url`, `page_number`,
`subject`, `topic`) was populated exclusively by the same deterministic, source-derived pipeline logic
used for the approved baseline — no candidate-generated or evaluation-dataset text could reach these
fields. Citations remain internal-only by construction (this experimental index was never wired into any
API-facing code path). No local filesystem paths or index internals are exposed anywhere outside this
research directory.

## 11. Remaining limitations

- **Top-5 metrics are not rigorously comparable** between conditions (see §7) — only top-1/top-3 are.
- **4 of the 10 priority gaps remain genuinely unaddressed** (Pakistan Movement history, 1971/Hamoodur
  Rahman Commission, doctrine-of-necessity case law, Simla Agreement specifically) — no viable
  accessible source was found, not silently worked around with a weaker one.
- **English's structural gap is unaddressed by design**: no government/institutional source type in
  this task's priority list can supply writing-pedagogy content; closing it would require a different
  kind of source (an academic composition/rhetoric textbook) than every other gap here.
- **The 5 retrieval/chunk-structure-failure scenarios identified in §2 remain unfixed** — this requires
  re-chunking the existing approved baseline's dense Political-Science/IR syllabus pages and/or the
  Constitution PDF, which is explicitly out of this task's bounds ("do not modify the approved 972-chunk
  baseline") and is flagged as a real, separate architectural recommendation for a future task.
- **`Paigham-e-Pakistan`'s breadth is a double-edged sword**, responsible for 2 of the 5 improvements
  *and* both regressions plus the misleading-evidence case's companion source. A narrower excerpt
  (only its fatwa/jihad sections) would likely preserve the wins without the collateral damage — not
  attempted here, since re-chunking a source mid-comparison would have blurred the clean baseline-vs-
  candidate measurement this phase was designed to produce.
- No independent human reviewer beyond this session validated any relevance judgment in this report.
- Backend regression tests were not re-run, because no backend code was touched by this task (confirmed
  via `git diff --stat -- backend/app`, identical to Task 13's diff).

## 12. Final recommendation: **CONDITIONAL PASS**

Not PASS: there are two concrete, identifiable, non-trivial regressions and a new misleading-evidence
risk, not just a "more chunks therefore better" improvement — exactly the kind of result this task's own
instructions warned against accepting uncritically. Not FAIL: the improvements are real, verified by
reading actual retrieved text (not score deltas), address exactly the gaps they were targeted at, and
outnumber the regressions (5 vs. 2, plus top-1/top-3 relevant-hit rates genuinely improved in aggregate).
The regressions have a clear, specific, already-diagnosed cause (one overly broad source's collateral
vocabulary overlap, and one place-name collision) rather than being systemic or unexplained.

**Recommendation for Task 15**: retain this experimental candidate for further evaluation, but only
after a targeted refinement — re-scoping `Paigham-e-Pakistan` to its directly relevant sections (jihad/
fatwa content only, dropping its general-history preamble) before any A/B quality comparison against
live Gemini, to test whether the two regressions can be eliminated without losing the two genuine wins
it currently provides. The `Lahore Declaration`'s place-name collision risk should also be weighed
against its (real but comparatively smaller, 2-chunk) contribution before promotion. RAG stays disabled
by default; nothing was deployed; the production index, question bank, frontend, database schema, and
the four evaluation dimensions are all unchanged.
