# Project Status

**Current phase:** Phase 5 (dataset and retrieval) complete. Awaiting review/approval before Phase 4 (Gemini + agents + LangGraph).

## Completed
- **Phase 0:** environment audit and plan approved.
- **Phase 1:** folder structure, `.gitignore`, FastAPI app, Vite/React/TS/Tailwind frontend with `/api` proxy, CLAUDE.md.
- **Phase 3 (backend core):**
  - SQLAlchemy models: User, Interview, Question, Answer, Evaluation, Feedback, Progress (FKs, relationships, timestamps). (Phase 3 created tables with `create_all`; since Phase 5 they are managed by Alembic.)
  - Auth: register / login / me, bcrypt hashing, JWT (pyjwt), `get_current_user` dependency, 404-based data isolation.
  - Endpoints: auth (3), questions (2), interviews (start, answer, next, complete, history, detail), reports, dashboard, progress, health. See `docs/api-documentation.md`.
  - Sample question bank `data/css_questions.json` (21 questions, 3 per subject across the 7 subjects) seeded idempotently at startup. **Labelled sample/unverified.**
  - Dev-mode evaluator and feedback (`services/dev_evaluator.py`, `services/report_service.py`): deterministic keyword/length heuristics, **not AI**. Every evaluation/report carries `evaluation_source: "dev_heuristic"`, `is_ai_generated: false` and a notice.
  - Dashboard/progress statistics are computed from saved records; a new user gets nulls/empty lists, nothing fabricated.
- **Verification (actually run):** `pytest` → **66 passed**; live curl journey against uvicorn + real SQLite (register → start → answer/next ×2 → complete → dashboard; unauthenticated call → 401); `/openapi.json` lists 15 paths. Test database file deleted afterwards.

- **Phase 5 (dataset + retrieval):**
  - 112 curated questions (7 subjects x 16, all three difficulty levels) in `data/questions/*.json`, with expected answer, important concepts, evaluation criteria, tags and explanation. **Sample/unverified**, see `docs/dataset.md`. The old `data/css_questions.json` (21 questions, still in git history from the Phase 3 commit) was replaced by this directory.
  - Strict validation (`app/rag/dataset.py`, CLI `python -m app.rag.validate`): required fields, unique ids, valid subject/difficulty, non-empty answers, criteria, duplicate and near-duplicate text. Invalid data aborts seeding.
  - Retrieval (`app/rag/`): `QuestionRetriever` protocol + `KeywordRetriever` (subject/topic/difficulty/tag filters, relevance-ranked keyword search, pagination), `select_questions()` (distinct, avoids the user's recent questions, topic spread, easy-to-hard for mixed). Vector search can be added behind the same protocol; **no vector DB was added** (no demonstrated benefit at this size).
  - Alembic introduced: baseline `0001` (Phase 3 schema) + `0002` (adds `evaluation_criteria`, `tags`, `explanation` to `questions`). Migrations run automatically at startup and adopt pre-Alembic databases without deleting data.
  - API: `GET /questions` gained `topic`, `tag`, ranked `search` with `score`, and new fields; new `GET /questions/meta`; `POST /interviews/start` accepts optional `topic`. Existing endpoints stay backward compatible.
  - **Verification (actually run):** `pytest` -> **183 passed** (66 original + 117 new); live uvicorn run on a fresh database: migrated to 0002, seeded 112 questions, meta/search/interview-start responded correctly; test DB deleted afterwards.

- **Phase 4 prerequisites (Gemini connectivity):**
  - `GEMINI_API_KEY` is set in `backend/.env` (git-ignored; never printed or committed).
  - `google-genai` **3.0.0** installed in `backend/.venv` and pinned as `google-genai>=3.0,<4` in `requirements.txt`. LangGraph is not installed yet.
  - The original default `gemini-2.5-flash` returned 404 ("no longer available to new users"), so the default is now **`gemini-3.8-flash`** (`app/core/config.py`, `.env.example`).
  - **Verified model: `gemini-3.8-flash`.** A minimal `generate_content` call from the backend succeeded on the **second attempt**, after a transient 504 timeout on the first (earlier attempts had also timed out). Backend tests: 183 passed.

## Remaining
- Phase 4: Gemini provider (`LLMProvider`), five agents, LangGraph orchestration, replace the dev evaluator/feedback. Still to install: `langgraph`.
- Phase 2: frontend pages and design system (shadcn/ui not initialised yet).
- Phase 6: frontend ↔ backend integration. Phase 7: frontend tests and full-journey check. Phase 8: README / architecture docs.

## Known issues / notes
- Questions are selected by rules from the sample bank; AI question generation and follow-ups arrive in Phase 4.
- Questions removed from the dataset files remain in the database (past interviews may reference them).
- The legacy tests seed from a frozen 21-question fixture (`backend/tests/fixtures/legacy_21.json`) via `tests/conftest.py`; the full dataset is covered by the new tests.
- Dataset facts are unverified; review before presenting as authoritative.
- `mode` (mock/practice) and `duration_minutes` are stored but not enforced server-side yet (timer is a frontend concern).
- Evaluation detail is only exposed through the report (after completion), by design, so feedback is never shown mid-interview.
- Test suite emits one third-party deprecation warning (Starlette TestClient / httpx); harmless.
- Gemini is configured and verified (see Phase 4 prerequisites). The Phase 4 provider must use request timeouts and a limited retry on 5xx/timeouts, falling back to a clearly labelled development mode, because Google returned repeated 504s before the first success.

## Commands (Windows)
```
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000     # API + Swagger at /docs
.venv\Scripts\python -m pytest -q                                      # backend tests (183)
.venv\Scripts\python -m app.rag.validate                              # check the question dataset
cd ..\frontend
npm run dev                                                            # http://localhost:5173
```

## Next step
Await review of Phase 5, then Phase 4 (Gemini provider, five agents, LangGraph). Gemini access is already configured and verified.
