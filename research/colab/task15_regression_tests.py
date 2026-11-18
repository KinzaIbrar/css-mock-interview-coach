"""Task 15 Phase 5: targeted, automated regression tests for the Task 15 experimental index. Plain
assertions (this is research tooling, not the backend's pytest suite) against the real built index --
no mocking, no fabricated scores. Run after task15_build_corpus.py. Exits non-zero if any check fails.
"""

import json
import sys
from pathlib import Path

import faiss
from sentence_transformers import SentenceTransformer

HERE = Path(__file__).parent
EMBED_DIR = HERE / "output_task15_coverage" / "InterviewIQ_Dataset" / "08_Embeddings"

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
index = faiss.read_index(str(EMBED_DIR / "css_knowledge_base.faiss"))
records = [json.loads(l) for l in open(EMBED_DIR / "css_knowledge_base_metadata.jsonl", encoding="utf-8") if l.strip()]
with open(EMBED_DIR / "index_config.json", encoding="utf-8") as f:
    config = json.load(f)
assert index.ntotal == len(records) == config["chunk_count"], "index/metadata/config mismatch"


def top_n(query, n=3):
    vec = model.encode([query], normalize_embeddings=True).astype("float32")
    scores, idxs = index.search(vec, n)
    return [(float(s), records[i]) for s, i in zip(scores[0], idxs[0])]


failures = []


def check(name, condition, detail):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}: {detail}")
    if not condition:
        failures.append(name)


# --- Regression 1 fixed: Objectives Resolution real hit back in top-3 ---
hits = top_n("Describe the main features of the Objectives Resolution of 1949 and its role in Pakistan's constitutional development.")
check(
    "pa-002 regression fixed",
    any("ANNEX (Article 2A) The Objectives Resolution" in r["content"] for _, r in hits),
    f"top-3 source titles: {[r['source_title'] for _, r in hits]}",
)
check(
    "pa-002 no longer dominated by Paigham-e-Pakistan",
    sum(1 for _, r in hits if r["source_title"] == "Paigham-e-Pakistan (2018)") == 0,
    f"Paigham-e-Pakistan count in top-3: {sum(1 for _, r in hits if r['source_title'] == 'Paigham-e-Pakistan (2018)')}",
)

# --- Regression 2 fixed: Montesquieu chunk back in top-3 ---
hits = top_n("Explain the theory of separation of powers in classical political thought, referencing Montesquieu.")
check(
    "ps-custom-001 regression fixed",
    any("PAPER: POLITICAL SCIENCE" in r["content"] and "Western Political T" in r["content"] for _, r in hits),
    f"top-3 source titles: {[r['source_title'] for _, r in hits]}",
)
check(
    "ps-custom-001 not buried by Sovereignty chunks",
    sum(1 for _, r in hits if r["source_title"].startswith("Sovereignty")) == 0,
    f"Sovereignty count in top-3: {sum(1 for _, r in hits if r['source_title'].startswith('Sovereignty'))}",
)

# --- Win 1 preserved: WTO ---
hits = top_n("What is the World Trade Organization (WTO) and why does it matter for developing countries?")
check("ca-004 WTO win preserved", hits[0][1]["source_title"] == "Understanding the WTO", f"rank1: {hits[0][1]['source_title']}")

# --- Win 2 preserved: Kashmir/Tashkent ---
hits = top_n("Discuss the Kashmir dispute in the context of international law and bilateral agreements between India and Pakistan.")
check("ir-016 Tashkent win preserved", hits[0][1]["source_title"].startswith("Tashkent"), f"rank1: {hits[0][1]['source_title']}")

# --- Win 3 preserved: jihad vs terrorism ---
hits = top_n("Evaluate the concept of jihad in Islam and distinguish it from terrorism.")
check("is-016 Paigham-e-Pakistan win preserved", hits[0][1]["source_title"] == "Paigham-e-Pakistan (2018)", f"rank1: {hits[0][1]['source_title']}")

# --- Win 4 preserved: Ijtihad/Iqbal ---
hits = top_n("Discuss the concept of Ijtihad and its relevance in addressing contemporary challenges.")
check("is-003 Iqbal/reconstruction win preserved", any("Iqbal" in r["content"] for _, r in hits), f"top-3: {[r['content'][:50] for _, r in hits]}")

# --- Win 5 preserved: sovereignty theory ---
hits = top_n("Discuss the main theories of state sovereignty.")
check("ps-custom-002 Sovereignty win preserved", hits[0][1]["source_title"].startswith("Sovereignty"), f"rank1: {hits[0][1]['source_title']}")

# --- Known, documented, unresolved risk: Lahore Declaration false-match (must NOT silently regress further) ---
hits = top_n("What was the Lahore Resolution of 1940 and why is it significant?")
check(
    "pa-001 false-match is the documented one (not worse)",
    hits[0][1]["source_title"] == "The Lahore Declaration (1999)",
    f"rank1: {hits[0][1]['source_title']} (documented, unresolved -- see lahore_declaration_investigation.md)",
)

print()
if failures:
    print(f"{len(failures)} FAILURE(S):", failures)
    sys.exit(1)
print("All targeted checks passed.")
