# Frontend Integration Checklist

Derived from the running backend's OpenAPI contract (`/openapi.json`) and the code - nothing here is invented. Base URL: `/api` (Vite proxies `/api` to `localhost:8000`). Swagger: `http://localhost:8000/docs`.

> Implemented in `frontend/` - see `docs/frontend-implementation.md` for how each item below was built and tested.

## 0. Global rules
- **Auth header:** `Authorization: Bearer <access_token>` on everything except `POST /auth/register`, `POST /auth/login`, `GET /health`.
- **Error shapes:** HTTP errors are `{"detail": "<message>"}`; validation errors (422) are `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}`; unexpected failures are `500 {"detail": "Internal server error"}`.
- **Status codes in use:** 400 (not enough questions for the setup), 401 (missing/invalid/expired token), 404 (not found *or not yours*), 409 (state conflict), 422 (validation).
- **Request timeout: set the HTTP client timeout to at least 90 s** for `POST /interviews/answer`, `/follow-up` and `/complete`. These call Gemini and, during a Google outage, can take up to ~65 s before the labelled fallback is used. All other calls are fast. Do not auto-retry these three requests (a duplicate returns 409 and wastes an AI call).
- **Dates** are ISO strings without a timezone suffix (stored UTC).

## 1. Authentication
| Step | Request | Success | Failures |
|---|---|---|---|
| Register | `POST /auth/register` `{email, password (8-72 bytes), full_name}` | 201 `{access_token, token_type, user{id,email,full_name,created_at,preferences}}` | 409 email exists; 422 invalid |
| Login | `POST /auth/login` `{email, password}` | 200 same shape | 401 `Incorrect email or password` (same message for unknown email) |
| Current user | `GET /auth/me` | 200 `user` | 401 |
- Store the token (memory/localStorage), attach it with an Axios interceptor, and on any **401** clear it and redirect to login. Tokens last 12 h; there is **no refresh endpoint and no logout endpoint** (logout = discard the token client-side).
- Protected routes: guard client-side, but the backend is the real enforcement.

## 2. Interview setup -> start
`GET /questions/meta` (200 `{total, subjects[{subject,count,difficulties{easy,medium,hard},topics[{topic,count}]}], tags[], notice}`) provides the subjects, topics and per-level counts for the setup form (disable options that cannot satisfy `num_questions`).

`POST /interviews/start` `{subject, difficulty: easy|medium|hard|mixed (default mixed), num_questions: 1-20 (default 5), duration_minutes: 5-120 (default 30), mode: mock|practice (default mock), topic?}` -> **201** `{interview: InterviewOut, question: {id,subject,topic,difficulty,text}, question_number, total_questions, notice}`.
Errors: 400 with a readable message when the bank has fewer questions than requested; 422 for invalid values. The `question` never contains the reference answer. Show `notice` (sample question bank).

## 3. Interview room (one question at a time)
State machine driven by the responses:

```
start ──► [question N]
            │ POST /interviews/answer
            ▼
   ack.follow_up_question? ──yes──► [follow-up input] ── POST /interviews/follow-up ──┐
            │ no                                                                         │
            ▼                                                                            ▼
   ack.has_next? ──yes──► POST /interviews/next ──► [question N+1]            (then same as "no")
            │ no
            ▼
   POST /interviews/complete ──► ReportOut ──► results page
```
| Action | Request -> response |
|---|---|
| Submit answer | `POST /interviews/answer` `{interview_id, answer_text (1-8000, not blank), time_taken_seconds?}` -> 200 `AnswerAck {interview_id, answered_index, answered_count, has_next, evaluation_saved, evaluation_source, is_ai_generated, follow_up_question?, ai_notice?, fallback_reason?}`. **No scores or feedback are returned.** 409 if already answered or completed. |
| Follow-up | Shown only when `follow_up_question` is non-null. `POST /interviews/follow-up` same body -> 200 `FollowUpAck {interview_id, answered_index, has_next, evaluation_source, is_ai_generated, ai_notice?, fallback_reason?}`. 409 if there is none / already answered / completed. One per question, max 3 per interview, never chained. |
| Next question | `POST /interviews/next` `{interview_id}` -> 200 `{interview_id, finished, question_number, total_questions, question|null}`. **409 while a follow-up is pending** or the question is unanswered. When `ack.has_next` is false you can skip `/next` and call `/complete`. |
| Resume / refresh | `GET /interviews/{id}` -> `{interview, current_question|null, question_number, total_questions, answered_indexes[], report_available, pending_follow_up|null}`. If `pending_follow_up` is set, show the follow-up input; otherwise if `current_index` is answered show "Next". |
| Complete / End interview | `POST /interviews/complete` `{interview_id}` -> 200 `ReportOut` (idempotent). 409 if **no question has been answered**. Unanswered questions count as 0 and appear as `skipped`. |
- **Timer:** the server stores `duration_minutes` and `started_at` but does **not enforce** them. The client runs the countdown and calls `/complete` on expiry. Send `time_taken_seconds` per answer (optional).
- Do not display anything about scores before `/complete`; the backend does not send any.
- Keep the answer text in client state until the response arrives so a failed request can be retried with the same text.

## 4. Loading states
Show a visible "Evaluating your answer..." state for `answer` and `follow-up` and "Preparing your report..." for `complete` (up to ~65 s in an outage; usually seconds). Disable the submit button and block double-submit. After a Gemini failure the next answers return quickly for ~30 s (cooldown) with the fallback label.

