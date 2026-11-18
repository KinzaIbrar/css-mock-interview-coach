# Task 18 — Fine-Tuning Feasibility, Experiment Status, and Integration Recommendation

## Feasibility finding (verified via web search this session, not assumed)

This project's entire AI layer (`backend/app/agents/gemini_provider.py`) authenticates with
`genai.Client(api_key=settings.gemini_api_key)` — the plain **Gemini API** (AI Studio key-based access),
the same mode every `GEMINI_API_KEY`/`GEMINI_API_KEYS` entry uses (Task 17).

**The plain Gemini API currently does not support fine-tuning at all.** Google's own guidance (checked
this session) states that with the deprecation of Gemini 1.5 Flash-001 in May 2025, there is no model
currently available that supports fine-tuning through the Gemini API, with support planned to return in
the future but not yet available.

**Real Gemini fine-tuning exists only on Vertex AI** — a separate Google Cloud platform requiring a GCP
project with billing enabled, IAM/service-account auth (not a simple API key), and a different client
mode (`genai.Client(vertexai=True, project=..., location=...)`). None of this is configured in this
project, and setting it up means creating a billed cloud resource — explicitly out of bounds without
your authorization ("do not incur paid costs without authorization").

**This directly confirms the task's own warning**: a `GEMINI_API_KEY` does not provide fine-tuning
access. No real tuning job was attempted or could be attempted with the infrastructure available in this
session.

## What was and wasn't done, stated precisely

| Step | Status |
|---|---|
| Dataset quality audit | **Done** — real checks run, see `dataset_quality_report.md` |
| Fine-tuning-ready dataset prepared | **Done** — `train.jsonl`/`val.jsonl`/`test.jsonl`, matching the real production prompt contract |
| Training configuration designed | **Done** — `training_config.json`, grounded in verified current Vertex AI docs |
| An actual tuning job created/run | **Not done** — requires Vertex AI + billing, not available/authorized this session |
| Validation performance measured | **Not done** — no tuned model exists to measure |
| Comparison against baseline | **Not done** (no tuned model to compare) — see "Baseline" below for what IS known |
| New paid cost incurred | **None** |

This is stated explicitly so no step above is mistaken for complete when it isn't, per the task's own
instruction not to claim fine-tuning is complete merely because a dataset or configuration exists.

## Baseline (the only real comparison point available right now)

The current production approach for question generation is **zero/few-shot prompting** via
`generate_questions.py`'s `SYSTEM_PROMPT` + `build_prompt()`, drafting one subject/topic/difficulty at a
time, always reviewed by a human before publishing (`data/questions/_drafts/`, never auto-published).
There is no existing quantitative quality score for this baseline to compare a hypothetical tuned model
against (Gemini has been largely unavailable throughout this project's history per `PROJECT_STATUS.md`,
so even the baseline's own real-model output has limited verified history). If a real tuning job is run
in the future, `training_config.json`'s `evaluation_plan_if_run` is the concrete methodology to produce
that comparison honestly (schema-validity rate + human review against the held-out `test.jsonl`).

## Integration recommendation (design only, nothing implemented)

If a real tuned model becomes available later (via your authorized Vertex AI setup), it integrates
**without breaking the Task 17 multi-provider system**, because every consumer only depends on the
`LLMProvider` protocol (`generate_json`, `.name`, `.model`):

1. A tuned model is just a different `model` identifier (e.g.
   `projects/<proj>/locations/<region>/tunedModels/<id>`) passed to a `GeminiProvider`-like wrapper.
2. The one real code change needed: `GeminiProvider._get_client()` would need an optional Vertex-AI
   client-construction branch (`vertexai=True, project=..., location=...`) alongside the existing
   AI-Studio `api_key=...` branch — a small, additive, well-contained change, not a rewrite, selected by
   a new config flag (e.g. `gemini_use_vertex: bool`) rather than altering existing behavior.
3. A tuned-model provider can then be **added as just another entry in `GeminiProviderPool`'s provider
   list** (Task 17) — e.g. tried first for question-generation-shaped prompts, falling back to the
   existing AI-Studio keys for everything else — or kept as a fully separate, opt-in path used only by
   `generate_questions.py`, never touching `evaluation_agent.py`/`feedback_agent.py`'s existing behavior.
4. **No RAG, FAISS baseline, question-bank, scoring logic, or frontend change is required** for this
   integration — confirmed by design, since the protocol boundary already isolates all of that.

This is a recommendation for a future, explicitly-authorized task — nothing above was implemented this
session.
