# Task 14 — Phase 2: Coverage Gap Diagnosis

**Method.** Every row below is built from the *real, human-judged* retrieval results already produced in
Task 12 (`research/evaluation/task12/retrieval_relevance.csv`, 96 judgments across the 32 scenarios'
top-3 FAISS hits against the approved 972-chunk baseline), cross-referenced with `sources.json`'s actual
source inventory and each scenario's reference answer/evaluation criteria. This is **not** the
dataset's own `expected_rag_relevance` field (which is a prediction recorded before retrieval was run) —
several of those predictions turned out wrong in either direction (e.g. `gc-013` was predicted
"tangential" but actually scored 2 relevant + 1 partial hit; `pa-002` behaved as predicted). Using the
real judgments, not the predictions, is the whole point of this diagnosis.

## Coverage matrix

| Subject | Scenario | Real top-3 judgment | Root-cause category | Explanation |
|---|---|---|---|---|
| Pakistan Affairs | pa-001 (Lahore Resolution 1940) | irrelevant / irrelevant / irrelevant | **Genuinely missing** | No Pakistan-Movement/freedom-movement narrative source exists at all; only brief syllabus headings. |
| Pakistan Affairs | pa-002 (Objectives Resolution 1949) | partial / partial / **relevant** | Good coverage | Constitution PDF's own preamble + Article 2A text is a direct hit. |
| Pakistan Affairs | pa-003 (1971 separation) | irrelevant / irrelevant / irrelevant | **Genuinely missing** | No 1971/Bangladesh-war source in the corpus. |
| Pakistan Affairs | pa-010 (doctrine of necessity / case law) | irrelevant / irrelevant / irrelevant | **Genuinely missing** | No case-law content (Dosso, Asma Jilani, etc.) anywhere in the corpus. |
| Current Affairs | ca-002 (IMF) | irrelevant / irrelevant / partial | **Too broad for specificity** | Economic Survey exists but has no IMF-programme-specific passage; generic/off-topic chunks outrank it. |
| Current Affairs | ca-013 (Paris Agreement / climate justice) | partial / irrelevant / irrelevant | **Too broad for specificity** | Economic Survey's Climate chapter covers Pakistan's adaptation policy, not the Paris Agreement/COP/climate-justice framing itself. |
| Current Affairs | ca-009 (circular debt) | partial / irrelevant / partial | **Too broad for specificity** | Economic Survey touches the energy sector generally; "circular debt" as a specific mechanism isn't covered. |
| Current Affairs | ca-004 (WTO) | irrelevant / partial / irrelevant | **Genuinely missing** | No WTO institutional source; `sources.json` already notes the WTO Pakistan page was rejected (tables/links only, no prose). |
| Governance & Constitutional Studies | gc-001 (separation of powers) | partial / partial / irrelevant | **Retrieval/chunk-structure failure** | The only chunk naming Montesquieu/separation-of-powers theory is buried in a dense, undifferentiated Political-Science-syllabus list chunk (confirmed in Tasks 8-10: ranks #310-515). Content exists, ranking doesn't surface it. |
| Governance & Constitutional Studies | gc-002 (18th Amendment) | **relevant / relevant** / partial | Good coverage | PIPS 18th-Amendment document is a strong direct hit. |
| Governance & Constitutional Studies | gc-004 (Fundamental Rights) | irrelevant / irrelevant / irrelevant | **Retrieval/chunk-structure failure** | The real Constitution Part II (Articles 8-28) text is in the corpus (225-page PDF, 312 chunks), but bare page-header fragments outrank it for this phrasing — a chunking-granularity problem, not a missing-source problem. |
| Governance & Constitutional Studies | gc-013 (Accountability: NAB/Auditor-General/Ombudsman) | **relevant / relevant** / partial | Good coverage (better than predicted) | The Governance & Public Policies syllabus section and the Constitution's own Auditor-General article both hit directly. |
| International Relations | ir-001 (UN Security Council) | **relevant / relevant / relevant** | Excellent coverage | UN Charter full text (33 chunks) is a perfect direct hit every time this has been tested. |
| International Relations | ir-002 (Realism / IR theory) | partial / irrelevant / irrelevant | **Retrieval/chunk-structure failure** | Same root cause as gc-001 and ps-custom-001: one dense IR/Political-Science-theory list chunk, specific theories (Morgenthau, Waltz) not surfaced. |
| International Relations | ir-016 (Kashmir dispute) | irrelevant / partial / irrelevant | **Genuinely missing** | No Simla Agreement / Tashkent Declaration / Lahore Declaration text anywhere in the corpus. |
| International Relations | ir-005 (sources of international law) | **relevant** / partial / irrelevant | Good coverage | International Law syllabus section opens with exactly this topic — direct hit. |
| English | en-002 (precis qualities) | irrelevant / relevant / irrelevant | Thin coverage | English (Precis & Composition) syllabus section names the topic but doesn't elaborate the actual qualities. |
| English | en-012 (denotation/connotation) | irrelevant / irrelevant / irrelevant | **Genuinely missing (structural)** | No English-language-skills/rhetoric instructional content exists anywhere — the whole corpus is exam-administration/legal/policy text, not a writing-pedagogy source. |
| English | en-008 (paragraph elements) | irrelevant / irrelevant / irrelevant | **Genuinely missing (structural)** | Same structural gap as en-012. |
| English | en-014 (ethos/pathos/logos) | partial / irrelevant / irrelevant | **Genuinely missing (structural)** | Same structural gap; nearest hit is a loosely-adjacent Philosophy syllabus heading. |
| General Knowledge | gk-006 (UN and its organs) | partial / **relevant / relevant** | Excellent coverage | UN Charter + dedicated "UN Structure" page both hit directly. |
| General Knowledge | gk-013 (2008 financial crisis) | **misleading** / irrelevant / irrelevant | **Genuinely missing + misleading-evidence risk** | No 2008-crisis content exists; the top hit's "Global Economic Review" heading superficially resembles it but is about FY2025-26. |
| General Knowledge | gk-003 (water scarcity / dams) | partial / partial / irrelevant | **Genuinely missing** | No dedicated water-resources/dam-policy source (Tarbela, Mangla, Diamer-Bhasha, Kalabagh, Indus Waters Treaty). |
| General Knowledge | gk-010 (IMF vs World Bank) | partial / **relevant** / irrelevant | Good coverage | Economic Survey names a real current IMF facility (EFF/RSF) — a genuine, if narrow, direct hit. |
| Islamic Studies | is-002 (sources of Islamic law) | partial / partial / **relevant** | Good coverage | Muslim Law & Jurisprudence syllabus chunk explicitly lists Quran/Sunnah/Ijma/Qiyas/Ijtihad. |
| Islamic Studies | is-003 (Ijtihad) | partial / partial / irrelevant | **Retrieval phrasing-sensitivity** | Same underlying content as is-002 scores markedly worse for this related phrasing — a genuine embedding-ranking limitation, not a missing-content one. |
| Islamic Studies | is-008 (Farewell Sermon / Seerah) | irrelevant / irrelevant / partial | **Genuinely missing** | No Seerah/Hadith-literature content beyond a bare syllabus heading. |
| Islamic Studies | is-016 (jihad vs. terrorism) | partial / partial / partial | **Genuinely missing** | Only generic Islamic-Studies reading-list content; no source substantively addresses the jihad/terrorism distinction. The reference answer itself names a real, findable primary document (Paigham-e-Pakistan, 2018) that isn't in the corpus. |
| Political Science | ps-custom-001 (Montesquieu / separation of powers) | irrelevant / **relevant** / irrelevant | **Retrieval/chunk-structure failure** | The Montesquieu-naming chunk is retrieved (rank 2) but weakly scored (0.371) — same dense-list-chunk root cause as gc-001/ir-002. All three questions are traceable to the *same* underlying chunk. |
| Political Science | ps-custom-002 (sovereignty theory) | irrelevant / irrelevant / partial | **Genuinely missing** | No Bodin/Hobbes/Austin/pluralist sovereignty-theory content. |
| General Science and Ability | gsa-custom-001 (solar system) | **relevant** / irrelevant / partial | Good coverage (surprising) | The General Science & Ability syllabus chunk explicitly names "Solar System, Sun, Earth, Astronomical System of Units." |
| General Science and Ability | gsa-custom-002 (greenhouse effect mechanism) | partial / partial / partial | **Too broad for specificity (cross-subject)** | The Economic Survey's Climate Change chapter covers impacts well but not the basic greenhouse-effect science mechanism — the best-available evidence carries a different subject label than the question's own subject. |

## Root-cause summary across all 32 scenarios

| Root-cause category | Count | Fixable by adding sources? |
|---|---|---|
| Good/excellent coverage already | 9 (pa-002, gc-002, gc-013, ir-001, ir-005, gk-006, gk-010, is-002, gsa-custom-001) | N/A |
| Genuinely missing content | 13 (pa-001, pa-003, pa-010, ca-004, ir-016, en-012, en-008, en-014, gk-013, gk-003, is-008, is-016, ps-custom-002) | **Yes** — this is where Phase 3's new sources target |
| Too broad / wrong specificity (content exists adjacently) | 5 (ca-002, ca-013, ca-009, en-002, gsa-custom-002) | **Partially** — a more specific/narrower source could help, but the existing broad source isn't *wrong*, just insufficiently granular |
| Retrieval/chunk-structure failure (content exists, ranking fails) | 5 (gc-001, gc-004, ir-002, is-003, ps-custom-001) | **No** — adding more sources cannot fix this; it is a chunking/embedding-granularity problem in the *existing* corpus |
| Misleading-evidence risk | 1 (gk-013, overlaps with "genuinely missing") | N/A — a risk-awareness finding, not a coverage gap |

## The most important finding: not all weak scenarios are a sourcing problem

**5 of the 32 scenarios (16%) are structurally unfixable by adding sources.** Three of them
(gc-001, ir-002, ps-custom-001) trace back to the *same* root chunk: a single dense,
undifferentiated Political-Science/IR-theory syllabus list chunk that mentions many theories and
theorists in one pass, so no individual theory (separation of powers, realism, Montesquieu) scores well
against a focused query even though the words are technically present somewhere in the chunk. `gc-004`
is a different mechanism (header-fragment chunks of the 225-page Constitution PDF outranking the real
substantive Fundamental Rights text), and `is-003` shows the same underlying content as a working
scenario (`is-002`) failing for a related-but-different phrasing — a genuine embedding-ranking
limitation.

**This means Task 14's source-addition strategy should explicitly target only the 13
genuinely-missing-content scenarios (and, secondarily, the 5 too-broad ones with narrower sources)** —
adding more sources for gc-001/gc-004/ir-002/is-003/ps-custom-001 would not move the needle, and doing
so anyway would misrepresent the actual fix needed. Per this task's own instruction ("if a proposed
improvement requires architectural changes, document it and request approval"): fixing the
retrieval/chunk-structure category would require either re-chunking the dense Political-Science/IR
syllabus pages at a finer (per-theory) granularity, or re-chunking the Constitution PDF with
header-stripping at a smaller chunk size — both are modifications to the **existing approved 972-chunk
baseline's chunking strategy**, explicitly out of bounds for this task ("do not modify the approved
972-chunk baseline"). This is flagged here as a real, separate, architectural follow-up recommendation
for a future task, not attempted in Task 14.

## Priority gaps selected for Phase 3 source research

In priority order, based on how many real scenarios each affects and how likely an authoritative source
is to exist:

1. Pakistan Affairs — Pakistan Movement / Lahore Resolution 1940 history (pa-001)
2. Pakistan Affairs — 1971 separation / Bangladesh war history (pa-003)
3. Pakistan Affairs — constitutional case law / doctrine of necessity (pa-010)
4. Current Affairs — WTO institutional facts (ca-004)
5. International Relations — Kashmir dispute bilateral documents (ir-016)
6. Political Science — sovereignty theory (ps-custom-002)
7. General Knowledge — 2008 global financial crisis (gk-013)
8. General Knowledge — Pakistan water resources / dam policy (gk-003)
9. Islamic Studies — Seerah / Farewell Sermon (is-008)
10. Islamic Studies — jihad vs. terrorism distinction, specifically Paigham-e-Pakistan (is-016)

Secondary (narrower sources only, existing broad source retained either way): IMF-Pakistan specifics
(ca-002), Paris Agreement primary text (ca-013), greenhouse-effect science mechanism (gsa-custom-002).

**Explicitly not targeted with new sources** (would not help, per the analysis above): gc-001, gc-004,
ir-002, is-003, ps-custom-001 — these need a chunking-strategy change to the existing baseline, not new
content, and that change is out of scope for this task.

English's three genuinely-missing scenarios (en-012, en-008, en-014) are also **not** targeted with new
sources in Phase 3: the task's own source-priority list is government/institutional/international-
organization documents, none of which publish English-composition/rhetoric pedagogy. Closing this gap
would require an academic writing-skills reference text, which is a different kind of source than every
other gap on this list — noted here as a real, structural limitation of this corpus's source strategy,
not silently worked around with a lower-quality source just to produce a number.
