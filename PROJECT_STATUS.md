# Project Status

**Current phase:** Phase 1 complete → ready for Phase 3 (backend), see roadmap order below.

## Completed
- Phase 0: environment audit and plan approved.
- Phase 1: folder structure, `.gitignore`, FastAPI app with `/api/health` + CORS + settings + SQLite session, Vite/React/TS/Tailwind frontend with `/api` proxy, CLAUDE.md. Verified: both servers run, proxy returns health JSON, `npm run build` passes, Swagger at /docs returns 200.

## Roadmap (backend before frontend polish)
Phase 3 backend (models, auth, routes, services) → Phase 5 RAG dataset → Phase 4 Gemini + agents + LangGraph → Phase 2 frontend pages → Phase 6 integration → Phase 7 tests → Phase 8 docs.

## Remaining
Everything beyond foundation: models, auth, endpoints, dataset, agents, UI pages, tests, docs.

## Known issues
- shadcn/ui not initialised yet (Phase 2).
- No `GEMINI_API_KEY` configured: AI runs in dev mode until set.
- Frontend/backend tests not yet written. `alembic`, `google-genai`, `langgraph` not installed yet.

## Commands
See CLAUDE.md → Commands.

## Next step
Phase 3: SQLAlchemy models (User, Interview, Question, Answer, Evaluation, Feedback, Progress), auth (register/login/me), then dashboard/interview routes with pytest coverage.
