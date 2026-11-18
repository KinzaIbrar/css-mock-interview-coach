# Task 15 — Phase 4: The Five Structural Chunking/Retrieval Failures, Investigated Separately

Per your selection, this phase is **diagnosis and documentation only** — no experimental re-chunked
index was built, and the approved baseline was not touched. These 5 scenarios (`gc-001`, `gc-004`,
`ir-002`, `ps-custom-001`'s *baseline-level* weakness, `is-003`'s phrasing-sensitivity) were identified
in Task 14's `coverage_gap_analysis.md` as not fixable by adding sources. This phase confirms each root
cause with direct evidence and proposes (but does not implement) a remediation design.

## Root cause 1 of 2: one shared, dense "Western Political Thought" syllabus chunk (3 scenarios)

**Rigorously confirmed, not inferred**: `gc-001`, `ir-002`, and `ps-custom-001` all retrieve the
**identical chunk_id** (`2a6579e7001c030a`, 201 words, from the FPSC syllabus's "PAPER: POLITICAL
SCIENCE (200 MARKS)... Western Political Thought" section) as their only politically-relevant
content — a single chunk that has to represent dozens of distinct theories and theorists (separation of
powers, realism, Montesquieu, sovereignty, and more) at once. Its real similarity score against each
query, verified directly against the approved baseline index:

| Scenario | Query topic | This chunk's rank | This chunk's score |
|---|---|---|---|
| `gc-001` | Separation of powers (Pakistan-specific) | #581 of 972 | 0.302 |
| `ir-002` | Realism (Morgenthau/Waltz) | #18 of 972 | 0.335 |
| `ps-custom-001` | Montesquieu by name | #2 of 972 | 0.371 |

The chunk does best when the query names a term likely to appear verbatim in its own dense list
(Montesquieu), and does poorly when the query needs Pakistan-specific or realism-specific elaboration
the chunk doesn't actually contain. **This is a chunk-granularity problem, not a missing-content
problem**: the underlying syllabus page almost certainly names Montesquieu, Morgenthau, Waltz and
others individually, but the fixed 350-word chunking swept them all into one chunk, diluting each
theory's own embedding signature.

**Proposed remediation (not implemented — requires re-chunking the approved 972-chunk baseline, out of
this task's bounds):** re-chunk the Political Science/International Relations syllabus pages at a finer
granularity — e.g. per-theory or per-sentence-group rather than a fixed 350-word window — so a query
naming Montesquieu specifically scores against a chunk that is *only* about Montesquieu, not a chunk
also containing Morgenthau, Waltz, Bodin, and a dozen others. This is the same remediation Task 14's own
`coverage_gap_analysis.md` already recommended; this phase adds the direct chunk_id-level confirmation.

## Root cause 2 of 2: Constitution PDF header-fragment chunking (`gc-004`)

**Confirmed**: the real Fundamental Rights text (Constitution Part II, Articles 8-28) genuinely exists
in the approved baseline (225-page PDF, 312 chunks) — but the query's top-3 baseline hits are bare
page-header fragments ("CONSTITUTION OF PAKISTAN 183 3. The Muslim Family Laws Ordinance, 1961...",
"CONSTITUTION OF PAKISTAN 180 2. The Land Reforms (Amendment) Act..."), which are footnote/cross-
reference lists that happen to embed with a similar generic "Constitution of Pakistan, legal provision"
signature, outranking the substantive article text itself for this particular phrasing.

**Proposed remediation (not implemented, same reason as above):** either a smaller chunk size for dense
legal-reference pages specifically, or stripping repeated structural boilerplate (the same kind of fix
already applied once to the FPSC syllabus document in Task 8, which measurably improved its retrieval
quality — see `research/colab/README.md`'s "Promoted from Task 8" note) applied here to the Constitution
PDF's own cross-reference/footnote pages.

## A different kind of limitation: phrasing-sensitivity (`is-003`)

Unlike the two root causes above, `is-003` (Ijtihad) is **not** a chunk-structure problem — the exact
same underlying content that scores well for a related scenario (`is-002`, "sources of Islamic law")
scores markedly worse for this related-but-differently-phrased question. This is a property of the
embedding model's sensitivity to phrasing, not a chunking defect, and re-chunking would not fix it.
**No remediation is proposed here** beyond what Task 15 already improved incidentally: the re-scoped
`Paigham-e-Pakistan` source now gives `is-003` a *second*, independent, genuinely relevant path to a
good answer (the Iqbal/"reconstruction of religious thought" chunk, verified in `regression_fixes.md`),
which is a real mitigation for this specific scenario even though it doesn't address the general
phrasing-sensitivity property.

## Summary: what Task 15 can and cannot do about these 5 scenarios

| Scenario | Root cause | Fixed by Task 15? |
|---|---|---|
| `gc-001` | Shared dense political-theory chunk | No — requires re-chunking the approved baseline (out of bounds) |
| `ir-002` | Same shared chunk | No — same reason |
| `ps-custom-001` (baseline-level) | Same shared chunk | No — same reason (the Task 14 *regression* on top of this was fixed; the underlying baseline-level weakness is untouched, exactly as it was before Task 14) |
| `gc-004` | Constitution PDF header-fragment chunking | No — requires re-chunking the approved baseline (out of bounds) |
| `is-003` | Phrasing sensitivity (not a chunk-structure issue) | Partially — gained a second genuine path via the Task 15 Paigham-e-Pakistan fix, but the underlying model limitation is unaddressed |

**Recommendation for a future task**: a dedicated re-chunking experiment (separate experimental index,
never touching the approved baseline) targeting specifically the Political-Science/IR-theory syllabus
pages and the Constitution's cross-reference-heavy pages, measured the same way Task 14/15 measured
everything else — real retrieval comparison, human-judged relevance, not score deltas alone.
