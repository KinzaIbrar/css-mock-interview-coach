# Task 14 — Failure Analysis: Regressions and Non-Improvements

Per this task's explicit instruction ("report both improvements and regressions"; "do not use keyword
shortcuts... do not alter queries selectively to make the experimental corpus appear better"), this file
documents every case where the experimental candidate did **not** help, or made things worse — found by
actually reading the retrieved text for every scenario whose top-5 composition changed (16 of 32), not
by trusting the raw similarity-score deltas alone (several of which increased even in the regression
cases, because a *new, higher-scoring but irrelevant* chunk entered, not because anything got better).

## Regression 1: `t12-pa-002` (Objectives Resolution of 1949) — lost its one relevant hit

**Baseline:** partial / partial / **relevant** (the real Article 2A / Objectives Resolution text, at
rank 3, score 0.659).
**Candidate:** irrelevant / irrelevant / partial. The real Article 2A chunk was pushed to rank 4+ by two
`Paigham-e-Pakistan` chunks (ranks 1-2, scores 0.780/0.694) discussing Pakistan's post-independence
prosperity narrative and the document's own Unanimous Fatwa text — topically adjacent (shared
vocabulary: "Pakistan," "Islam," "constitution") but not actually about the 1949 Objectives Resolution.

**Root cause:** `Paigham-e-Pakistan` is a 121-page document covering national-identity and religious-
authority narrative broadly, not narrowly scoped to the jihad/terrorism topic it was added for. Its
167 chunks carry enough general "Pakistan + Islam + constitutional legitimacy" vocabulary to outscore a
precisely-matching but narrower chunk on an unrelated constitutional-history question.

## Regression 2: `t12-ps-custom-001` (Montesquieu / separation of powers) — lost its one relevant hit

**Baseline:** irrelevant / **relevant** (rank 2, the actual Montesquieu-naming chunk, score 0.371) /
irrelevant.
**Candidate:** irrelevant / irrelevant / irrelevant. The Montesquieu chunk's own score is **unchanged**
(0.371 — adding vectors to a FAISS `IndexFlatIP` never changes an existing vector's similarity score) but
it is now outranked by **five** `Sovereignty` (Stanford Encyclopedia) chunks (scores 0.425–0.490) about
Kantorowicz, Pogge, and cosmopolitanism — real political-theory content, but about sovereignty, not
separation of powers. Verified directly: a full-corpus search (not just top-5) confirms the Montesquieu
chunk is now ranked **#16 of 1187**, buried by the new source's own content, which the new source was not
even targeting this specific question.

**Root cause:** the `Sovereignty` encyclopedia entry is long (26 chunks) and covers general
political-theory vocabulary broadly enough to crowd out an unrelated-but-adjacent political-theory
question it wasn't meant to answer.

## New misleading-evidence risk: `t12-pa-001` (Lahore Resolution of 1940)

**Baseline:** irrelevant / irrelevant / irrelevant (no relevant content, but nothing actively misleading
either).
**Candidate:** rank 1 is now **"The Lahore Declaration (1999)"** — a real, genuinely different 1999
India-Pakistan bilateral document that the embedding model matched almost entirely on the shared place
name "Lahore." This is a textbook example of the "potentially misleading evidence" category this task
explicitly asked to measure: a confident-looking, topically-named hit that a careless reader could
mistake for relevant, which is actually about an unrelated event 59 years later. Pre-existing baseline
risk count for this failure mode was 1/32 (`t12-gk-013`); the candidate's count is 2/32.

## Sources added but never surfacing: `t12-gk-003` and `t12-is-008`

Two of the seven new sources were verified as real and genuinely on-topic, but **never entered the
top-5 for their own target question**:
- **IRSA detail page** (added for `gk-003`, water scarcity/dams): ranked **#99 of 1187** for its own
  target query (score 0.344). Root cause: it is a single 833-character chunk — too short and too
  narrowly about the 1991 Water Apportionment Accord/IRSA's founding mandate to compete with the
  Economic Survey's much larger (hundreds of chunks), broader climate/economy content on the same
  general theme.
- **Sahih Muslim 1218** (added for `is-008`, Farewell Sermon): ranked **#117 of 1187** for its own
  target query (score 0.294), despite being a real, substantial (13-chunk, ~22,000-character) primary
  hadith narration of the actual Farewell Hajj. The candidate's new rank-1 hit for this question came
  from `Paigham-e-Pakistan` instead, and it is only generically Islam-adjacent, not substantively about
  the Farewell Sermon itself — a lateral move, not a real fix (see `baseline_vs_candidate.csv`,
  `t12-is-008`).

This is a genuine, useful negative finding: **verifying a source is real and on-topic does not guarantee
it will be retrieved for the exact question it was added to answer.** Chunk length, phrasing overlap
with the specific query, and competition from other (even unrelated) content in the same index all
matter, and none of that can be known without actually running the retrieval and checking, which is
exactly what this phase did.

## Benign noise (no material change either way)

Six scenarios (`t12-pa-010`, `t12-gc-001`, `t12-gc-004`, `t12-ir-002`, `t12-ir-005`, `t12-en-002`,
`t12-en-014`) had a new chunk (usually from `Paigham-e-Pakistan` or `Sovereignty`) enter their top-5, but
it did not displace anything that was previously relevant, nor did it become genuinely relevant itself —
it just occupied a slot that was already unhelpful. These are flagged here for completeness but are not
treated as regressions, since the human-judged top-3 relevance verdict for each is unchanged.

## What this means for the candidate as a whole

Net effect across all 32 scenarios (see `baseline_vs_candidate.csv` for every row, `FINAL_REPORT.md` for
the aggregate numbers): **5 genuine improvements, 2 genuine regressions, 1 new misleading-evidence risk,
2 added-but-ineffective sources, 6 benign no-ops, 16 untouched.** This is not a uniform win. The specific,
identifiable cause of both regressions and the new misleading hit is **the same two broad, large, or
coincidentally-named sources** (`Paigham-e-Pakistan`'s broad national/religious vocabulary and the
`Lahore Declaration`'s name collision with the unrelated Lahore Resolution) — not a general property of
adding more sources. A narrower excerpt of `Paigham-e-Pakistan` (e.g. only its fatwa/jihad sections,
chunks it was actually added for) would likely have preserved its two genuine wins (`is-016`, `is-003`)
without causing the `pa-002` regression — this is flagged as a concrete, specific recommendation for a
follow-up refinement, not attempted in this task (re-chunking an already-added source mid-task would
blur the clean baseline-vs-candidate comparison this phase was designed to produce).