## 5. AI / fallback labelling (must be shown, never hidden)
| Where | Field | Rule |
|---|---|---|
| Answer / follow-up ack | `ai_notice` (non-null) | Show it as a visible banner/toast: the answer was **not** AI-evaluated. `fallback_reason` is a machine code (`not_configured`, `quota_exhausted`, `rate_limited`, `timeout`, `http_503`, `http_401`, `invalid_output`, `cooldown`, `unexpected_error`, ...); do not show it as the main message. |
| Follow-up ack | `ai_notice` mentioning the "original AI evaluation was kept" | Show it; the reply was saved but not re-evaluated. |
| Report | `evaluation_source` | `gemini` -> badge "AI evaluation" + `evaluation_model`; `mixed` -> warning "partly AI"; `dev_heuristic` -> badge "Development evaluation (not AI)". Always render `notice`. |
| Report per question | `questions[].evaluation_source` / `is_ai_generated` | Per-question badge (important for `mixed`). `skipped` questions have none. |
| Report feedback | `feedback_source` (`gemini` / `dev_rules`), `feedback_is_ai_generated` | Separate badge for the summary/improvements block. |
| Report | `progress_note` | Rule-based comparison with the previous session: label it as such, not as AI. |
| Report / questions | `reference_notice`, `QuestionList.notice`, `is_sample` | Reference answers are **unverified samples**; keep the disclaimer visible next to model answers. |
| Dashboard | `recommendations_source: "rule_based"`, `is_ai_generated: false`, `notice` | Label "AI Recommendations" page content accordingly: these are rule-based, not AI. |

## 6. Results page (`ReportOut`)
`interview, overall_score (0-100), criteria_scores{relevance,subject_knowledge,accuracy,reasoning,structure,clarity (each 0-10)}, strengths[], weaknesses[], missing_info[], summary, improvements[], revision_topics[], next_practice[], questions[QuestionResult], evaluation_source, is_ai_generated, evaluation_model|null, notice, reference_notice, feedback_source, feedback_is_ai_generated, progress_note|null`.
`QuestionResult`: `order_index, question_id, question, topic, difficulty, skipped, answer_text|null, scores|null, overall|null, strengths[], weaknesses[], missing_info[], model_answer, evaluation_source|null, is_ai_generated, follow_up_question|null, follow_up_answer|null`.
`GET /reports/{interview_id}` returns the same object (409 until completed; 404 if not yours).

## 7. Dashboard, history, progress, question bank
| Page | Request -> response |
|---|---|
| Dashboard | `GET /dashboard` -> `{total_interviews, in_progress_count, average_score|null, best_score|null, weakest_subject|null, score_trend[{interview_id,subject,score,completed_at}], subject_performance[{subject,sessions_count,avg_score,best_score,last_score}], recent_interviews[InterviewOut], recommendations[{title,detail,subject|null}], recommendations_source, is_ai_generated, notice}`. New users get nulls/empty lists - render an empty state, not zeros. |
| History | `GET /interviews/history?limit=50&offset=0` -> `InterviewOut[]` newest first (`status` is `in_progress` or `completed`; link in-progress rows to resume and completed rows to `/reports/{id}`). No server-side filtering; filter client-side. |
| Analytics | `GET /progress` -> `{total_completed, overall_average|null, subjects[...], trend[...]}`. |
| Question bank | `GET /questions?subject=&topic=&difficulty=&tag=&search=&limit=20&offset=0` -> `{items[QuestionOut], total, limit, offset, notice}`; `search` ranks by relevance and sets `score`; `GET /questions/{id}` -> `QuestionOut` (includes `reference_answer`, `keywords`, `evaluation_criteria`, `tags`, `explanation`, `is_sample`). |

## 8. Voice (browser only - no backend work)
- Speech-to-text: Web Speech API (`SpeechRecognition` / `webkitSpeechRecognition`) writing into the same text box that is sent as `answer_text`. Feature-detect, handle permission denial, and **always keep typing available**. Chrome/Edge support it; Firefox does not.
- Text-to-speech: `speechSynthesis` reading `question.text` and `follow_up_question`.
- The backend only ever receives text. There are no audio endpoints.

## 9. Backend gaps for the planned pages
These are **not** blockers for the core interview journey, but the matching UI cannot be completed without them:
1. **Profile / Settings:** `user.preferences` is returned but there is **no endpoint to update it or the profile**, and **no change-password endpoint** (`PATCH /auth/me` etc. do not exist).
2. **"End interview" with zero answers:** `/complete` returns 409 if nothing was answered and there is **no abandon/cancel endpoint**, so such an interview stays `in_progress` (it appears in history and in `in_progress_count`).
3. **Resume detail is thin:** `GET /interviews/{id}` does not return the answers already given, only which indexes are answered.
4. **No server-side enforcement of `duration_minutes` / `mode`.**
5. **No refresh/logout endpoints** (see section 1).
6. **CORS** allows only `http://localhost:5173` by default (`CORS_ORIGINS`).

## 10. Added after the start-error audit
- **Setup form:** for topic + a specific difficulty the metadata has no count, so the form calls `GET /questions?subject&topic&difficulty&limit=1` and uses `total` (same filters as `POST /interviews/start`) to validate before submitting. A refused request (400) is shown next to the Start button, scrolled into view and focused.
- **`GET /health` -> `ai_availability`:** use it for the "Gemini configured / quota used up / rate-limited" indicator; refresh it after any answer that returned an `ai_notice`.
