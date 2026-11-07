# Deployment guide (free tier)

Architecture: **Vercel** (static React/Vite frontend) → HTTPS → **Render** (FastAPI) → **Supabase** (PostgreSQL). Gemini is called only
from the backend. Camera/pose processing and the 3D avatar run in the visitor's browser. Nothing here has been deployed yet; follow
the steps below when you are ready.

> Note: the frontend is **TypeScript** (React 19 + Vite 8), not JavaScript. Nothing about deployment depends on that.

## Why not keep SQLite?
Render's free web service has an **ephemeral disk**: files (including `app.db`) are wiped on every deploy, restart and after it
sleeps. SQLite would silently lose all users and interviews. Use hosted PostgreSQL (Supabase free). The code supports both:
`DATABASE_URL=sqlite:///...` for local work, `postgresql://...` in production (the app rewrites it to the `psycopg` 3 driver).
Schema changes are Alembic migrations applied automatically at startup (they render valid PostgreSQL – checked offline; see "Not
verified" below).

## Accounts you need
1. GitHub (the repo must be pushed there – you do this; nothing was committed or pushed for you)
2. Supabase (free) – database
3. Render (free) – backend
4. Vercel Hobby (free) – frontend
5. Google AI Studio – your existing Gemini API key

## Step 1 – Supabase (database)
1. Create a project (choose a region near your Render region; set a strong database password and save it).
2. **Project → Connect → "Session pooler"** and copy the URI. Use the pooler, **not** the "Direct connection": the direct host is
   IPv6-only and Render's free tier cannot reach it. It looks like  
   `postgresql://postgres.<project-ref>:<PASSWORD>@aws-0-<region>.pooler.supabase.com:5432/postgres`
3. Keep it secret. This is your `DATABASE_URL`. (Special characters in the password must be URL-encoded.)
4. Tables are created by the backend on first start. Do not create them by hand.

### Optional: move your existing local data
Only if you want your current local users/interviews online. The source is only read; the copy refuses a non-empty target.
```
cd backend
.venv\Scripts\python -m scripts.copy_database --source sqlite:///./app.db --target "<your Supabase DATABASE_URL>"
```
(Run it before or after the first deploy, as long as the target has no users yet.) It migrates the target schema, copies
`questions` (with ids, because answers reference them), then users, interviews, answers, evaluations, follow-ups, feedback and
progress, and verifies the row counts. If the app already seeded the target's questions, they are kept when their ids match the
source. Passwords are copied as stored hashes and never printed. Make a backup first, e.g. with Python's `sqlite3` backup API
(`backend/backups/` is git-ignored).

## Step 2 – Render (backend)
Option A – Blueprint: Render dashboard → **New → Blueprint** → pick the repo → it reads `render.yaml`.  
Option B – manual: **New → Web Service** → pick the repo, then:

| Setting | Value |
|---|---|
| Root Directory | `backend` |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'` |
| Health Check Path | `/api/health` |
| Instance type | Free |

**Environment variables** (Render → Environment):

| Key | Value |
|---|---|
| `PYTHON_VERSION` | `3.11.9` |
| `APP_ENV` | `production` (the app refuses to start without a strong `JWT_SECRET`) |
| `DATABASE_URL` | the Supabase session-pooler URI from Step 1 |
| `JWT_SECRET` | a random string ≥ 32 chars, e.g. `python -c "import secrets;print(secrets.token_urlsafe(48))"` (Blueprint generates one) |
| `CORS_ORIGINS` | your Vercel URL, no trailing slash, e.g. `https://css-coach.vercel.app` (comma-separate several) |
| `GEMINI_API_KEY` | your key (backend only; never put it in Vercel) |
| `GEMINI_MODEL` | `gemini-3.8-flash` (unchanged default) |
| `CORS_ORIGIN_REGEX` | optional, for Vercel preview URLs, e.g. `https://css-coach-.*\.vercel\.app` |

Deploy, then open `https://<service>.onrender.com/api/health` – expect `{"status":"ok","environment":"production",...}`. The first
start applies the migrations and loads the 112-question dataset into Postgres. Keep **one** instance/worker (the Gemini cooldown
state is in process memory).

## Step 3 – Vercel (frontend)
1. **Add New → Project** → import the repo.
2. **Root Directory:** `frontend`. Framework preset: Vite (also set in `frontend/vercel.json`). Build: `npm run build`. Output: `dist`.
3. **Environment variable** (Production, and Preview if you use it):  
   `VITE_API_BASE_URL` = `https://<your-service>.onrender.com/api`
4. Deploy. The build downloads the MediaPipe WASM/model into `public/vision/` (`scripts/setup-vision-assets.mjs`); if that download
   fails the build still succeeds and the camera simply reports "Not enough data".
5. Copy the final Vercel URL into Render's `CORS_ORIGINS` (Step 2) and redeploy the backend. Order matters: until then the browser
   blocks API calls with a CORS error.

`frontend/vercel.json` provides the SPA fallback (deep links like `/interviews/3/results` work on refresh), sets
`Permissions-Policy: camera=(self), microphone=(self)` and caching for assets. Camera and microphone need HTTPS, which Vercel provides.

## Step 4 – Test the deployed app
1. `https://<render>/api/health` → `ok`. `https://<render>/docs` loads.
2. Open the Vercel URL → register → log in → refresh the page (still signed in, deep links work).
3. Start an interview (introduction on). Answer the introduction, then Q1. Confirm the four agents' statuses change while you submit.
4. With a working Gemini key you should see the evaluation labelled as AI; if the quota is used up you will see the labelled
   `dev_heuristic` fallback instead (never silently fake).
5. Answer until a follow-up appears, reply, finish, and open the report: coaching plan, follow-up score, history and dashboard.
6. Camera: press "Turn on camera", allow it, confirm the preview and "Camera on" indicator, turn it off (the browser camera light
   goes off). Microphone: use "Dictate answer" (Chrome/Edge; the browser sends audio to its own speech service).
7. Restart/redeploy the Render service and log in again – your data is still there (Supabase). Check Supabase → Table editor.
8. Browser devtools → Network: all calls go to your Render URL over HTTPS, and no response contains your Gemini key.

## Free-tier limitations
* **Render free sleeps after ~15 min idle**; the first request afterwards takes ~30–60 s (cold start + migrations check). Open the
  site/`/api/health` before a demo. The app's 120 s AI timeout covers a cold start during an answer submission.
* Render free has limited monthly instance hours and 512 MB RAM (the app fits; the LangGraph/Gemini imports are the biggest part).
* **Supabase free pauses projects after ~1 week of inactivity** (restore from the dashboard; data is kept) and has a 500 MB limit.
* **Gemini free tier**: the development key hit the 20 requests/day limit for `gemini-3.8-flash` – roughly 3 interviews/day. When
  exhausted the app labels results as development heuristics. A billed key or another model avoids this.
* Vercel Hobby is for non-commercial use; fine for a portfolio/practice project.
* The 3D avatar chunk (~0.9 MB gzip 240 KB) loads only on the interview page.

## Low-memory note (local)
On a machine with little free RAM, Vitest workers can run out of memory and report fewer passing tests. Use
`npx vitest run --maxWorkers=1 --no-file-parallelism`.

## Local development is unchanged
`backend\.env` keeps `DATABASE_URL=sqlite:///./app.db`; `npm run dev` still proxies `/api` to `localhost:8000`.

## Verification status (be honest)
Verified here: backend test suite, frontend tests/type-check/production build, a production-mode server start (temp SQLite) with
`APP_ENV=production`, health check, CORS preflight from an allowed origin, rejection of other origins, and the migrations rendered as
PostgreSQL SQL offline.  
**Not verified (needs your accounts):** a live Supabase connection and the migrations/`copy_database` run against a real PostgreSQL;
the Render and Vercel builds; a successful live Gemini call (quota); camera/microphone on a real device over HTTPS. Do the checklist
above after deploying and tell me what fails.
