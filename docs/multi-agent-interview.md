# Multi-agent conversational interview

## The four agents (what is real)

| UI agent | Implemented by | Uses Gemini? | Status shown in the UI comes from |
|---|---|---|---|
| Interviewer Agent | `interviewer_agent.py` (greeting, intro prompt, adaptive order), `question_agent.py`, `conductor_agent.py` (follow-up rules, repeat check) | No (rules) | room state + Web Speech (speaking/listening) |
| Evaluator Agent | `evaluation_agent.py` + `prompts/evaluation.py` | Yes, with labelled `dev_heuristic` fallback | in-flight request + backend `trace` (completed / error) + `GET /api/agents` availability |
| Coaching Agent | `coaching_agent.py` (rule-based plan), `feedback_agent.py` (Gemini summary, `dev_rules` fallback), `progress_agent.py` | Feedback part only | "Coaching" only while the report is being built |
| Orchestration Agent | `agents/graph.py` (LangGraph) | No | in-flight request; `trace` |

Statuses (`Active/Speaking/Listening/Evaluating/Coaching/Waiting/Completed/Error`) are derived in `frontend/src/utils/agentStatus.ts`
**only** from the real room state and real backend results. Nothing is animated on a timer.

## Conversation flow

`POST /interviews/start` with `with_introduction: true` (the setup page sends it) →
greeting + "Tell me about yourself" → `POST /interviews/introduction` (context only, **not scored**; 409 if repeated or if the
interview has no intro step) → Q1 → `POST /answer` → optional follow-up (`POST /follow-up`) → `POST /next` → Q2 …

* Main questions are numbered 1..N. A follow-up carries its parent's number and is **not** counted (`main_questions_answered`).
* `GET /interviews/{id}` returns the whole `conversation`, so a reload resumes exactly (pending introduction / follow-up included).
* Follow-ups: max 1 per question, 3 per interview, never chained; a follow-up that is a near-duplicate (Jaccard ≥ 0.8) of the
  main question or an earlier follow-up is dropped by the Conductor.
* **Follow-up replies are evaluated separately** (`evaluation` prompt in `reply_only` mode) and stored on the `follow_ups` row.
  The main answer's evaluation is never re-scored or replaced, so a failed AI call can never erase a good evaluation. The report
  shows each follow-up score and `follow_up_average`; neither changes `overall_score`.
* Adaptive difficulty (mixed interviews only): after a main answer, the next *unasked* question is swapped for a harder one when the
  last score ≥ 70, easier when < 40. Nothing is repeated or dropped.
* Duplicate submissions: 409s from the backend + a synchronous lock and re-check-before-resend in the room.

## Evaluation honesty

Without a working Gemini, evaluation is `dev_heuristic` and every response, trace entry and report section says so
(`is_ai_generated=false`). The coaching plan is `rule_based`. No result is fabricated.

## Avatar

`components/avatar/` – a procedural Three.js (React Three Fiber) interviewer, lazy-loaded. States: idle (breathing, blinking),
speaking, listening (head tilt), waiting. Speech uses `speechSynthesis` with **Repeat question / Stop speaking**; the caption
under the avatar shows the exact text being read.

* **Mouth movement is an approximate open/close rhythm while the browser is speaking. It is not phoneme/viseme lip-sync** – the Web
  Speech API exposes no audio or phoneme data.
* If WebGL is unavailable or the scene throws, a flat 2D stand-in with the same states is shown, with a note.
* No licensed GLB/VRM model was available, and an unlicensed one must not be used, so the avatar is procedural (no asset licence
  question). To use a licensed model later, add it under `frontend/public/avatar/` and load it in `AvatarScene.tsx` – this is the
  one avatar requirement **not** met (blocker: no licensed asset provided).

## Camera and non-verbal observations

* Off by default. `useCamera` asks the browser for permission **only** after the user presses "Turn on camera", after the panel has
  explained what happens. A "Camera on" indicator and a "Turn off camera" button are always available; tracks are stopped on
  turn-off, on finishing and on leaving the page. Denied / missing camera / unsupported browser each get a message and the
  interview continues normally.
* Processing is in the browser (MediaPipe Tasks Vision Pose Landmarker "lite", CPU delegate, ~5 analyses/second). WASM and model
  are served locally from `frontend/public/vision/` (created by `scripts/setup-vision-assets.mjs` on `npm run dev`/`build`; gitignored;
  if the download fails the preview still works and metrics say "Not enough data").
* Frames and landmarks are never stored or sent. `ObservationAggregator` keeps counters only. `POST /interviews/observations` accepts
  bounded aggregates (`extra="forbid"`, so frames/landmarks are rejected with 422) and is owner-only.
* Metrics (rules in `observation_service.py` and shown in the report): face visible %, facing camera %, posture stability,
  movement level, tracking quality, observation coverage, and speaking pace (dictated answers only). A metric is shown only when
  ≥ 20 s / 30 samples were analysed, coverage ≥ 60 % and tracking quality ≥ 50 %; otherwise **"Not enough data"**.
* There is **no** emotion, confidence, honesty or personality inference and **no combined non-verbal score**. The report lists the
  limitations and the rules, and keeps the verbal score and the non-verbal section separate.

## Data model (migration 0004)

`interviews`: `intro_required`, `introduction`, `observations (JSON aggregates)`. `follow_ups`: `overall`, `evaluation (JSON)`,
`source`, `is_ai_generated`, `model`. Additive and nullable/defaulted, so existing databases upgrade without data loss.

## Known limitations

* Real Gemini calls currently fail with the free-tier daily quota (429) on the development key, so AI paths are verified with fake
  providers; the live behaviour is the labelled fallback.
* Pose tracking quality depends on lighting, distance and camera angle; head direction is a coarse nose-vs-ears estimate.
* Speech recognition/synthesis depend on the browser (best in Chrome/Edge).
* The 3D avatar chunk (~0.9 MB, loaded only on the interview page) is large for a low-spec laptop; the flat fallback is used when
  WebGL is missing.
