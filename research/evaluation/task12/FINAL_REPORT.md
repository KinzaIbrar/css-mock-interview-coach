# Task 12 — Final Report: Controlled RAG Evaluation and A/B Testing

## 1. What was inspected
`backend/app/rag/vector/{loader,embedder,vector_retriever,evidence}.py`, `evaluation_agent.py`,
`prompts/evaluation.py`, `core/config.py`, the Task 11 test suite (`test_vector_retrieval.py`, 40 tests)
and the existing `test_agents.py`/`test_retrieval.py`, and the real approved-baseline artifact files.
Confirmed, by reading the code and re-running tests (not assumed): `RAG_EVIDENCE_ENABLED` still defaults
to `False`; `evidence.get_evidence()` returns `[]` immediately when disabled, before importing
faiss/torch; the dev-heuristic fallback path (`EvaluationAgent._fallback`) never calls the evidence
layer at all, so it cannot misreport using RAG; `EvaluationOutcome.citations` is excluded from
`.columns()` (the DB-write path) and never referenced by `AnswerAck`/`FollowUpAck`/`Report`; retrieval
failures are converted to `[]` by `evidence.get_evidence`'s `except RagError` / `except Exception`
clauses; the approved 972-chunk baseline's `index_config.json` timestamp is identical to before this
task started.

## 2. Evaluation dataset size and subject coverage
**32 scenarios** (target: "at least 30," met). 28 from real `data/questions/*.json` entries across 7
production subjects (4 each); 4 standalone, clearly-labelled evaluation-only scenarios covering
Political Science and General Science & Ability (2 each), which exist in the RAG corpus but not in the
production question bank. All 7 requested answer-quality types represented 3-9 times each.
`research/evaluation/task12/evaluation_dataset.jsonl`.

## 3. A/B methodology (as designed; see §4 limitations)
Condition A: RAG disabled, existing path unchanged. Condition B: same question, same candidate answer,
same reference answer/criteria, same model (`gemini-3.8-flash`), same system prompt, same four scoring
dimensions — only the optional `<retrieved_background>` section differs. The harness to run both
conditions and diff the results exists and is ready; **it could not be executed this session** (§8/§13).

## 4. Model and parameter consistency
Both conditions were designed to call `EvaluationAgent().evaluate()` identically except for
`settings.rag_evidence_enabled`, which only changes whether `evidence_block` is non-empty in
`build_prompt(...)`. No other parameter (model name, temperature, retries, timeout) differs between
conditions anywhere in the code.

## 5. Retrieval relevance results (real, executed against the approved 972-chunk baseline)
Top-3 hits judged by hand (relevant / partially relevant / irrelevant / misleading) for all 32
scenarios — 96 judgments total:

| Metric | Value |
|---|---|
| Directly relevant hit in top-3 | 16/96 slots (17%) |
| Partially relevant | 32/96 (33%) |
| Irrelevant | 47/96 (49%) |
| Potentially misleading | 1/96 (1%) |
| **Scenarios with >=1 relevant hit** | **11/32 (34%)** |
| **Scenarios with NO useful evidence at all** | **7/32 (22%)** |

**Evidence coverage by subject** (scenarios with >=1 relevant hit / total): Governance and Constitutional
Studies 2/4, International Relations 2/4, General Knowledge 2/4, Pakistan Affairs 1/4, English 1/4,
Islamic Studies 1/4, Political Science 1/2, General Science and Ability 1/2, **Current Affairs 0/4**.

**Honest correction to my own predictions:** several scenarios I predicted "strong" (IMF role, Paris
Agreement/climate justice, Fundamental Rights) came back weak on real testing — the right content exists
*somewhere* in the corpus (confirmed in other scenarios' results, e.g. gk-010 surfaced a real IMF
facility) but didn't surface for these specific phrasings. This is new, real evidence that **retrieval
quality is noticeably phrasing-sensitive**, not just topic-dependent. Full detail: `retrieval_relevance.csv`.

## 6. Baseline versus RAG evaluation results
**Not available.** See §8.

## 7. Four-dimension score comparison
**Not available** — no real score exists for either condition for any scenario. I am not substituting
the dev-heuristic or fabricating numbers to fill this section, per the task's explicit instruction.

## 8. The blocker, stated plainly
Gemini (`gemini-3.8-flash`) returned `HTTP 503: "This model is currently experiencing high demand.
Spikes in demand are usually temporary. Please try again later."` on a direct SDK call (3.2s), then hung
with no response for over 15 minutes on a second attempt (manually stopped), then failed again in 3.4s
with an explicit 15-second client timeout. Three independent attempts, three failures, no successful
call. This is a live external-service availability issue, confirmed by bypassing our own code entirely
(calling `google.genai` directly) — not a bug in the RAG integration. **Per the task's own instructions,
I am reporting this blocker rather than substituting heuristic scores or fabricating an A/B result.**

