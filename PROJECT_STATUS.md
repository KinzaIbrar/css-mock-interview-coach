# Project Status

**Deployment prep (latest):** see `DEPLOYMENT.md`. Added PostgreSQL support (`psycopg`, URL normalisation, pooled engine), production JWT-secret guard, `CORS_ORIGIN_REGEX`, `render.yaml`, `frontend/vercel.json`, `scripts/copy_database.py`. Backend 402 tests passed / frontend 125 passed (single-worker; parallel workers can OOM on a low-RAM machine). `copy_database.py` now also copies `questions` (FK-safe on PostgreSQL); verified on a backup of the real DB into a temp SQLite file with 0 FK violations. Verified backup: `backend/backups/` (git-ignored) / build ok. NOT deployed; live Supabase/Render/Vercel untested.

## Multi-agent conversational interview (latest milestone) - see `docs/multi-agent-interview.md`
**Completed:** four named agents with real, derived statuses (`GET /api/agents`, per-request `trace`); introduction ("Tell me about yourself") -> Q1 -> follow-up -> Q2 flow with correct main-question numbering and a resumable `conversation`; follow-up replies evaluated **separately** (main evaluation never replaced; the old "kept original evaluation" path is gone); repeat-follow-up protection; adaptive question order (mixed interviews); rule-based Coaching plan (weak topics, concepts, recurring mistakes, practice questions) in the report; procedural 3D avatar (React Three Fiber) with Repeat/Stop speech, text caption and a flat fallback; optional consent-gated camera with in-browser MediaPipe pose tracking (aggregates only, never frames), separate non-verbal report section with "Not enough data", limitations and rules; migration 0004; AuthContext no longer signs out on network errors (401 only); docs.
**Incomplete / blockers:** no licensed GLB/VRM avatar model was available, so the avatar is procedural (no phoneme lip-sync - approximate mouth motion only; documented); live Gemini still NOT verified (free-tier daily quota 429), so AI paths are tested with fakes; camera tracking was unit-tested on synthetic landmarks and not exercised on a real webcam in this session (no camera available); remaining UX-audit items (per-route titles, 16px inputs, 404 h1, follow-up layout on narrow screens) not done.
**Tests (actually run):** backend `pytest` 392 passed; frontend `vitest` 125 passed; `tsc -b` and `vite build` pass; `oxlint` 0 errors (3-4 non-blocking warnings); `compileall` ok; dataset validator OK; migration tests pass at head `0004`. `backend/app.db` was not modified by tests (in-memory DB).
**New dependencies:** frontend `three`, `@react-three/fiber`, `@mediapipe/tasks-vision`, dev `@types/three` (backend: none). `npm run dev|build` runs `scripts/setup-vision-assets.mjs` (copies WASM, downloads the ~5.8 MB pose model to gitignored `public/vision/`; failure is non-fatal).
**Next steps:** drop a licensed avatar into `frontend/public/avatar/` and load it in `AvatarScene.tsx`; try the camera on a real webcam; restart the backend (migration 0004 applies automatically); re-run `python -m scripts.check_gemini` after the quota resets.


**Current phase:** Phase 2 (frontend) implemented; a start-error / Gemini-429 audit has just been completed and fixed (see below). **Live Gemini evaluation is NOT verified**: the latest real call was rejected with HTTP 429 because the free-tier **daily quota (20 requests/day for `gemini-3.8-flash`) is exhausted**. Nothing here claims Gemini produced a successful evaluation.

## Status matrix

| Area | Implemented | Automated-test verified | Live-provider verified |
|---|---|---|---|
| Phase 3 backend core (auth, models, interviews, reports, dashboard, progress) | Yes | Yes | n/a (no provider) |
| Phase 5 dataset (112 questions) + retrieval + Alembic 0001/0002 | Yes | Yes (validator + tests) | n/a |
| Phase 4 provider layer (timeout, retries, cooldown, JSON validation, redaction) | Yes | Yes (fake client + real SDK exception classes) | **No** - blocked (503/504) |
| Phase 4 agents + LangGraph (answer + completion graphs) | Yes | Yes (fake provider) | **No** |
| Fallback + AI/dev labelling (`gemini` / `dev_heuristic` / `mixed`, `dev_rules`) | Yes | Yes | **Yes** - outage fallback seen live (503 and invalid-key 400), labelled correctly, key never in logs |
| Migrations 0001-0003 incl. 0002->0003 data preservation | Yes | Yes | Yes (fresh DB on real server start) |
| Structured-output call to `gemini-3.8-flash` through the agents | Yes (code) | Yes (fakes only) | **NOT VERIFIED** - real call returned 429 (daily quota exhausted) |
| HTTP 429 handling (daily quota vs rate limit, real cause reported, no pointless retries) | Yes | Yes (66 new backend tests incl. real SDK exception) | **Yes** - observed against Google's real 429 in the browser: 1 request, labelled fallback, key not in logs |
| `GET /health` `ai_availability` + honest sidebar/profile status | Yes | Yes | **Yes** (browser showed "Gemini quota used up") |
| Phase 2 frontend: auth, dashboard, setup, interview room + follow-ups, report, history, question bank, profile | Yes | Yes (87 Vitest tests) | Browser-checked against the real backend in **fallback** mode only; AI path via mocks |
| Voice dictation / read-aloud (optional) | Yes | Unsupported-browser path only | **No** (no microphone/speakers available) |
| Remaining: README (8), tablet/cross-browser/a11y audit | No | - | - |

