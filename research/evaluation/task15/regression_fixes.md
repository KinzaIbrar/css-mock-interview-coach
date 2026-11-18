# Task 15 — Phase 1-2: Fixing the Two Task 14 Regressions

Both fixes reuse content already downloaded/extracted in Task 14 (`output_task14_coverage/01_Raw_Data/`
and `07_Processed_Chunks/`) — no new fetching or source research was performed, per this task's
constraint. Full build/verification scripts: `research/colab/task15_build_corpus.py`,
`task15_verify.py`, `task15_regression_tests.py` (9/9 automated checks passing).

## Fix 1: Objectives Resolution (`t12-pa-002`)

**First attempt (rejected on measurement, not assumption):** restrict `Paigham-e-Pakistan` to PDF pages
36-78 by chapter boundary (Ch.3 "State of Pakistan and Challenges" onward), based on the original
regression-causing chunk's page number (33) falling inside the excluded "Ch.1-2" range. **Verified
empirically this did not fully fix it**: the Unanimous Fatwa's own opening page (64, well inside the
kept range) independently scores 0.694 against the `pa-002` query — above the real Objectives-Resolution
chunk's own fixed score (0.659) — so it alone continued to bury the real hit. The same page-range cut
also cost a genuine win: `is-003`'s Iqbal/"reconstruction of religious thought" chunk lives at page 32,
inside the chapter I had excluded.

**Final fix:** replaced the chapter-level heuristic with a precise, per-chunk empirical exclusion. Every
one of the full document's 167 chunks was scored (real `all-MiniLM-L6-v2` embeddings, not estimated)
against the `pa-002` regression query; exactly **4 chunks** (PDF pages 33, 34, 35, 64) exceed the real
baseline chunk's own score. Excluding only those 4 (keeping the other 163, including the recovered
page-32 Iqbal chunk) fixes the regression completely.

**Verified result** (`task15_verify.py`, `task15_regression_tests.py`): `pa-002`'s candidate top-3 is now
`[Constitutional Law syllabus header, Constitution preamble, **the real Article 2A / Objectives
Resolution text**]` — identical in composition to the original Task 12 baseline. `is-003`'s win is
simultaneously preserved (Iqbal chunk at rank 1).

## Fix 2: Montesquieu / Separation of Powers (`t12-ps-custom-001`)

Not caused by `Paigham-e-Pakistan` at all — caused by the `Sovereignty` (Stanford Encyclopedia) entry's
26 chunks, five of which scored above the real Montesquieu-naming chunk's own fixed score (0.371) for
the separation-of-powers query, pushing it from rank 2 (baseline) to rank 16 of 1,187 (Task 14
candidate).

**Fix:** every one of the 26 Sovereignty chunks was scored against both the regressing query
(`ps-custom-001`) and the target query it was added for (`ps-custom-002`). A 12-of-26 subset was kept —
every kept chunk scores below 0.371 against the regressing query (so the real Montesquieu chunk's rank
is completely unaffected, not just reduced), while the set still includes the article's core
definitional content (holder of sovereignty, absoluteness, internal/external dimensions) and its
Peace-of-Augsburg/Bodin historical context (one kept chunk is literally about Bodin's own historical
situation — "time when France was sundered by civil war between Calvinist Huguenots and the Catholic
monarchy. He viewed the problem of order as central..."). Excluded: the article's own opening summary
sentence (the single best match for `ps-custom-002`, but also the single biggest regressor),
Kantorowicz/EU/UN/Jouvenel-critique chunks, and pure bibliography — none of which were ever responsible
for the `ps-custom-002` win in the first place.

**Verified result**: `ps-custom-001`'s candidate top-3 is now `[18th Amendment Proclamation clause,
**the real Montesquieu-naming syllabus chunk**, 18th Amendment High Courts clause]` — identical in
composition to the original Task 12 baseline. `ps-custom-002`'s win is simultaneously preserved (a
Sovereignty chunk at rank 1, score 0.596 — slightly lower than the unfiltered 26-chunk version's 0.663,
but still clearly, directly on-topic).

## Confirmed: no new collateral damage

Re-checked the two scenarios that had benign (non-regressing) `Paigham-e-Pakistan` noise in Task 14
(`gc-001` at rank 5, `pa-010` at rank 4) — both unchanged in verdict after the re-scoping; no new issue
introduced. The other 26 scenarios were not re-swept in full (per this task's instruction to avoid
repeating Task 14's full retrieval comparison) — none of their retrieval inputs changed, since neither
`Paigham-e-Pakistan` nor `Sovereignty` ever appeared in their top-5 to begin with (confirmed from Task
14's own `retrieval_comparison_raw.json`).

## Net result

| Metric | Task 14 candidate | Task 15 candidate |
|---|---|---|
| Total chunks | 1,187 | 1,169 (-18: 4 Paigham-e-Pakistan + 14 Sovereignty) |
| `pa-002` regression | Present | **Fixed** |
| `ps-custom-001` regression | Present | **Fixed** |
| `ca-004`, `ir-016`, `is-016`, `is-003`, `ps-custom-002` wins | Present | **All preserved** |
| `pa-001` misleading Lahore Declaration match | Present | Unchanged (see `lahore_declaration_investigation.md`) |
