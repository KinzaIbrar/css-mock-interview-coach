# Frontend Implementation (Phase 2)

React 19 + Vite 8 + **TypeScript** (the project's existing stack; see "Deviations") + Tailwind CSS v4 with CSS-variable design tokens, React Router 7, Axios, TanStack Query, React Hook Form + Zod, Recharts, Lucide icons. No new packages were installed for Phase 2.

## Running it
```
cd backend;  .venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
cd frontend; npm run dev            # http://localhost:5173  (proxies /api -> http://localhost:8000)
npm run build | npm run lint | npm test
```
**Environment** (`frontend/.env.example`, placeholders only): `VITE_API_BASE_URL` - default `/api` (works with the dev proxy). No secrets ever belong in the frontend; the Gemini key lives only in `backend/.env`.

## Pages and routes
| Route | Page | Access | Data source |
|---|---|---|---|
| `/login`, `/register` | Login, Registration | public only (signed-in users are redirected) | `POST /auth/login`, `/auth/register` |
| `/dashboard` (`/` redirects here) | Dashboard | protected | `GET /dashboard` |
| `/interviews/new` | Interview setup | protected | `GET /questions/meta`, `POST /interviews/start` |
| `/interviews/:id` | Interview room (distraction-free layout, no sidebar) | protected | `GET /interviews/{id}`, `POST /interviews/answer`, `/follow-up`, `/next`, `/complete` |
| `/interviews/:id/results` | Report | protected | `GET /reports/{id}` |
| `/history` | Interview history | protected | `GET /interviews/history?limit&offset` |
| `/questions` | Question bank (extra, supported by the backend) | protected | `GET /questions/meta`, `GET /questions` |
| `/profile` | Profile | protected | `GET /auth/me` (via context), `GET /health` |
| `*` | Not found | public | - |

## Structure (`frontend/src`)
- `api/` - `client.ts` (Axios instance, token storage, `ApiError` normalisation, 401 handling, `AI_TIMEOUT_MS`), `types.ts` (mirrors the backend schemas), `auth.ts`, `interviews.ts`, `content.ts` (dashboard, reports, questions).
- `context/AuthContext.tsx`, `routes/guards.tsx` (`ProtectedRoute`, `PublicOnlyRoute`).
- `components/ui/` (Button, Card, Form controls, Alert/Spinner/Skeleton/EmptyState/ErrorState, Badge, ProgressBar), `layout/` (AppShell, FocusLayout, AuthLayout, Logo), `dashboard/`, `interview/` (AnswerComposer, EvaluatingPanel, InterviewTimer, VoiceControls, AiNotice, StatusBadge), `evaluation/` (ScoreRing, CriteriaBars, QuestionResultCard, SourceBadge).
- `hooks/` (`useSpeechRecognition`, `useSpeechSynthesis`), `utils/` (format, schemas, interview helpers, button styles), `pages/`, `test/`.
- Route-level code splitting: the charting library loads only with the dashboard.

## Design system
Tokens live in one `@theme` block in `src/index.css`: surface/canvas/ink/muted/line colours, one blue accent (`primary`), semantic success/warning/danger, radii, shadows, font stack. Text/background pairs were chosen for WCAG AA contrast. Status is never colour-only: every state has an icon and words (badges, alerts, score bands). Motion is limited to short fades and respects `prefers-reduced-motion`. Light theme only.

## Authentication behaviour
- The backend issues a 12-hour bearer JWT. It is kept in `localStorage` (`cmic.token`) so a refresh keeps the session; access is wrapped in try/catch with an in-memory fallback.
- On start, a stored token is validated with `GET /auth/me`; any **401** from a protected call clears the token, clears the query cache and sends the user to `/login` (with a return path). A 401 from the login form itself only shows "Incorrect email or password".
- **Sign out is client-side only** (there is no logout endpoint): it discards the token and cached data. There is no refresh token; after 12 h the user signs in again.
- Trade-off: `localStorage` tokens are readable by any script running on the page (XSS). The app renders no user HTML and has no third-party scripts, but an httpOnly-cookie design would need backend changes.

## Interview setup: availability and errors
- Subject, topic and "mixed" counts come from `GET /questions/meta`. For **topic + a specific difficulty** (not in the metadata) the form asks `GET /questions?...&limit=1` for the exact `total`, shows "N available for this choice", and refuses an impossible request before sending it (so it never produces a 400). While the count loads, the server decides.
- A server refusal (400/422) is rendered directly above the Start button, scrolled into view and focused (`role=alert`), because on small screens the form's top is far from the button.
- The Start button is disabled while the request is pending, so a double click sends one request.

## AI status
The sidebar and Profile use `GET /health`: "Gemini configured" only when Gemini is configured **and** usable; otherwise "Gemini quota used up", "Gemini is rate-limited" or "Gemini temporarily unavailable" with when it will be tried again. It is refreshed after any answer that falls back.

## The interview room (key behaviours)
- Loads state from `GET /interviews/{id}`, so refresh/resume works (including a pending follow-up).
- One request at a time (synchronous lock + disabled controls + keyboard shortcut blocked). AI calls use a **120 s timeout** and show a progress panel whose message changes after 8 s and 25 s.
- **No scores or feedback appear mid-interview** because the backend deliberately does not return them; the room shows "Answer submitted", where it came from (AI / development evaluation) and any `ai_notice`. Scores appear in the report.
- **Safe retry:** on 409, timeout, network error or 5xx the page re-reads the interview before doing anything. If the answer was saved it says so; if not, the text is kept and a retry is safe; if the server cannot be reached the next attempt checks first and never sends the same answer twice.
- Follow-ups: shown when `follow_up_question` is returned or `pending_follow_up` is set; "Next"/"Finish" are not offered until it is answered; a 409 from `/next` resynchronises state.
- The countdown timer is client-side only; reaching zero does not auto-submit or stop anything (the server does not enforce duration).

## Evaluation source labelling
`gemini` -> "AI evaluation" (+ model); `dev_heuristic` -> "Development evaluation · not AI"; `mixed` -> "Partly AI" with per-question badges; feedback `dev_rules` -> "Rule-based feedback · not AI"; `progress_note` -> "Progress · rule-based, not AI"; dashboard suggestions are labelled rule-based. The report banner always shows the backend's `notice`; room responses show `ai_notice`.

## Voice (optional)
- Dictation uses the browser Web Speech API (`SpeechRecognition` / `webkitSpeechRecognition`), reading aloud uses `speechSynthesis`. Both are feature-detected: unsupported browsers (e.g. Firefox) see a text-only message and nothing breaks. The microphone is stopped while a request is pending and on unmount. Permission denial, no microphone, network and no-speech errors have specific messages. Transcribed text goes into the same editable box.
- Chrome/Edge send audio to their own speech service; the UI says so. **Actual speaking/listening was not tested** (headless environment, no microphone/speakers).

## Known limitations
- Backend gaps (see `docs/frontend-integration.md` section 9): no profile/preferences/password endpoints (Profile is read-only and says so); no abandon endpoint (finishing with zero answers returns 409 and the interview stays in progress); resume does not return previously typed answers; no refresh/logout.
- Duration and mode are not enforced by the server (stated on the setup page).
- History pagination is previous/next only: the API returns a plain list without a total, so a final page can be empty.
- Gemini was unavailable during development, so the **live AI path was never exercised in the browser** (only fallback, via an invalid key, and mocked AI responses in tests).
- Light theme only; no landing/marketing page (the root redirects to the dashboard / login).

## Deviations from the brief
- **TypeScript, not JavaScript:** the repository's frontend was already TypeScript (and `CLAUDE.md` specifies it); converting would have been a migration. Files are `.tsx`/`.ts`.
- API modules are `auth.ts`, `interviews.ts`, `content.ts` (dashboard + reports + questions) rather than one file per resource.
- A Question Bank page was added because the backend supports it; the profile "settings" are limited to what exists.

## Testing
- `npm test` (Vitest + Testing Library): 97 tests - API client (error mapping, 401 handling, timeouts), validation schemas, formatting, auth pages and route guards, setup, dashboard, history, results (gemini / fallback / mixed labelling, skipped, follow-up) and the interview room (follow-ups, duplicate-submit prevention, 409 and unknown-outcome recovery, finishing). Mutation checks confirmed the recovery tests fail when that logic is broken.
- Real-browser QA (Playwright against the real backend on a temporary database with an invalid Gemini key): registration, validation errors, protected-route redirect, invalid-token handling, login failure/success, setup, answering with the labelled fallback, a real 409 recovery, finishing early, the report, phone-width layout and overflow checks on every page, mobile menu. Console showed only the intentional 401/409 responses.
- Not tested: tablet width in a browser, real voice input/output, automated accessibility audit (axe), cross-browser (only Chromium).
