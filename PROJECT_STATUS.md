# Project Status

**Current phase:** Phase 3 (backend core) complete. Awaiting approval to start Phase 4 (Gemini + agents + LangGraph).

## Completed
- **Phase 0:** environment audit and plan approved.
- **Phase 1:** folder structure, `.gitignore`, FastAPI app, Vite/React/TS/Tailwind frontend with `/api` proxy, CLAUDE.md.
- **Phase 3 (backend core):**
  - SQLAlchemy models: User, Interview, Question, Answer, Evaluation, Feedback, Progress (FKs, relationships, timestamps). Tables are created on startup via `create_all`.
  - Auth: register / login / me, bcrypt hashing, JWT (pyjwt), `get_current_user` dependency, 404-based data isolation.
  - Endpoints: auth (3), questions (2), interviews (start, answer, next, complete, history, detail), reports, dashboard, progress, health. See `docs/api-documentation.md`.
  - Sample question bank `data/css_questions.json` (21 questions, 3 per subject across the 7 subjects) seeded idempotently at startup. **Labelled sample/unverified.**
  - Dev-mode evaluator and feedback (`services/dev_evaluator.py`, `services/report_service.py`): deterministic keyword/length heuristics, **not AI**. Every evaluation/report carries `evaluation_source: "dev_heuristic"`, `is_ai_generated: false` and a notice.
  - Dashboard/progress statistics are computed from saved records; a new user gets nulls/empty lists, nothing fabricated.
- **Verification (actually run):** `pytest` → **66 passed**; live curl journey against uvicorn + real SQLite (register → start → answer/next ×2 → complete → dashboard; unauthenticated call → 401); `/openapi.json` lists 15 paths. Test database file deleted afterwards.

## Remaining
- Phase 5: full curated dataset + keyword retrieval module (`app/rag/`).
- Phase 4: Gemini provider (`LLMProvider`), five agents, LangGraph orchestration, replace the dev evaluator/feedback. Add `google-genai`, `langgraph`.
- Phase 2: frontend pages and design system (shadcn/ui not initialised yet).
- Phase 6: frontend ↔ backend integration. Phase 7: frontend tests and full-journey check. Phase 8: README / architecture docs.

## Known issues / notes
- No Alembic yet: schema changes require deleting `backend/app.db` (dev) until migrations are added.
- Questions are chosen randomly from the sample bank; "AI question generation" and follow-up questions arrive in Phase 4.
- `mode` (mock/practice) and `duration_minutes` are stored but not enforced server-side yet (timer is a frontend concern).
- Evaluation detail is only exposed through the report (after completion), by design, so feedback is never shown mid-interview.
- Test suite emits one third-party deprecation warning (Starlette TestClient / httpx); harmless.
- No `GEMINI_API_KEY` configured. Needed before Phase 4 testing (create at aistudio.google.com, put in `backend/.env`; never commit or paste it).

## Commands (Windows)
```
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000     # API + Swagger at /docs
.venv\Scripts\python -m pytest -q                                      # backend tests
cd ..\frontend
npm run dev                                                            # http://localhost:5173
```

## Next step
Await approval, then Phase 5 (dataset + retrieval) followed by Phase 4 (AI agents), or the order you prefer.
