# Project Status

**Current phase:** Phase 4 backend audit complete (3 genuine bugs fixed). Backend is **ready for Phase 2 frontend with limitations** (see below). **Live Gemini verification is still BLOCKED by provider availability** (HTTP 503 "high demand" from Google); nothing here claims it succeeded.

## Status matrix

| Area | Implemented | Automated-test verified | Live-provider verified |
|---|---|---|---|
| Phase 3 backend core (auth, models, interviews, reports, dashboard, progress) | Yes | Yes | n/a (no provider) |
| Phase 5 dataset (112 questions) + retrieval + Alembic 0001/0002 | Yes | Yes (validator + tests) | n/a |
| Phase 4 provider layer (timeout, retries, cooldown, JSON validation, redaction) | Yes | Yes (fake client + real SDK exception classes) | **No** - blocked (503/504) |
| Phase 4 agents + LangGraph (answer + completion graphs) | Yes | Yes (fake provider) | **No** |
| Fallback + AI/dev labelling (`gemini` / `dev_heuristic` / `mixed`, `dev_rules`) | Yes | Yes | **Yes** - outage fallback seen live (503 and invalid-key 400), labelled correctly, key never in logs |
| Migrations 0001-0003 incl. 0002->0003 data preservation | Yes | Yes | Yes (fresh DB on real server start) |
| Structured-output call to `gemini-3.8-flash` through the agents | Yes (code) | Yes (fakes only) | **NOT VERIFIED** |
| Frontend pages (Phase 2), integration (6), frontend tests (7), README (8) | **No** | - | - |

**Latest test count: 307 passed, 0 failed** (`cd backend; .venv\Scripts\python -m pytest -q`). Dataset validator: OK, 112 records. No linters/type-checkers are configured in the repo; every Python file compiles (`compileall`).

## Live Gemini status (honest record)
- Key present in `backend/.env` (git-ignored), model `gemini-3.8-flash`, `google-genai` 3.0.0, LangGraph 1.2.20.
- Earlier: one minimal plain-text request succeeded on the 2nd attempt. Since then every call, including a plain one-word prompt, returned **503 "model experiencing high demand"** or **504 deadline expired** (Google-side capacity, not request shape).
- Latest `scripts.check_gemini` (this audit): evaluation -> **HTTP 503 after 2 attempts (~39 s)**, feedback skipped by the cooldown. Exit code 1 = **not verified**. It was run once; no repeated calls.
- To verify later: `cd backend; .venv\Scripts\python -m scripts.check_gemini` (exit 0 only if Gemini itself answered both the evaluation and the feedback call).

## Phase 4 audit - findings and fixes
Found by writing regression tests against a real SQLite *file* database (the in-memory test DBs hid these) and confirming each failed on the old code:
1. **SQLite write lock held during the Gemini call.** The Answer row was flushed before the (up to ~65 s) call, freezing every other user's writes. **Fixed:** read -> call Gemini -> write everything once (`graph.save_evaluation_node`). Same for follow-up replies. Verified the new tests fail if the fix is reverted.
2. **An unexpected exception in the AI layer returned HTTP 500** and blocked the interview. **Fixed:** evaluation and feedback agents catch it and fall back, labelled `unexpected_error`.
3. **A failed follow-up re-evaluation overwrote a good Gemini evaluation with the heuristic.** **Fixed:** the reply is saved and the AI evaluation is kept (the response says so).
4. **Concurrent completion** crashed on the unique constraint (500). **Fixed:** the loser returns the existing report. Duplicate answer submissions return a clean 409.
5. **SQLite foreign keys were not enforced** (`ON DELETE CASCADE` was silently ignored). **Fixed:** `PRAGMA foreign_keys=ON` on the production engine; deleting a user now cascades through every table (tested).
Also: a test I wrote created an empty `backend/app.db` by connecting to the real path; fixed so tests never touch it (the empty file was removed).

Verified without changes: both LangGraph graphs are acyclic; follow-ups <=1 per question, <=3 per interview, never chained, enforced by DB unique constraint too; no duplicate evaluations; pending follow-up -> `/next` 409; unanswered follow-up recorded as unanswered on completion; ownership returns 404 for other users; invalid/empty/oversized answers 422 before any AI call; candidate text is sanitised in prompts; Unicode (Urdu/emoji) round-trips; scores validated 0-10 (out-of-range rejected, overall computed locally); error text is redacted and the key never appears in responses or logs (also checked on a real server with an invalid key).

## Known limitations / remaining backend issues
- Live Gemini output unverified; **prompts and scoring are uncalibrated against real model responses** and may need tuning.
- During a Gemini outage an answer or completion can take up to ~65 s before the labelled fallback; later requests fail fast for 30 s (cooldown). The frontend needs loading states and a >=90 s client timeout.
- The audit's design target is SQLite. **MySQL/other databases were not tested** (e.g. `server_default` on TEXT in migration 0002 would need review). There is no `Conversation` table: conversation context is derived from saved answers/evaluations (by design).
- API gaps for the planned UI (details in `docs/frontend-integration.md`): no endpoint to update profile/preferences or change password; no abandon/cancel for an interview with zero answers (it stays `in_progress`); `GET /interviews/{id}` omits the answers already given; no refresh/logout endpoint; `duration_minutes`/`mode` not enforced server-side.
- No per-user rate limiting on AI-backed endpoints (each answer is one Gemini call; answers are capped at 8000 chars).
- Question bank is a sample, **unverified** study aid; questions are retrieved, not LLM-generated. Removed dataset questions stay in the DB.
- `unexpected_error` fallbacks log only the exception class name.

## Phase 2 frontend readiness: READY WITH LIMITATIONS
The complete interview journey (auth -> setup -> room with follow-ups -> report -> dashboard/history) is available and tested end to end, on a database created by the real migrations. The Profile/Settings page cannot be fully built without the gaps above. Frontend integration checklist: `docs/frontend-integration.md`.

## Documentation
`docs/api-documentation.md` (endpoints), `docs/ai-agents.md` (agents, graphs, failure policy), `docs/dataset.md`, `docs/frontend-integration.md` (new), `CLAUDE.md`.

## Commands (Windows)
```
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000     # API + Swagger at /docs
.venv\Scripts\python -m pytest -q                                      # backend tests (307)
.venv\Scripts\python -m scripts.check_gemini                          # live Gemini check (2 real API calls)
.venv\Scripts\python -m app.rag.validate                              # check the question dataset
cd ..\frontend
npm run dev                                                            # http://localhost:5173
```

## History (condensed)
- Phase 0-1: audit, structure, FastAPI + Vite/React/TS/Tailwind skeleton.
- Phase 3: models, JWT auth, interview/report/dashboard/progress endpoints, dev heuristic evaluator (66 tests).
- Phase 5: 112 curated sample questions, validator, keyword retriever, question selection, Alembic 0001-0002 (183 tests).
- Phase 4: provider layer, five agents, LangGraph, follow-ups, migration 0003 (280 tests), then this audit (307 tests).

## Next step
Await approval. Then Phase 2 (frontend), optionally preceded by the small backend gaps above (profile/preferences update, abandon interview). Re-run `scripts.check_gemini` whenever Google capacity recovers.
