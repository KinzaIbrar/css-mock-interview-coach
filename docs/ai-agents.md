# AI Agents (Phase 4)

## Principles
- **Never fabricate.** If Gemini is not configured, times out, fails, or returns output that does not match the required structure, the step falls back to the keyword/length development heuristic and is **labelled** on every response and in the database (`source = dev_heuristic`, `is_ai_generated = false`).
- **Grounded.** Questions come from the curated bank (Phase 5). The evaluation prompt contains the question, the reference answer (an *unverified sample*), the important concepts and the evaluation criteria. The model is told to accept other correct points.
- **Candidate text is data.** Answers are wrapped in delimiter tags, any look-alike tags are stripped, and the system prompt tells the model never to follow instructions found inside them. Scores are range-checked: out-of-range output is rejected, not clamped. The overall score is computed by the application from the six criteria, never taken from the model.
- **No database write while waiting for Gemini.** Each step reads, calls Gemini, and only then writes everything (answer, follow-up reply, evaluation) in a single transaction. SQLite allows one writer at a time, so an open write transaction during a slow or retried call would freeze every other user; it also means an interrupted request leaves nothing half-saved (the candidate simply resubmits).
- **A failed re-evaluation never downgrades.** If Gemini cannot re-evaluate after a follow-up reply, the reply is saved and the existing AI evaluation is kept (the response says so).
- **Bounded.** Follow-ups: at most one per question and `MAX_FOLLOW_UPS_PER_INTERVIEW` (3) per interview, and they are never chained. Gemini calls: per-attempt timeout, at most 2 retries on 5xx / 429 / timeouts inside a total time budget, then a cooldown during which calls fail fast.
- **Secrets.** The key is read only from `backend/.env`, redacted from every error, and never logged or returned by the API.

## The five agents (`backend/app/agents/`)
| Agent | File | Uses LLM? | Role |
|---|---|---|---|
| Question | `question_agent.py` | no | Retrieves candidates (Phase 5 retriever) and picks the interview's questions. |
| Interview Conductor | `conductor_agent.py` | no (rules) | Builds the conversation context (last 3 questions + scores) and decides whether a follow-up may be asked / accepted. |
| Answer Evaluation | `evaluation_agent.py` | **Gemini** | Scores relevance, subject knowledge, accuracy, reasoning, structure, clarity (0-10), strengths, weaknesses, missing information, and optionally proposes a follow-up. |
| Feedback | `feedback_agent.py` | **Gemini** | Personalised summary, improvements and revision topics (restricted to topics actually asked). |
| Progress Tracking | `progress_agent.py` | no (rules) | Updates the per-subject aggregate and compares with the previous session; output is labelled rule-based. |

Supporting modules: `llm_provider.py` (provider-neutral `LLMProvider` protocol), `gemini_provider.py` (google-genai implementation with the retry/cooldown policy), `runtime.py` (`get_provider()`; returns `None` when no key is configured), `schemas.py` (required JSON shapes), `errors.py`, and `app/prompts/` (prompt text). Swapping providers means implementing `LLMProvider` and returning it from `runtime.get_provider()`.

## LangGraph workflow (`graph.py`)
All agents share one `InterviewState` (user id, interview id, subject, difficulty, current question, previous questions, candidate answers, evaluation results, follow-up count, interview status, final feedback, plus step inputs/outputs). Because an interview is request/response, the workflow runs as two short graphs and the database is the memory between requests:

```
Interview start      Question agent: retrieve and select questions          (QuestionAgent, in start_interview)
Answer step          START -> evaluate -> [follow_up_decision] -> save_evaluation -> END
Follow-up reply      same graph, re-evaluating answer + follow-up together, follow-ups disabled
Completion step      START -> score -> feedback -> finalise -> progress -> END      then the report is built
```
The conditional edge after `evaluate` routes to `follow_up_decision` only when follow-ups are allowed *and* Gemini proposed one. There are no loops.

## Data saved
Existing tables are reused: `answers` (candidate text), `evaluations` (six scores, overall, strengths/weaknesses/missing info, `source`, `is_ai_generated`, `model`), `feedback` (`source`, `is_ai_generated`, `model`), `progress`. Migration `0003` adds the `follow_ups` table (question, reply) and the `model` columns.

## Rate limits and quota (HTTP 429)
A 429 is **not** treated like a flaky network. Google says which limit was hit and how long to wait (`QuotaFailure.quotaId`, `RetryInfo.retryDelay`), and the provider reads that:
- **Daily quota exhausted** (`quotaId` contains `PerDay`, e.g. the free tier's *20 requests per day per model*): **never retried** (one request, no sleeps). The provider stays quiet for Google's retry delay, capped by `GEMINI_QUOTA_COOLDOWN_CAP_SECONDS` (default 900 s), then probes again. During that window every call fails fast with the **real** reason `quota_exhausted` (not a generic "cooldown"), and nothing is sent to Google.
- **Per-minute rate limit:** waits the delay Google asked for (not a blind 2 s) when it fits the request's time budget, otherwise fails fast with `rate_limited` and pauses for that delay.
- A 429 without details is retried at most `GEMINI_MAX_RETRIES` times with the normal backoff, then reported as `rate_limited`.
- 5xx / timeouts keep the generic short cooldown (`cooldown`); no request is made while it lasts, so it does not claim a new timeout.
- Evaluation and feedback share the same per-model quota, so one cooldown correctly covers both; once it expires each operation tries Gemini again independently. A failed call never overwrites an existing AI evaluation.
- `GET /api/health` returns `ai_availability` `{available, reason, retry_after_seconds}` so clients can show whether Gemini is usable **right now** (it makes no call to Google).
- **Practical consequence:** on the free tier (20 requests/day/model) one 5-question interview uses about 6 requests (5 evaluations + 1 feedback; follow-ups add more), i.e. roughly 3 interviews per day. Use a billed key or a different model for more.

## Configuration (`backend/.env`)
Fallback reasons you may see: `not_configured`, `quota_exhausted`, `rate_limited`, `timeout`, `http_<status>`, `invalid_output`, `invalid_score`, `cooldown`, and `unexpected_error` (any other failure inside the AI layer is caught and falls back too, so an AI bug can never block an interview).

`GEMINI_API_KEY`, `GEMINI_MODEL` (default `gemini-3.8-flash`), and optional `GEMINI_TIMEOUT_SECONDS` (30), `GEMINI_MAX_RETRIES` (2), `GEMINI_RETRY_DELAY_SECONDS` (2), `GEMINI_BUDGET_SECONDS` (65), `GEMINI_COOLDOWN_SECONDS` (30), `GEMINI_QUOTA_COOLDOWN_CAP_SECONDS` (900), `MAX_FOLLOW_UPS_PER_INTERVIEW` (3).

## Verifying the live connection
```
cd backend
.venv\Scripts\python -m scripts.check_gemini
```
Makes 2 real calls (evaluation + feedback) and exits 0 only if Gemini itself answered both. If Google is overloaded it prints a `FALLBACK (reason)` line instead - wait and rerun.

## Testing
Tests never call Gemini: `tests/conftest.py` forces dev-fallback mode, and `tests/fakes.py` provides a scriptable fake provider and fake SDK client. See `tests/test_gemini_provider.py` (retries, timeouts, cooldown, secrets), `tests/test_agents.py` (scoring, validation, fallback, prompt safety) and `tests/test_ai_interview_flow.py` (end-to-end flows, follow-ups, persistence, failures).
