# Task 15 — Phase 3: Lahore Declaration 1999 vs. Lahore Resolution 1940 False-Match Investigation

**Scope decision (per your selection):** retrieval-side mitigation only, no new source research (a
Lahore-Resolution-1940 source was already searched for and not found in Task 14).

## Diagnosis

The candidate's rank-1 hit for `t12-pa-001` ("What was the Lahore Resolution of 1940 and why is it
significant?") is "The Lahore Declaration (1999)" at similarity 0.591 — a real, entirely unrelated
1999 India-Pakistan bilateral document.

A direct test isolates the cause precisely: embedding the real query against (a) the actual Lahore
Declaration chunk in the corpus, and (b) a synthetic, correctly-on-topic passage about the real 1940
resolution (not in the corpus, used only for this diagnostic):

| Comparison | Cosine similarity |
|---|---|
| Query vs. the real Lahore Declaration 1999 chunk (the false match) | 0.602 |
| Query vs. a genuinely correct 1940 Lahore Resolution passage (hypothetical) | 0.791 |
| Lahore Declaration 1999 chunk vs. the correct 1940 passage (should be dissimilar) | 0.558 |

**This is not an embedding-model defect — it is what the model does when the right content doesn't
exist.** A genuinely correct passage would score markedly higher (0.79) than the false match (0.60),
confirming the model *can* tell the two events apart when both are available to compare against. The
problem is structural: there is no 1940-specific content anywhere in the corpus (confirmed, Task 14), so
the model's best available candidate is the next-closest thing it has — a document sharing the place
name "Lahore" and the general genre (a signed Pakistan-India diplomatic text).

## Why no clean retrieval-side mitigation exists

The obvious fix to consider is a minimum-similarity floor (don't show evidence below some score).
Tested against the real score distribution across every scenario measured in Task 14/15:

| Scenario | Score | Genuine or false? |
|---|---|---|
| `pa-001` (false match) | 0.591 | **False** |
| `ps-custom-002` rank-1 (Sovereignty, Task 15 re-scoped) | 0.596 | Genuine |
| `ir-016` rank-1 (Tashkent Declaration) | 0.609 | Genuine |
| `ca-004` rank-1 (Understanding the WTO) | 0.648 | Genuine |

The false match's score (0.591) sits *below* three genuine, verified wins, with no gap wide enough to
place a universal floor between them without also discarding genuine evidence. Any threshold strict
enough to exclude 0.591 would also exclude the `ps-custom-002` win at 0.596 — trading one disclosed risk
for the loss of a verified improvement. **No clean, universally-safe similarity threshold exists** for
this corpus and query set.

A more targeted mitigation (e.g. appending explicit year/date tokens to the query, or a
named-entity/date-aware re-ranking step) was considered but would mean changing retrieval query
construction or adding a new ranking stage beyond simple top-k cosine search — both are changes to "the
existing retrieval algorithm," which is out of this task's bounds (and every prior RAG task's bounds).

## Conclusion and recommendation

**No fix applied — documented as a disclosed, inherent limitation**, not a regression introduced by this
task (it was already present and disclosed in Task 14). Practical mitigations that stay within bounds:
1. The production evaluation prompt's existing SYSTEM instruction already frames all
   `<retrieved_background>` content as unverified and never authoritative (Task 11/13) — this is the
   real, already-existing safety net for exactly this kind of false match, independent of whether the
   candidate corpus is ever activated.
2. If a future task resumes source research, a genuine Pakistan-Movement/Lahore-Resolution-1940 primary
   source (not found in Task 14's search) would directly out-rank this false match the same way the
   Tashkent Declaration fixed `ir-016` — this remains the only complete fix, and is explicitly deferred,
   not attempted here.
