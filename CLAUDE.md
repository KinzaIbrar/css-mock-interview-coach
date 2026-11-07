# CSS Mock Interview Coach — Project Guide for Claude Code

Agentic AI mock-interview platform for CSS (Pakistan) aspirants. 48-hour MVP, solo developer, low-spec Windows laptop (16 GB RAM, no GPU).

## Stack
- Frontend: React + Vite + TypeScript, Tailwind v4, shadcn/ui, React Router, Axios, TanStack Query, Recharts, Lucide, React Hook Form + Zod. Tests: Vitest + React Testing Library.
- Backend: Python 3.11 (uv venv at `backend/.venv`), FastAPI, SQLAlchemy, Pydantic, JWT (pyjwt) + bcrypt. Tests: pytest + httpx.
- DB: SQLite (`backend/app.db`, gitignored). AI: Gemini API behind an `LLMProvider` interface; LangGraph orchestration. RAG: curated JSON dataset in `data/questions/` (one file per subject, strictly validated) + keyword retrieval behind a `QuestionRetriever` protocol (`backend/app/rag/`). Schema changes go through Alembic migrations (`backend/alembic/`), applied automatically at startup; never require deleting `app.db`.
- Voice: browser Web Speech / Speech Synthesis only.

## Hardware rules (strict)
No local models, no CUDA, no Docker, no large embedding models. ChromaDB/MediaPipe/OpenCV are optional and deferred. Explain and get approval before installing heavy packages. Never install two libraries doing the same job.

## Working rules
1. Inspect before modifying; never overwrite files blindly.
2. Phased development; the app must stay runnable after each phase. Fix errors before moving on.
3. Keep frontend/backend separate and code modular (routes → services → models; schemas separate).
4. No hardcoded dashboard stats, no fake buttons, no mock data presented as real AI output. Without `GEMINI_API_KEY`, show a clearly labelled dev mode.
5. Never expose secrets; the Gemini key lives only in `backend/.env`. Never commit `.env`.
6. Every user-data query is scoped to the authenticated user.
7. Sample questions/reference answers must be labelled as unverified samples; never claim official sources.
8. Do not claim tests pass unless actually run. Keep PROJECT_STATUS.md current.
9. Stop and give exact instructions for manual actions (API keys, permissions).
10. Priorities: (1) auth, dashboard, setup, AI questions, answer eval, feedback report, history, persistence; (2) LangGraph, RAG, analytics, recommendations; (3) voice, camera, Chroma.
11. Camera feature must not claim to measure confidence/personality.

## Architecture
FastAPI routes → services → SQLAlchemy models. Five agents in `backend/app/agents/` (Question, Conductor, Evaluation, Feedback, Progress) share one LangGraph `InterviewState` (`agents/graph.py`), run per step: answer → evaluate → [follow-up decision] → save; completion → score → feedback → finalise → progress; then the report is built. Gemini sits behind the `LLMProvider` protocol (`agents/gemini_provider.py`: timeout, limited retries on 5xx/429/timeouts, cooldown). **AI results are never fabricated**: if Gemini is unconfigured/failing/invalid, fall back to the labelled dev heuristic (`dev_heuristic` / `dev_rules`, `is_ai_generated=false`). Follow-ups: max 1 per question, 3 per interview, never chained. Never hold a DB write transaction across an LLM call (read -> call Gemini -> write once; SQLite has one writer). SQLite foreign keys are enforced (`enable_sqlite_foreign_keys`). Tests must never call the real API (`tests/conftest.py` forces fallback; use `tests/fakes.py`). See `docs/ai-agents.md`.

## Commands (Windows)
- Backend: `cd backend; .venv\Scripts\python -m uvicorn app.main:app --reload --port 8000` (docs at /docs)
- Backend tests: `cd backend; .venv\Scripts\python -m pytest`
- Live Gemini check (2 real calls, prints no secrets): `cd backend; .venv\Scripts\python -m scripts.check_gemini`
- Validate dataset: `cd backend; .venv\Scripts\python -m app.rag.validate`
- New migration: edit models, then `.venv\Scripts\python -m alembic revision -m "msg"` (write it by hand; `tests/test_migrations.py` fails on drift)
- Frontend: `cd frontend; npm run dev` (port 5173, proxies /api → 8000)
- Frontend tests/build: `npm test`, `npm run build`
- Notes: TypeScript 7 is used (no `baseUrl`; use `paths` with `./`).
