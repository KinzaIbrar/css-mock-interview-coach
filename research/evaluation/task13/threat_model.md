# Task 13 — Threat Model: Evaluation-Prompt Trust Boundaries

## Actors

| Actor | Trust level | Controls |
|---|---|---|
| The system (our code) | Trusted | SYSTEM prompt text, prompt structure/ordering, delimiter tag names, which text goes where |
| The candidate | **Untrusted** | `answer_text`, `introduction`, follow-up question-reply text (the follow-up *question* text is actually system-authored, but is sanitized anyway as defense in depth) |
| The RAG corpus (curated CSS knowledge-base PDFs/text, ingested offline) | **Untrusted content, trusted provenance** | The excerpt *text* of each chunk is arbitrary document content we did not author and cannot fully vet; the chunk's *metadata* (chunk_id, source_title, page_number, subject/topic) is trusted, because it is assigned by our own ingestion pipeline and FAISS record, never derived from the excerpt text itself |
| Gemini (the LLM) | Not trusted to resist instructions found in DATA, so DATA must never look like an instruction or a system-authored delimiter | Receives the final assembled prompt; has no way to tell candidate-authored text from system-authored text except the delimiter tags and the SYSTEM prompt's explicit framing |

## The boundary that failed (Task 12 → Task 13)

The prompt distinguishes trusted system content from untrusted content **only by which XML-like tag
name wraps it** (`<candidate_answer>`, `<candidate_introduction>`, `<candidate_follow_up_answer>`,
`<retrieved_background>`) plus a SYSTEM-prompt instruction that content inside those tags is DATA, never
instructions. That boundary is enforced by `sanitize_user_text`, which must guarantee that **no
candidate-controlled string can ever contain a literal occurrence of any of those tag names**. Before
this task, the function's regex covered `candidate_*`, `system`, and `instructions?` — but not
`retrieved_background`. A candidate could therefore place a literal `<retrieved_background>...
</retrieved_background>` sequence inside their own answer, and it would reach Gemini unescaped, nested
inside `<candidate_answer>`.

## Why this matters even though no instruction-override was demonstrated (Task 12)

The SYSTEM prompt already tells the model that `<retrieved_background>` content is DATA, never an
instruction, and never more authoritative than the model's own judgement — so this was not a direct path
to an arbitrary score override (unlike an unescaped `<candidate_answer>` tag would be, which previously
*was* defended). The real risk is narrower but still real: a candidate could cause what *looks
structurally* like a second, candidate-controlled "retrieved evidence" section to appear in the prompt —
a **fake-authority / social-engineering risk**, not a command-injection one. It also mattered
independently of whether `RAG_EVIDENCE_ENABLED` was even on, since the SYSTEM prompt's framing of
`<retrieved_background>` applies to the tag text itself, regardless of whether the evidence layer
actually ran.

## Assets to protect

1. **Scoring integrity** — the four evaluation dimensions and the candidate's score must be derived only
   from the model's genuine judgement of the real answer against the real reference material, never from
   a structural trick in the candidate's text.
2. **Evidence authenticity** — any text that appears inside a real `<retrieved_background>` block must
   have actually come from the vector retriever; a candidate must never be able to fabricate, extend, or
   prematurely close that block.
3. **Citation/provenance integrity** — `EvidenceItem`/`EvaluationOutcome.citations` fields (chunk_id,
   source_title, source_url, page_number) must only ever be populated from real FAISS retriever records,
   never influenced by, or derived from, candidate-supplied text, and must never leak into any API
   response or the database.
4. **Fallback transparency** — the dev-heuristic fallback (used whenever Gemini is unconfigured/failing)
   must stay entirely separate from the evidence layer and never be mistaken for an AI-backed result.

## Mitigation strategy chosen

Rather than enumerate every possible obfuscation of `retrieved_background` by name (a losing,
open-ended battle — the task itself warns "do not assume simple string replacement is sufficient"), the
fix in `sanitize_user_text` (`backend/app/prompts/common.py`) now:

1. Normalizes Unicode (NFKC) and a curated set of angle-bracket look-alikes to plain ASCII `<`/`>` first,
   so fullwidth, CJK, and angle-quote confusables cannot bypass the subsequent checks.
2. Strips any text matching one of our known tag names (now including `retrieved_background`, with
   tolerant internal whitespace/separator matching), replacing it with a readable `"[tag removed]"`
   marker — this keeps the existing, already-tested behavior for the previously-known attack shapes.
3. **Escapes every remaining literal `<` and `>` character** to `&lt;`/`&gt;`. This final pass is the
   actual security guarantee: it closes the *entire* vulnerability class — any tag name, known or not,
   nested, repeated, or malformed — not just the specific names enumerated in step 2. No literal `<` or
   `>` character can survive this function under any input.

This mirrors, and generalizes, the precedent already set for retrieved-corpus text in
`evidence.py`'s `_sanitize_excerpt` (which calls this same function), so both untrusted-content paths now
share one, uniformly stronger boundary.

## What this does *not* attempt to fix, and why

- It does not stop a sufficiently capable LLM from being *persuaded* by well-written prose inside
  `<candidate_answer>` that argues for a higher score — that is a model-judgement question, addressed by
  the SYSTEM prompt's explicit scoring rubric and the instruction never to reward unsupported claims, not
  by string sanitization. No sanitizer can make a model immune to argument; it can only prevent the
  candidate from *structurally impersonating* system-authored content.
- It does not add a cryptographic nonce or random per-request boundary token. Universal angle-bracket
  escaping already makes it impossible for untrusted text to construct *any* live tag, which is a
  sufficient and simpler guarantee for this threat; a nonce-based redesign would be a bigger structural
  change than this hardening task calls for.
- It was not tested against a live Gemini call (the external outage documented in Task 12 may still be in
  effect, and this task's fix is a prompt-construction/string-sanitization concern, verifiable without a
  live model). What was verified is that the *final prompt string* sent to the provider never contains a
  live, candidate-controlled delimiter — not how a real model would react to prose-level persuasion.
