# API Documentation

Interactive docs (Swagger UI): `http://localhost:8000/docs` · OpenAPI JSON: `/openapi.json`.
All paths are prefixed with `/api`. Request and response bodies are JSON.

> **Development mode.** Until the Gemini integration (Phase 4), answer evaluation and feedback come from a
> simple keyword/length heuristic (`evaluation_source: "dev_heuristic"`, `is_ai_generated: false`). Responses that
> carry evaluation data include a `notice` saying so. The bundled question bank is a **sample, unverified**
> dataset (`is_sample: true`), not official CSS material.

## Conventions
- **Auth:** `Authorization: Bearer <access_token>` on every endpoint except `/auth/register`, `/auth/login`, `/health`.
- **Errors:** `{"detail": "<message>"}`; validation errors (422) return FastAPI's `detail` list.
  Common codes: 400 bad request, 401 unauthenticated, 404 not found, 409 conflict, 422 validation.
- **Data isolation:** every interview, answer, report, dashboard and progress query is scoped to the authenticated
  user. Another user's resources return **404** (never 403) so their existence is not revealed.
- **Scores:** per-criterion scores are 0-10; `overall` / `overall_score` are 0-100. Unanswered questions count as 0.
- **Subjects:** Pakistan Affairs, Current Affairs, Islamic Studies, General Knowledge, English,
  International Relations, Governance and Constitutional Studies.
- **Difficulty:** `easy | medium | hard` (questions); interviews also accept `mixed`. **Mode:** `mock | practice`.

## Health
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | no | `{status, environment, ai_mode}`; `ai_mode` states whether a Gemini key is configured. |

## Authentication
| Method | Path | Success | Errors |
|---|---|---|---|
| POST | `/auth/register` | 201 `TokenResponse` | 409 email already registered (case-insensitive); 422 invalid email, password < 8 chars or > 72 bytes, blank name |
| POST | `/auth/login` | 200 `TokenResponse` | 401 `Incorrect email or password` (identical for unknown email and wrong password) |
| GET | `/auth/me` | 200 `UserOut` | 401 missing / invalid / expired token |

Register body: `{"email", "password", "full_name"}` · Login body: `{"email", "password"}`.
`TokenResponse`: `{access_token, token_type: "bearer", user: {id, email, full_name, created_at, preferences}}`.
Tokens are HS256 JWTs (`sub` = user id) and expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 720).

## Questions (question bank)
The bank is a curated **sample, unverified** set (112 questions, see `docs/dataset.md`).

| Method | Path | Description |
|---|---|---|
| GET | `/questions` | Filters (all optional, combinable): `subject`, `topic` (exact, case-insensitive), `difficulty` (`easy\|medium\|hard`), `tag`, `search`, plus `limit` (1-100, default 20) and `offset`. Returns `{items, total, limit, offset, notice}`. With `search`, items are **ranked by relevance** (best first), only matching questions are returned and each item carries a `score`; without `search`, `score` is `null` and order is by subject then id. `total` is the match count before pagination. Behaviour change since Phase 3: search matches whole words (with light plural stemming) and word prefixes of 4+ characters, no longer arbitrary substrings (`constitu` matches, `stitution` does not); `search` may now be up to 200 characters. |
| GET | `/questions/meta` | What the bank contains, for building filters: `{total, subjects: [{subject, count, difficulties: {easy, medium, hard}, topics: [{topic, count}]}], tags, notice}`. |
| GET | `/questions/{id}` | One question; 404 if unknown. |

Question fields: `id, subject, topic, difficulty, text, reference_answer` (the dataset's *expected answer*), `keywords` (*important concepts*), `evaluation_criteria`, `tags`, `explanation`, `is_sample`, `score`.

## Interviews
Flow: `start` → (`answer` → `next`) × N → `complete` → `reports/{id}`.

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/interviews/start` | `{subject, difficulty="mixed", num_questions=5 (1-20), duration_minutes=30 (5-120), mode="mock", topic?}` | 201. Picks distinct questions, avoiding those from the user's last 5 interviews where possible and spreading topics; `mixed` covers all levels and runs easy to hard; optional `topic` restricts to one topic. Returns `{interview, question, question_number, total_questions, notice}`. 400 if the bank has fewer matching questions than requested (message names the subject/topic and how many exist). The question never includes the reference answer. |
| POST | `/interviews/answer` | `{interview_id, answer_text (1-8000 chars), time_taken_seconds?}` | Saves the answer and its evaluation. Returns only an acknowledgement `{answered_index, answered_count, has_next, evaluation_saved, evaluation_source}`; **feedback is not revealed during the interview**. 409 if the current question is already answered or the interview is completed. |
| POST | `/interviews/next` | `{interview_id}` | Advances to the next question: `{finished, question_number, total_questions, question}`. `finished: true` with `question: null` after the last one. 409 if the current question is unanswered. |
| POST | `/interviews/complete` | `{interview_id}` | Computes the overall score, stores feedback, updates progress, and returns the full report. Idempotent (returns the same report if already completed). 409 if nothing has been answered. |
| GET | `/interviews/history` | - | The caller's interviews, newest first. Query: `limit` (1-200, default 50), `offset`. |
| GET | `/interviews/{id}` | - | `{interview, current_question, question_number, total_questions, answered_indexes, report_available}`; use it to resume an in-progress interview. Evaluation data is only available via the report. |

`InterviewOut`: `{id, subject, difficulty, num_questions, duration_minutes, mode, status (in_progress|completed), current_index, answered_count, started_at, completed_at, overall_score}`.

## Reports
| Method | Path | Description |
|---|---|---|
| GET | `/reports/{interview_id}` | Full report for a **completed** interview (409 otherwise): `overall_score`, `criteria_scores` (relevance, subject_knowledge, accuracy, reasoning, structure, clarity), `strengths`, `weaknesses`, `missing_info`, `summary`, `improvements`, `revision_topics`, `next_practice`, per-question results (answer, scores, model answer, skipped flag), `evaluation_source`, `is_ai_generated`, `notice`, `reference_notice`. |

## Dashboard
| Method | Path | Description |
|---|---|---|
| GET | `/dashboard` | Computed from the caller's saved interviews: `total_interviews` (completed), `in_progress_count`, `average_score`, `best_score`, `weakest_subject` (null for a new user - nothing is fabricated), `score_trend` (last 10), `subject_performance`, `recent_interviews` (last 5), `recommendations` (rule-based, `is_ai_generated: false`). |

## Progress
| Method | Path | Description |
|---|---|---|
| GET | `/progress` | `{total_completed, overall_average, subjects: [{subject, sessions_count, avg_score, best_score, last_score}], trend: [{interview_id, subject, score, completed_at}]}`. Per-subject aggregates are updated whenever an interview is completed. |

## Example
```bash
curl -X POST localhost:8000/api/auth/register -H "Content-Type: application/json" \
  -d '{"email":"me@example.com","password":"a-long-password","full_name":"Me"}'
# use the returned access_token:
curl -X POST localhost:8000/api/interviews/start -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"subject":"English","difficulty":"mixed","num_questions":2,"duration_minutes":20}'
```