**Latest test counts (before the multi-agent milestone): backend 373 passed, 0 failed** (`cd backend; .venv\Scripts\python -m pytest -q`); **frontend 97 passed, 0 failed** (`cd frontend; npm test`). Frontend `tsc`, `vite build` pass; `oxlint`: 0 errors, 3 warnings (non-blocking). Dataset validator: OK, 112 records. No linters/type-checkers are configured in the repo; every Python file compiles (`compileall`).

## Start-error and Gemini-429 audit (latest)
**1. Repeated `400` on `POST /interviews/start` - two root causes, both on the client; backend validation is correct and unchanged.**
- The only 400 in the backend is "Only N question(s) available...", i.e. fewer questions than requested for (subject, topic, difficulty); malformed fields are 422. In the real dataset **52 of 53 topics hold fewer than 5 questions**, and the form defaults to 5, so *topic + a specific difficulty* was refused for all 159 combinations. The form only knew the count for topic + "mixed", so it sent requests certain to fail.
- The server's explanatory message was rendered at the **top** of the form: on a phone-width screen it was ~391 px above the visible area while the Start button was in view, so users saw nothing happen and clicked again (each click = another 400).
- **Fixed (frontend only):** for topic + difficulty the form fetches the exact count (`GET /questions?...&limit=1`, same filters as start), validates before sending, and moves focus to the field; a server refusal is shown above the Start button, scrolled into view and focused. Verified in a real browser: the doomed request is no longer sent (0 `POST /start`), one click = one request.
- No duplicate requests were found (the Start button is disabled while pending); the doubled `/auth/me` and `GET /interviews/{id}` calls are React StrictMode in the dev server only.

**2. Gemini `429` - cause identified from Google's real response.** `QuotaFailure.quotaId = GenerateRequestsPerDayPerProjectPerModel-FreeTier`, **limit 20/day for `gemini-3.8-flash`**, `RetryInfo.retryDelay = 17244 s` (~4.8 h), rejected in 0.9 s. It is a **daily quota**, not a burst/rate limit. The old provider treated every 429 as transient: it retried twice (pointless), lost the cause (`http_429`), used a fixed 30 s cooldown (so every later answer tried and failed again) and the UI kept saying "Gemini configured".
- **Fixed:** the provider now reads Google's `QuotaFailure`/`RetryInfo`. Daily quota -> **no retries**, pause for Google's delay (capped at 15 min by `GEMINI_QUOTA_COOLDOWN_CAP_SECONDS`, then probe again), every call in that window fails fast with the real reason `quota_exhausted`. Per-minute limit -> wait Google's delay only if it fits the time budget, else fail fast (`rate_limited`). 5xx/timeouts keep the generic cooldown. Users get plain-language notices; `/health` exposes `ai_availability`; the sidebar/profile show quota/rate-limit/outage state.
- **Practical limit:** on the free tier one 5-question interview uses ~6 requests, so roughly **3 interviews per day** until the quota resets (or use a billed key / another model).

**3. Cooldown and independence.** Evaluation and feedback share one per-model quota, so a shared pause is correct for 429; each operation retries independently once it expires (tested: after the cooldown both an evaluation and the feedback use Gemini again). A failed Gemini call never erases a stored AI evaluation (tested for 429 on a follow-up reply and mid-interview), and reports label `gemini` / `dev_heuristic` / `mixed` correctly (tested and seen live).

**4. Not verified:** a successful real Gemini evaluation (quota exhausted). **Your running backend (port 8000) was started before these fixes: restart it to get them.** `backend/app.db` is your real database and was not touched.

## Live Gemini status (honest record)
- Key present in `backend/.env` (git-ignored), model `gemini-3.8-flash`, `google-genai` 3.0.0, LangGraph 1.2.20.
- Earlier: one minimal plain-text request succeeded on the 2nd attempt. Since then every call, including a plain one-word prompt, returned **503 "model experiencing high demand"** or **504 deadline expired** (Google-side capacity, not request shape).
- Latest `scripts.check_gemini` (this audit): evaluation -> **HTTP 503 after 2 attempts (~39 s)**, feedback skipped by the cooldown. Exit code 1 = **not verified**. It was run once; no repeated calls.
- Latest real call (audit): **429 RESOURCE_EXHAUSTED, daily free-tier quota (20/day) used up, Google's retry delay ~4.8 h.** Not a failure of the key or the code.
- To verify later (after the quota resets or with a billed key): `cd backend; .venv\Scripts\python -m scripts.check_gemini` (exit 0 only if Gemini itself answered both the evaluation and the feedback call).

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

## Phase 2 frontend (implemented)
Details, structure, behaviours, limitations and deviations: `docs/frontend-implementation.md`. Highlights: typed API layer with a 120 s timeout for AI calls and `ApiError` normalisation; client-side token handling (no refresh/logout endpoints exist); protected/public route guards; an interview room that never double-submits and re-checks the server after any 409/timeout/network failure before retrying; follow-up flow; every AI/fallback source labelled (`gemini` / `dev_heuristic` / `mixed`, `dev_rules`, rule-based progress). Scores are shown only in the report because the backend withholds them mid-interview. Written in TypeScript (the existing stack) rather than JavaScript as the brief said.

**Phase 2 limitations:** Profile is read-only (no backend endpoints); no abandon-interview; duration/mode not enforced server-side; live Gemini path unverified in the browser; voice untested with real devices; tablet width, cross-browser and automated accessibility checks not done.

## Phase 2 frontend readiness (backend audit, earlier): READY WITH LIMITATIONS
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
Await review of Phase 2. Suggested next: small backend additions the UI needs (profile/preferences update + change password, abandon interview), re-run `scripts.check_gemini` and a live browser pass when Google capacity recovers, then README/final documentation (Phase 8).