## 9. Human-review findings and limitations
No independent human reviewer was available this session — the retrieval-relevance judgments in §5 are
**developer-reviewed, not independently validated**, and are labelled as such throughout
`retrieval_relevance.csv`. The planned blinded Condition-A-vs-B review (Phase 6) could not happen at all,
since there are no Condition A/B results yet to review.

## 10. Performance and memory measurements (real, both sessions)
| Measurement | Task 11 | Task 12 (re-measured) |
|---|---|---|
| Memory: app only | 126.3 MB | (unchanged infra, not re-measured) |
| Memory: + index loaded | 141.0 MB | — |
| Memory: + model loaded | 598.4 MB (+457 MB) | — |
| Model load time (first call) | 21.9 s | 13.5 s (same order of magnitude; both are one-time first-load costs) |
| Index load time | 0.112 s | 0.0755 s |
| Retrieval latency (steady state) | mean 35 ms | p50 17.7 ms, p90 26.4 ms over 32 real queries |
| GPU used | No | No |

No Gemini-latency comparison exists (§8). Full detail: `performance_results.csv`.

## 11. Failure and fallback testing
10 of 12 required cases map directly to Task 11's real, automated, re-run test suite (all passing,
454/454 full regression). 2 cases required new manual checks this session: long candidate answers
(50,000 chars) truncate cleanly to 4,000 — **pass**; and a candidate answer containing a literal
`<retrieved_background>` tag is **not** currently neutralized by `sanitize_user_text` — a real, newly
found gap, assessed as low-to-moderate severity (not a working instruction override, since the system
prompt already treats anything inside that tag as non-authoritative data, but a real social-engineering-
style risk worth fixing). Full detail and severity reasoning: `failure_analysis.md`.

## 12. Regression test results
**454/454 passed**, re-run fresh this session. Zero backend application-code changes were made in Task
12 (confirmed via `git diff --stat -- backend/app`, identical to Task 11's diff).

## 13. Files created or modified
**New (all under `research/evaluation/task12/`):** `README.md`, `evaluation_dataset.jsonl`,
`retrieval_raw.json`, `retrieval_relevance.csv`, `ab_results.jsonl` (32 rows, all blocked), `performance_results.csv`,
`failure_analysis.md`, this file. **Modified:** nothing in `backend/`, `frontend/`, or `data/questions/`.

## 14. Git status and protected-file verification
`git diff --stat -- backend/app frontend/src data/questions/*.json` → empty for all three (only the
pre-existing Task 11 backend diff remains, untouched by Task 12). All three RAG index variants
(original 979-chunk, approved 972-chunk, rejected 1,085-chunk) show identical `built_at_utc`/chunk counts
to before this task began. No file in this task's output directory exceeds 80 KB; nothing resembling an
API key, secret, FAISS index, or model cache was written here.

## 15. Remaining limitations
- **The core question this task was built to answer — does RAG evidence improve evaluation quality —
  remains unanswered.** Everything that *didn't* require a live Gemini call (dataset construction,
  retrieval relevance, performance, robustness, regression) was genuinely executed; everything that did
  (the actual quality comparison) is blocked and honestly reported as such, not faked.
- Retrieval relevance itself is weaker and more phrasing-sensitive than this project's earlier,
  narrower evaluation sets suggested (34% of scenarios had any directly relevant top-3 evidence here, vs.
  higher apparent hit rates in Tasks 8-10's shorter, more targeted question set) — worth knowing
  independent of the Gemini question.
- The newly found `<retrieved_background>` tag-injection gap in `sanitize_user_text` is unfixed (by
  design — out of this task's scope) and should be picked up before RAG is ever considered for real use.
- No independent human reviewer validated any judgment in this report.

## Final decision: **CONDITIONAL GO**

Not GO: no evidence exists that RAG improves evaluation quality — the one experiment designed to show
that could not run. Not NO-GO: nothing tested this session demonstrated a regression, a safety failure,
or an unacceptable cost either — robustness is solid (454/454, graceful degradation confirmed every way
it was tested), memory/latency costs are known and bounded, and the retrieval layer, while weaker than
hoped on this broader dataset, surfaces genuinely relevant evidence for roughly a third of scenarios
without ever blocking evaluation.

**Conditions for a future GO/NO-GO decision:**
1. Re-run the exact same `evaluation_dataset.jsonl` through both conditions once Gemini is reliably
   reachable — this is the single blocking prerequisite, and the harness is ready.
2. Fix the `<retrieved_background>` tag-neutralization gap in `sanitize_user_text` before any real use,
   independent of the quality-comparison outcome.
3. Treat the Current Affairs subject (0/4 useful evidence here) and the phrasing-sensitivity finding as
   open retrieval-quality questions, not yet resolved by this task.

RAG stays disabled by default. No deployment, no frontend change, no default-flag change occurred in
this task.
